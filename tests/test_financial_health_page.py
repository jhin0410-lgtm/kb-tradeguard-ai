from pathlib import Path


def test_financial_health_page_compiles():
    page = Path("pages/9_Financial_Health.py")
    source = page.read_text(encoding="utf-8")
    compile(source, str(page), "exec")
