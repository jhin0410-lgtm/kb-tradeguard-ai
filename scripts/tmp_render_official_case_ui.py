"""Render desktop/mobile competition UI screenshots and verify official case cards."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for name, width, height in (
                ("desktop", 1440, 1000),
                ("mobile", 430, 932),
            ):
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                )
                page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_selector(".tg-case-card", state="visible", timeout=60_000)
                page.wait_for_timeout(3_000)
                card_count = page.locator(".tg-case-card").count()
                if card_count != 3:
                    raise RuntimeError(
                        f"Expected three official case cards in {name} view, found {card_count}"
                    )
                body_text = page.locator("body").inner_text()
                required = (
                    "베트남 전기·전자 수출 맥락",
                    "미국 화장품 수출 맥락",
                    "일본 기계류 수입 맥락",
                    "실제 공개데이터 사례 3개",
                )
                missing = [item for item in required if item not in body_text]
                if missing:
                    raise RuntimeError(
                        f"Missing official case labels in {name} view: {missing}"
                    )
                page.screenshot(
                    path=str(output_dir / f"competition-{name}.png"),
                    full_page=True,
                )
                (output_dir / f"competition-{name}.txt").write_text(
                    body_text,
                    encoding="utf-8",
                )
                page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
