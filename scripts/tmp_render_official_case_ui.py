"""Render desktop/mobile competition UI screenshots and verify official case cards."""

from __future__ import annotations

import argparse
import json
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
    audit_rows = []

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
                cards = page.locator(".tg-case-card")
                card_count = cards.count()
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

                card_geometry = cards.evaluate_all(
                    """elements => elements.map((element) => ({
                        clientWidth: element.clientWidth,
                        scrollWidth: element.scrollWidth,
                        clientHeight: element.clientHeight,
                        scrollHeight: element.scrollHeight,
                        left: element.getBoundingClientRect().left,
                        right: element.getBoundingClientRect().right
                    }))"""
                )
                overflowing = [
                    index
                    for index, item in enumerate(card_geometry, start=1)
                    if item["scrollWidth"] > item["clientWidth"] + 1
                ]
                if overflowing:
                    raise RuntimeError(
                        f"Horizontal overflow in {name} official case cards: {overflowing}"
                    )
                if any(item["left"] < -1 or item["right"] > width + 1 for item in card_geometry):
                    raise RuntimeError(
                        f"Official case card extends outside the {name} viewport"
                    )

                page.screenshot(path=str(output_dir / f"competition-{name}-top.png"))
                cards.first.scroll_into_view_if_needed()
                page.wait_for_timeout(1_000)
                page.screenshot(path=str(output_dir / f"competition-{name}-cases.png"))
                (output_dir / f"competition-{name}.txt").write_text(
                    body_text,
                    encoding="utf-8",
                )
                audit_rows.append(
                    {
                        "viewport": name,
                        "width": width,
                        "height": height,
                        "card_count": card_count,
                        "card_geometry": card_geometry,
                        "required_labels_present": True,
                        "horizontal_overflow": False,
                    }
                )
                page.close()
        finally:
            browser.close()

    (output_dir / "ui-audit.json").write_text(
        json.dumps(audit_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
