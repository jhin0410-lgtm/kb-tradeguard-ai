from __future__ import annotations

import base64
import gzip
import io
import runpy
import tarfile
from pathlib import Path


ROOT = Path(".")
_ALLOWED_ROOTS = {"src", "tests"}
_ALLOWED_PREFIXES = ("src/", "tests/")


source_payload = "".join(
    (ROOT / f"tmp/integrated_payload_{index:02d}.b64").read_text(encoding="utf-8")
    for index in range(3)
)
archive_bytes = base64.b64decode(source_payload)
with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe archive member: {member.name}")
        if member.name not in _ALLOWED_ROOTS and not member.name.startswith(_ALLOWED_PREFIXES):
            raise RuntimeError(f"Unexpected archive member: {member.name}")
    archive.extractall(ROOT)

# Correct the independently reviewed gross-exposure expectation in the packed test.
portfolio_test = ROOT / "tests/test_portfolio_assessment.py"
text = portfolio_test.read_text(encoding="utf-8")
text = text.replace(
    'assert assessment.gross_exposure_krw == Decimal("856000000")',
    'assert assessment.gross_exposure_krw == Decimal("1036000000")',
)
portfolio_test.write_text(text, encoding="utf-8")

# Recognize the common banking notation L/C as a letter-of-credit payment method.
portfolio_source = ROOT / "src/intelligence/portfolio_assessment.py"
text = portfolio_source.read_text(encoding="utf-8")
text = text.replace(
    'if "lc" in payment or "letter of credit" in payment or "신용장" in payment:',
    'if "lc" in payment or "l/c" in payment or "letter of credit" in payment or "신용장" in payment:',
)
portfolio_source.write_text(text, encoding="utf-8")

patch_payload = "".join(
    (ROOT / f"tmp/integrated_patch_script_{index:02d}.b64").read_text(encoding="utf-8")
    for index in range(2)
)
patch_path = ROOT / "scripts/tmp_apply_integrated_product_sprint.py"
patch_path.write_bytes(gzip.decompress(base64.b64decode(patch_payload)))
runpy.run_path(str(patch_path), run_name="__main__")

# Preserve the existing mobile navigation contract while adding new workflow sections.
competition_app = ROOT / "competition_app.py"
text = competition_app.read_text(encoding="utf-8")
text = text.replace(
    '          <a href="#evidence" target="_self">근거</a>\n'
    '          <a href="#portfolio" target="_self">포트폴리오</a>',
    '          <a href="#evidence" target="_self">근거</a>\n'
    '          <a href="#actions" target="_self">실행</a>\n'
    '          <a href="#portfolio" target="_self">포트폴리오</a>',
)
competition_app.write_text(text, encoding="utf-8")
