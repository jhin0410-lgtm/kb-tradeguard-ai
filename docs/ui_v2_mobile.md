# Product UI V2 and Mobile Access

## Entry points

- `assessment_app_v2.py`: desktop-first V2 with 60-second and detailed review modes
- `assessment_app_v2_mobile.py`: mobile-first V2 with a compact hero, compressed 2×2 flow, collapsed sidebar, and a main-page run button

Both entrypoints reuse the same deterministic assessment pipeline and governed V2 view models.

## V2 goals

1. **60-second product screen** — disposition, top three risks, evidence coverage, and next three actions appear before detailed tables.
2. **Risk-first summary** — no opaque aggregate score; ranked concerns keep severity, category, factual basis, unresolved facts, and Reference IDs.
3. **Evidence Drawer** — each risk opens a native Streamlit popover that resolves direct references and one linked layer across RiskSignal, Evidence, Calculation, CountryFact, Compliance, Counterparty, ClauseFinding, and TradeDocument records.
4. **Mobile compact mode** — responsive CSS plus a four-tab information architecture for phones and presentation screens.
5. **Presentation Snapshot V2** — a self-contained offline HTML snapshot and deterministic JSON snapshot containing the top risks, next actions, stage statuses, authority boundary, and case hashes.

The V2 layer is read-only presentation logic. It does not create or change findings, calculations, disposition, action dependencies, product candidates, or institution-specific decisions.

## Desktop run

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run assessment_app_v2.py
```

## Polished phone run

The phone-specific entrypoint is optimized for the screenshots reviewed on 2026-07-28:

- the hero is shorter and no longer dominates the first viewport;
- the three product principles are compact pills rather than full-height cards;
- the four-step flow uses a 2×2 grid;
- the sidebar starts collapsed;
- the primary `5단계 사전진단 시작` action is also available in the main page.

Use the included Windows launcher:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run-mobile-demo.ps1
```

The script:

- finds a local IPv4 address;
- binds Streamlit to `0.0.0.0`;
- launches `assessment_app_v2_mobile.py`;
- prints a phone URL such as `http://192.168.0.15:8501/?view=compact`.

Requirements:

- PC and phone must be on the same trusted Wi-Fi network;
- Windows Firewall should be allowed only for Private networks;
- VPN, guest-network isolation, or corporate Wi-Fi policy may prevent device-to-device access;
- this mode is for synthetic demo data only.

Manual equivalent:

```powershell
ipconfig
py -3.13 -m streamlit run assessment_app_v2_mobile.py `
  --server.address 0.0.0.0 `
  --server.port 8501 `
  --server.headless true
```

Then open this on the phone:

```text
http://<PC IPv4 address>:8501/?view=compact
```

## Public URL for off-site phone access

A phone does not connect directly to the Python process as a native mobile app. The Streamlit server hosts a responsive web application, and the phone opens its HTTPS URL in a browser.

For a public competition demo:

1. deploy the public repository with `assessment_app_v2_mobile.py` or `assessment_app_v2.py` as the app entrypoint;
2. keep all API keys and private files out of the repository;
3. use synthetic showcase scenarios only;
4. disable or avoid real-document uploads on a publicly shared demo unless a separate secure storage and privacy design is implemented;
5. share the URL with `?view=compact` for the phone-oriented screen.

A browser shortcut can be added to the phone home screen, but this is still a web app, not a native Android or iOS application.

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

Do not split the engine into an API merely for visual polish before the competition. The V2 Streamlit UI should first validate the user workflow and presentation narrative.

## Screenshot checklist

Capture both desktop detailed and polished phone modes:

- mobile hero, compact principle pills, and main-page run button;
- 60-second disposition and KPI strip;
- top three risk cards;
- Evidence Drawer open on the highest-ranked risk;
- next three actions;
- compact four-tab navigation;
- Presentation Snapshot HTML preview;
- audit hashes and download controls.

## Trust boundary

Mobile access changes only the display channel. It does not make the prototype production-ready or authorize processing of real customer documents. Public access must remain synthetic-demo-only until authentication, authorization, encrypted storage, retention, monitoring, and privacy controls are designed and reviewed.
