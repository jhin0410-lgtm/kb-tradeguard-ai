"""Canonical deployment entrypoint for the public competition demo."""

from __future__ import annotations

import os

from src.demo_scenarios import DemoScenarioMetadata


PUBLIC_DEMO_URL = "https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/"

# The public URL is not a secret. An explicit deployment environment value can still
# override it if the app is moved or renamed later.
os.environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", PUBLIC_DEMO_URL)

# competition_app originally called the display field ``label`` while the governed
# metadata contract names it ``title``. Keep the deployment entrypoint backward
# compatible without changing scenario content or deterministic assessment behavior.
if not hasattr(DemoScenarioMetadata, "label"):
    DemoScenarioMetadata.label = property(lambda item: item.title)  # type: ignore[attr-defined]

from competition_app import main  # noqa: E402


if __name__ == "__main__":
    main()
