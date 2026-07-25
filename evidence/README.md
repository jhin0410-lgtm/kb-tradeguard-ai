# Provider verification evidence

Run `python scripts/provider_smoke_test.py` manually with valid optional
provider configuration. A successful live run writes
`provider_smoke_redacted.json`, containing synthetic demo answers, citation
identifiers, selected tools, and validation outcomes only.

The generated transcript is ignored by default. Review it before intentionally
including it in any submission evidence. A missing transcript means live
provider verification has not been completed.
