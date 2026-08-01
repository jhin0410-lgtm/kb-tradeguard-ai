"""Verify the generated submission ZIP in an isolated extracted directory."""
from __future__ import annotations

import argparse
import compileall
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_REQUIRED = {
    "streamlit_app.py",
    "competition_app.py",
    "assessment_app.py",
    "requirements.txt",
    "README.md",
    ".streamlit/config.toml",
    "src",
    "pages",
    "data",
    "docs",
    "scripts",
    "tests",
    "submission-manifest.json",
}
_BANNED_PARTS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "outputs",
}
_BANNED_NAMES = {".env", "secrets.toml"}
_BANNED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _validate_members(names: list[str]) -> str:
    roots = {name.split("/", 1)[0] for name in names if name and not name.endswith("/")}
    if len(roots) != 1:
        raise ValueError(f"Submission ZIP must contain exactly one root directory: {sorted(roots)}")
    root = next(iter(roots))
    relative_names = {
        name[len(root) + 1 :]
        for name in names
        if name.startswith(root + "/") and not name.endswith("/")
    }
    missing = sorted(
        item
        for item in _REQUIRED
        if item not in relative_names
        and not any(name.startswith(item.rstrip("/") + "/") for name in relative_names)
    )
    if missing:
        raise ValueError("Submission ZIP is missing required paths: " + ", ".join(missing))
    for relative in relative_names:
        path = Path(relative)
        if any(part in _BANNED_PARTS for part in path.parts):
            raise ValueError(f"Banned directory included in submission ZIP: {relative}")
        if path.name in _BANNED_NAMES or path.suffix.lower() in _BANNED_SUFFIXES:
            raise ValueError(f"Banned file included in submission ZIP: {relative}")
    return root


def _verify_manifest(root: Path) -> dict:
    manifest_path = root / "submission-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("entrypoint") != "streamlit_app.py":
        raise ValueError("Submission manifest entrypoint is not streamlit_app.py")
    if manifest.get("run_command") != "python -m streamlit run streamlit_app.py":
        raise ValueError("Submission manifest run command is inconsistent")
    listed = {str(item["path"]) for item in manifest.get("files", [])}
    for required_file in ("streamlit_app.py", "competition_app.py", "requirements.txt"):
        if required_file not in listed:
            raise ValueError(f"Manifest does not list required file: {required_file}")
    return manifest


def _verify_import(root: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "import streamlit_app; import competition_app; import assessment_app; import src; print('submission-import-ok')",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Extracted submission import failed:\n" + result.stdout + "\n" + result.stderr
        )


def _verify_streamlit_health(root: Path, timeout_seconds: int) -> None:
    port = _free_port()
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    env = {
        **os.environ,
        "PYTHONPATH": str(root),
        "TRADEGUARD_ENABLE_PRIVATE_WORKSPACE": "false",
    }
    process = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + timeout_seconds
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    output: list[str] = []
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                if process.stdout is not None:
                    output.extend(process.stdout.readlines())
                raise RuntimeError(
                    "Extracted Streamlit app stopped before becoming healthy:\n"
                    + "".join(output[-80:])
                )
            try:
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    body = response.read().decode("utf-8", errors="replace").strip().lower()
                    if response.status == 200 and body == "ok":
                        return
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        raise TimeoutError(
            f"Extracted Streamlit app did not become healthy within {timeout_seconds} seconds"
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def verify_package(archive: Path, *, start_app: bool, timeout_seconds: int = 45) -> dict:
    archive = archive.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    with tempfile.TemporaryDirectory(prefix="tradeguard-submission-") as temporary:
        extract_dir = Path(temporary)
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            root_name = _validate_members(names)
            package.extractall(extract_dir)
        root = extract_dir / root_name
        manifest = _verify_manifest(root)
        if not compileall.compile_dir(root, quiet=1):
            raise RuntimeError("Extracted submission compileall failed")
        _verify_import(root)
        if start_app:
            _verify_streamlit_health(root, timeout_seconds)
        return {
            "status": "verified",
            "archive": str(archive),
            "root": root_name,
            "manifest_file_count": manifest.get("file_count"),
            "compileall": True,
            "imports": True,
            "streamlit_health": bool(start_app),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--start-app", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()
    result = verify_package(
        args.archive,
        start_app=args.start_app,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
