# Product UI V2 and Mobile Access

## Entry points

- `competition_app.py`: single-screen public competition demo for desktop and mobile
- `streamlit_app.py`: canonical public deployment entrypoint
- `assessment_app_v2.py`: desktop-first V2 with 60-second and detailed review modes
- `assessment_app_v2_mobile.py`: mobile-first V2 development entrypoint

All entrypoints reuse the same deterministic assessment pipeline and governed V2 view models.

## V2 goals

1. **60-second product screen** — disposition, top three risks, evidence coverage, and next three actions appear before detailed tables.
2. **Risk-first summary** — no opaque aggregate score; ranked concerns keep severity, category, factual basis, unresolved facts, and Reference IDs.
3. **Evidence Drawer** — each risk resolves direct references and one linked layer across RiskSignal, Evidence, Calculation, CountryFact, Compliance, Counterparty, ClauseFinding, and TradeDocument records.
4. **Mobile navigation** — the public app fixes `요약 | 근거 | 실행 | 감사` at the bottom of the phone screen.
5. **Presentation Snapshot V2** — a self-contained offline HTML snapshot and deterministic JSON snapshot containing the top risks, next actions, stage statuses, authority boundary, and case hashes.

The V2 layer is read-only presentation logic. It does not create or change findings, calculations, disposition, action dependencies, product candidates, or institution-specific decisions.

## Desktop run

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run competition_app.py
```

The default high-risk synthetic scenario runs automatically. Detailed development review remains available through `assessment_app_v2.py` and `assessment_app.py`.

## Phone connection on the same Wi-Fi

Use the included Windows launcher:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run-mobile-demo.ps1
```

The script:

- finds a local IPv4 address;
- binds Streamlit to `0.0.0.0`;
- launches `competition_app.py`;
- sets the same-Wi-Fi address as the local QR target;
- prints a phone URL such as `http://192.168.0.15:8501/?demo=1`.

Requirements:

- PC and phone must be on the same trusted Wi-Fi network;
- Windows Firewall should be allowed only for Private networks;
- VPN, guest-network isolation, or corporate Wi-Fi policy may prevent device-to-device access;
- this mode is for synthetic demo data only.

Manual equivalent:

```powershell
ipconfig
$env:TRADEGUARD_PUBLIC_DEMO_URL="http://<PC IPv4 address>:8501/"
py -3.13 -m streamlit run competition_app.py `
  --server.address 0.0.0.0 `
  --server.port 8501 `
  --server.headless true
```

Then open this on the phone:

```text
http://<PC IPv4 address>:8501/?demo=1
```

## Public URL for off-site phone access

A phone does not connect directly to the Python process as a native mobile app. The Streamlit server hosts a responsive web application, and the phone opens its HTTPS URL in a browser.

For a public competition demo:

1. deploy `streamlit_app.py`;
2. configure `TRADEGUARD_PUBLIC_DEMO_URL` with the deployed HTTPS address;
3. keep all API keys and private files out of the repository;
4. use synthetic showcase scenarios only;
5. share the generated QR or the URL with `?demo=1`.

The public app omits JSON upload, original-document upload, Live AI, API-key input, and customer-data storage.

A browser shortcut can be added to the phone home screen, but this is still a web app, not a native Android or iOS application.

## Presentation mode

Use:

```text
https://<public-demo>/?presentation=1
```

This mode hides scenario controls, audit downloads, QR notices, and bottom navigation. It keeps only:

- product definition;
- deterministic disposition;
- top three risks;
- next three actions.

## When to move beyond Streamlit

Streamlit is appropriate for the current competition prototype because the engine, validation, audit export, and demo workflow are Python-first. A full native-product architecture should be a later step:

```text
Deterministic Python domain engine
        ↓
FastAPI service boundary
        ↓
Responsive web/PWA or Flutter/React Native client
        ↓
Authentication, encrypted storage, institution integration, audit operations
```

Do not split the engine into an API merely for visual polish before the competition. The current public UI should first validate the user workflow and presentation narrative.

## Screenshot checklist

Capture both desktop and phone public-demo modes:

- public hero and disposition;
- top three risk cards;
- highest-ranked risk with `판단 근거 열기` open;
- next three actions;
- fixed mobile bottom navigation;
- regression-validation status;
- public QR;
- Presentation Snapshot HTML preview;
- audit hashes and download controls;
- `presentation=1` full-screen view.

## Trust boundary

Mobile access changes only the display channel. It does not make the prototype production-ready or authorize processing of real customer documents. Public access must remain synthetic-demo-only until authentication, authorization, encrypted storage, retention, monitoring, and privacy controls are designed and reviewed.
