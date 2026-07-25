from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "page_path",
    [
        "pages/8_Official_Data.py",
        "pages/9_Financial_Health.py",
        "pages/10_Financial_Trends.py",
    ],
)
def test_streamlit_page_compiles(page_path):
    page = Path(page_path)
    source = page.read_text(encoding="utf-8")
    compile(source, str(page), "exec")
