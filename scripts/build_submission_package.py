"""Build a clean, reproducible KB TradeGuard AI submission source package."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

_REQUIRED_PATHS = (
    "streamlit_app.py",
    "competition_app.py",
    "assessment_app.py",
    "assessment_app_v2.py",
    "assessment_app_v2_mobile.py",
    "app.py",
    "copilot_app.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    ".env.example",
    ".streamlit/config.toml",
    "src",
    "pages",
    "data",
    "docs",
    "scripts",
    "tests",
)

_EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "outputs",
    "node_modules",
}
_EXCLUDED_NAMES = {
    ".env",
    "secrets.toml",
    ".DS_Store",
    "Thumbs.db",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".zip"}


def _is_included(path: Path, root: Path, output: Path) -> bool:
    relative = path.relative_to(root)
    if path.resolve() == output.resolve():
        return False
    if any(part in _EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name in _EXCLUDED_NAMES:
        return False
    if path.suffix.lower() in _EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    return path.is_file()


def collect_files(root: Path, output: Path) -> list[Path]:
    missing = [item for item in _REQUIRED_PATHS if not (root / item).exists()]
    if missing:
        raise FileNotFoundError("Missing required submission paths: " + ", ".join(missing))
    files = [path for path in root.rglob("*") if _is_included(path, root, output)]
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_package(root: Path, output: Path, *, prefix: str = "KB-TradeGuard-AI") -> dict:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = collect_files(root, output)
    entries: list[dict[str, object]] = []

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            arcname = str(PurePosixPath(prefix) / PurePosixPath(relative))
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
            entries.append({"path": relative, "size": len(data), "sha256": _sha256(data)})

        manifest = {
            "schema_version": "tradeguard-submission-package/1.0",
            "entrypoint": "streamlit_app.py",
            "run_command": "python -m streamlit run streamlit_app.py",
            "file_count": len(entries),
            "files": entries,
            "excluded": sorted(_EXCLUDED_PARTS | _EXCLUDED_NAMES),
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        info = zipfile.ZipInfo(f"{prefix}/submission-manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, manifest_bytes)

    result = {
        "output": str(output),
        "file_count": len(entries),
        "archive_size": output.stat().st_size,
        "archive_sha256": _sha256(output.read_bytes()),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist/KB-TradeGuard-AI-prototype.zip"))
    parser.add_argument("--prefix", default="KB-TradeGuard-AI")
    args = parser.parse_args()
    result = build_package(args.root, args.output, prefix=args.prefix)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
