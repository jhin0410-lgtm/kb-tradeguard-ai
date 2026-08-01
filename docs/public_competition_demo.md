# Public Competition Demo

## Purpose

`streamlit_app.py` is the only user-facing execution and deployment entrypoint.

The same application contains four connected modes:

```text
Decision Desk
Analyst Workspace
Portfolio & Official Data
Evidence & Submission
```

The public presentation URL always opens the synthetic Decision Desk and hides workspace navigation.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Default URL:

```text
http://localhost:8501/?mode=decision
```

Presentation URL:

```text
http://localhost:8501/?presentation=1&scenario=oa_high_risk
```

Additional modes:

```text
http://localhost:8501/?mode=analyst
http://localhost:8501/?mode=portfolio
http://localhost:8501/?mode=evidence
```

## Public deployment

Streamlit Cloud app file:

```text
streamlit_app.py
```

Public URL:

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/
```

Presentation URL:

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/?presentation=1&scenario=oa_high_risk
```

Configure the public QR URL through:

```text
TRADEGUARD_PUBLIC_DEMO_URL=https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/
```

The QR is generated locally and no external QR service is used.

## Decision Desk

The default synthetic case runs automatically and displays:

1. active company, scenario, country, transaction count and governed disposition;
2. current transaction decision cockpit;
3. top risks and Evidence IDs;
4. governed Action Plan;
5. transaction-value-based FX Stress;
6. natural hedge and net exposure;
7. monthly ending cash;
8. dynamic ProductCandidate top three;
9. current-case KB consultation handoff;
10. validation and audit downloads.

Scenario changes rerun the same five-stage deterministic pipeline. Values are not inferred or silently corrected.

## Analyst Workspace

The workspace is available inside the same application but must be treated as a Private/local review surface.

- reviewed JSON Package input;
- contract and L/C findings;
- document reconciliation;
- transaction-capacity analysis;
- Human Review Overlay;
- full ProductCandidate view;
- Action dependency;
- audit ZIP;
- optional Grounded Live AI.

Do not upload real customer information or credentials to the public deployment.

## Portfolio & Official Data

This mode receives the active `run.updated_case` from Decision Desk.

It does not default to an unrelated demo workspace when an active Case exists.

- currency exposure;
- natural hedge;
- monthly liquidity;
- FX sensitivity;
- current-case product candidates;
- attached official-data Snapshot status;
- optional read-only official API surfaces.

## Evidence & Submission

- 22 rules;
- 30 Gold cases;
- 150 semantic-preserving mutations;
- 4 governed scenarios;
- Package/Input/Output hash;
- presentation HTML;
- audit JSON;
- detailed audit bundle.

These values describe internal deterministic regression and traceability. They do not establish legal accuracy, transaction safety, bank approval, K-SURE acceptance, insurance coverage or product eligibility.

## Presentation mode

`presentation=1` keeps only the four-step narrative:

```text
거래 판정 → 위험 시나리오 → 금융지원 → 근거·검증
```

It hides the sidebar, scenario controls and detailed workspace modes.

## Capture list

1. unified product header and active Case strip;
2. Decision Cockpit;
3. top risk with evidence open;
4. FX Stress and net exposure;
5. dynamic ProductCandidate cards;
6. current-case KB handoff;
7. mode navigation in normal view;
8. Analyst Workspace document tab;
9. connected Portfolio view;
10. Evidence & Submission downloads;
11. mobile view;
12. presentation full screen.

Do not capture browser account information, local paths, API keys or real customer information.

## Trust boundary

The public app is a synthetic-data competition prototype. It does not provide transaction approval, legal advice, sanctions or AML clearance, credit decisions, executable pricing, product eligibility or automated business blocking.
