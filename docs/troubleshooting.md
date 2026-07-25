# Troubleshooting

## The app says deterministic fallback

This is the safe default. Install `requirements-ai.txt` and set the optional
environment variables locally to exercise configured structured AI. Never
place credentials in tracked files.

## PowerShell blocks a script

Use `run.cmd` or `test.cmd`, which do not depend on PowerShell script execution
policy. The `.ps1` equivalents are retained for environments that permit them.

## A policy checksum mismatch appears

The local summary no longer matches its reviewed manifest checksum. Review the
content against the official link, update its review metadata, and then update
the checksum. Do not bypass the check.

## A spreadsheet row is invalid

Review the preserved sheet/row provenance and required fields. Parsing
confidence only indicates that a cell was read; it does not establish correct
semantic mapping.

## Streamlit loses session transactions

The prototype uses in-memory session state and is not a durable system of
record. Export the audit JSON when evidence is needed.

## Theoretical rates differ from a bank quote

The prototype uses disclosed deterministic assumptions and ACT/365 tenor.
It has no executable pricing integration; confirm actual terms with the bank.
