from pathlib import Path

from src.public_repo_safety import build_public_repo_safety_report


def test_public_repo_safety_accepts_placeholder_configuration(tmp_path: Path):
    (tmp_path / ".env.example").write_text(
        "OPENAI_API_KEY=\nTRADEGUARD_LIVE_DATA=false\n",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('safe')\n", encoding="utf-8")

    report = build_public_repo_safety_report(tmp_path)

    assert report["report_version"] == "public-repo-safety/1.1"
    assert report["status"] == "safe"
    assert report["finding_count"] == 0
    assert report["text_scanned_file_count"] == 2


def test_public_repo_safety_flags_secret_shaped_text(tmp_path: Path):
    token = "sk-" + "A" * 32
    (tmp_path / "config.txt").write_text(
        f"OPENAI_API_KEY={token}\n",
        encoding="utf-8",
    )

    report = build_public_repo_safety_report(tmp_path)

    assert report["status"] == "review_required"
    assert any(
        item["reason"] == "openai_api_key" for item in report["findings"]
    )


def test_public_repo_safety_scans_shell_notebooks_xml_and_env_examples(tmp_path: Path):
    secrets = {
        "deploy.sh": "TOKEN=" + "ghp_" + "A" * 24,
        "analysis.ipynb": '"api_key": "' + "AIza" + "A" * 35 + '"',
        "settings.xml": "<key>" + "AKIA" + "A" * 16 + "</key>",
        ".env.example": "OPENAI_API_KEY=" + "sk-" + "B" * 32,
    }
    for filename, text in secrets.items():
        (tmp_path / filename).write_text(text, encoding="utf-8")

    report = build_public_repo_safety_report(tmp_path)

    flagged_paths = {
        item["path"]
        for item in report["findings"]
        if item["kind"] == "credential_pattern"
    }
    assert flagged_paths == set(secrets)
    assert report["text_scanned_file_count"] == len(secrets)


def test_public_repo_safety_skips_binary_content_without_crashing(tmp_path: Path):
    (tmp_path / "image.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00" + b"sk-" + b"A" * 32)

    report = build_public_repo_safety_report(tmp_path)

    assert report["status"] == "safe"
    assert report["scanned_file_count"] == 1
    assert report["text_scanned_file_count"] == 0


def test_public_repo_safety_flags_private_paths(tmp_path: Path):
    private_dir = tmp_path / "data" / "private"
    private_dir.mkdir(parents=True)
    (private_dir / "customer.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".streamlit").mkdir()
    (tmp_path / ".streamlit" / "secrets.toml").write_text(
        "TOKEN='redacted'\n",
        encoding="utf-8",
    )

    report = build_public_repo_safety_report(tmp_path)

    flagged_paths = {item["path"] for item in report["findings"]}
    assert "data/private/customer.json" in flagged_paths
    assert ".streamlit/secrets.toml" in flagged_paths
