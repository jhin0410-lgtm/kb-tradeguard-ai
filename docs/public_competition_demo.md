# Public Competition Demo

## Purpose

`competition_app.py` is the single-screen public demonstration surface. `streamlit_app.py` is the canonical deployment entrypoint.

The public app is deliberately narrower than the development workspace:

- synthetic showcase scenarios only;
- no JSON or original-document upload;
- no Live AI call;
- no API-key input;
- no customer-data storage;
- no Official Data, Financial Health, Financial Trends, or Live FX development pages in the public navigation.

The underlying deterministic five-stage assessment pipeline is unchanged.

## Run locally

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run competition_app.py
```

The default `oa_high_risk` scenario runs automatically. Use the compact scenario selector to switch to another governed synthetic case.

Useful query parameters:

```text
?demo=1
?scenario=oa_high_risk
?presentation=1
```

`presentation=1` hides scenario controls, audit downloads, QR configuration messages, and the bottom navigation. It retains only the product statement, deterministic disposition, top risks, and next actions.

## Public HTTPS deployment

Deploy `streamlit_app.py` as the app file. The repository already includes `.streamlit/config.toml` for the public theme and disabled usage telemetry.

Configure the deployed HTTPS URL through a secret or environment variable:

```text
TRADEGUARD_PUBLIC_DEMO_URL=https://your-app-name.streamlit.app/
```

The app creates the QR image locally with the configured URL. It does not call an external QR service.

The QR points to the governed public-demo URL with `demo=1`. The app rejects relative URLs and non-HTTP(S) schemes.

## Mobile information architecture

A fixed bottom navigation keeps the four customer-facing sections accessible:

```text
요약 | 근거 | 실행 | 감사
```

The public terminology is Korean-first:

- Risk-first → 핵심 위험 우선
- Evidence Drawer → 판단 근거
- Reference ID → 근거 ID
- Audit Snapshot → 검토 기록 / 감사 Snapshot
- Decision Brief → 거래 검토 요약

Detailed record IDs remain available inside the evidence and audit views.

## Automatic result view

The public app does not stop at an instructional landing page. It runs the default synthetic case and displays:

1. deterministic disposition;
2. five-stage trace;
3. top three risks;
4. evidence counts and linked records;
5. next three actions;
6. regression-validation counts;
7. presentation HTML and audit JSON downloads.

Scenario changes rerun the same deterministic pipeline. No input fields are inferred or silently corrected.

## Validation status

The app exposes compact regression-coverage counts:

- 22 governed trade-document rules;
- 30 explicit Gold cases;
- 150 semantic-preserving mutations;
- 4 governed showcase scenarios.

These values describe internal deterministic regression fixtures. They do not establish legal accuracy, transaction safety, bank approval, K-SURE acceptance, insurance coverage, or product eligibility.

## Presentation capture

Recommended screenshots after deployment:

1. HTTPS public hero and disposition;
2. top three risks;
3. highest-ranked risk with `판단 근거 열기` open;
4. next three actions;
5. mobile fixed bottom navigation;
6. regression-validation status;
7. QR code and mobile browser result;
8. Case hash and snapshot download area;
9. `presentation=1` full-screen view.

Do not capture browser tabs, local file paths, API keys, or real customer information.

## Trust boundary

The public app is a synthetic-data competition prototype. It does not provide transaction approval, legal advice, sanctions or AML clearance, credit decisions, executable pricing, product eligibility, or automated business blocking.
