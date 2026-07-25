import json

from src.provenance import AuditTrail


def test_audit_json_contains_events_assumptions_and_no_document_bytes():
    events = []
    audit = AuditTrail(events)
    audit.record(
        "upload",
        source_filename="invoice.csv",
        extraction_provider="deterministic_csv_heading_map",
        document_bytes_persisted=False,
    )
    report = json.loads(
        audit.export_json(
            {
                "as_of_date": "2026-08-31",
                "hedge_basis": "Expected transaction exposure",
                "hedge_ratios": {"USD": 0.5},
            }
        )
    )
    assert report["events"][0]["event_type"] == "upload"
    assert report["events"][0]["document_bytes_persisted"] is False
    assert report["calculation_assumptions"]["hedge_ratios"] == {"USD": 0.5}
    assert "content" not in report["events"][0]
