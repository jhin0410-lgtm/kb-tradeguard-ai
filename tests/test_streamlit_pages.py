from pathlib import Path


def test_official_data_page_compiles():
    page = Path("pages/8_Official_Data.py")
    source = page.read_text(encoding="utf-8")
    compile(source, str(page), "exec")
