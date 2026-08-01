"""Capture actual rendered KB TradeGuard AI pages with Selenium.

This script starts the canonical Streamlit entrypoint, waits until governed page
content is visible in a real browser, and writes desktop/mobile screenshots plus
an integrity manifest. The public workspace flag remains disabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True)
class CaptureTarget:
    filename: str
    query: str
    width: int
    height: int
    marker: str


TARGETS = (
    CaptureTarget(
        "01-decision-desk-desktop.png",
        "?mode=decision&scenario=oa_high_risk",
        1440,
        2200,
        "TRADE DECISION COCKPIT",
    ),
    CaptureTarget(
        "02-portfolio-official-data.png",
        "?mode=portfolio&scenario=oa_high_risk",
        1440,
        1800,
        "CONNECTED CASE ANALYTICS",
    ),
    CaptureTarget(
        "03-evidence-submission.png",
        "?mode=evidence&scenario=oa_high_risk",
        1440,
        1800,
        "SUBMISSION & AUDIT EVIDENCE",
    ),
    CaptureTarget(
        "04-presentation-mode.png",
        "?presentation=1&scenario=oa_high_risk",
        1440,
        2200,
        "TRADE DECISION COCKPIT",
    ),
    CaptureTarget(
        "05-decision-desk-mobile.png",
        "?mode=decision&scenario=oa_high_risk",
        430,
        1900,
        "TRADE DECISION COCKPIT",
    ),
)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, process: subprocess.Popen[str], timeout: int) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError("Streamlit exited before capture:\n" + output)
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200 and response.read().decode().strip().lower() == "ok":
                    return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"Streamlit did not become healthy within {timeout} seconds")


def browser_options(profile: Path, width: int, height: int) -> Options:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    return options


def capture_page(base_url: str, output_dir: Path, target: CaptureTarget, timeout: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="tradeguard-chrome-") as profile_text:
        driver = webdriver.Chrome(options=browser_options(Path(profile_text), target.width, target.height))
        try:
            driver.set_page_load_timeout(timeout)
            driver.get(base_url + target.query)
            wait = WebDriverWait(driver, timeout, poll_frequency=0.5)
            wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
            wait.until(lambda browser: target.marker in browser.find_element("tag name", "body").text)
            wait.until(lambda browser: "Running" not in browser.find_element("tag name", "body").text[:100])
            time.sleep(4)
            driver.execute_script("window.scrollTo(0, 0)")
            driver.set_window_size(target.width, target.height)
            path = output_dir / target.filename
            if not driver.save_screenshot(str(path)):
                raise RuntimeError(f"Selenium did not save {path}")
        except TimeoutException as exc:
            body = ""
            try:
                body = driver.find_element("tag name", "body").text[:2000]
            except Exception:
                pass
            raise RuntimeError(
                f"Timed out waiting for marker {target.marker!r} at {target.query}. Body:\n{body}"
            ) from exc
        finally:
            driver.quit()

    size = path.stat().st_size
    if size < 10_000:
        raise RuntimeError(f"Screenshot appears incomplete: {path} ({size} bytes)")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "file": path.name,
        "bytes": size,
        "sha256": digest,
        "query": target.query,
        "marker": target.marker,
        "viewport": [target.width, target.height],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/ui-captures"))
    parser.add_argument("--startup-timeout", type=int, default=90)
    parser.add_argument("--render-timeout", type=int, default=90)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    env = {
        **os.environ,
        "TRADEGUARD_ENABLE_PRIVATE_WORKSPACE": "false",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "PYTHONPATH": str(root),
    }
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
    process = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(port, process, args.startup_timeout)
        base_url = f"http://127.0.0.1:{port}/"
        captures = [
            capture_page(base_url, output_dir, target, args.render_timeout)
            for target in TARGETS
        ]
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if process.stdout:
            (output_dir / "streamlit.log").write_text(process.stdout.read(), encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entrypoint": "streamlit_app.py",
        "private_workspace_enabled": False,
        "capture_count": len(captures),
        "captures": captures,
    }
    (output_dir / "capture-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
