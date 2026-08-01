import json
import zipfile
from pathlib import Path

from scripts.build_submission_package import build_package, collect_files


def test_submission_package_collects_required_entrypoint_and_excludes_cache(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    required_files = {
        "streamlit_app.py": "print('app')\n",
        "competition_app.py": "",
        "assessment_app.py": "",
        "assessment_app_v2.py": "",
        "assessment_app_v2_mobile.py": "",
        "app.py": "",
        "copilot_app.py": "",
        "requirements.txt": "streamlit\n",
        "README.md": "# test\n",
        "LICENSE": "test\n",
        "SECURITY.md": "test\n",
        ".env.example": "OPENAI_API_KEY=replace\n",
        ".streamlit/config.toml": "[theme]\n",
        "src/module.py": "",
        "pages/page.py": "",
        "data/sample.json": "{}\n",
        "docs/guide.md": "",
        "scripts/tool.py": "",
        "tests/test_x.py": "",
    }
    for relative, content in required_files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__/module.pyc").write_bytes(b"cache")
    (root / ".env").write_text("SECRET=bad\n", encoding="utf-8")
    output = tmp_path / "submission.zip"

    files = collect_files(root, output)
    names = {path.relative_to(root).as_posix() for path in files}

    assert "streamlit_app.py" in names
    assert ".streamlit/config.toml" in names
    assert ".env.example" in names
    assert ".env" not in names
    assert "__pycache__/module.pyc" not in names


def test_submission_package_contains_manifest_and_single_root(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for relative in (
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
        "src/module.py",
        "pages/page.py",
        "data/sample.json",
        "docs/guide.md",
        "scripts/tool.py",
        "tests/test_x.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative + "\n", encoding="utf-8")
    output = tmp_path / "submission.zip"

    result = build_package(root, output)

    assert result["file_count"] >= 19
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert all(name.startswith("KB-TradeGuard-AI/") for name in names)
        assert "KB-TradeGuard-AI/streamlit_app.py" in names
        manifest = json.loads(archive.read("KB-TradeGuard-AI/submission-manifest.json"))
    assert manifest["entrypoint"] == "streamlit_app.py"
    assert manifest["run_command"] == "python -m streamlit run streamlit_app.py"
