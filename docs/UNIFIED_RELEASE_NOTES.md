# Unified Product Release Notes

## Goal

Expose KB TradeGuard AI as one connected product through `streamlit_app.py` instead of requiring users or judges to choose between multiple Streamlit entrypoints.

## Product modes

- Decision Desk: public synthetic decision workflow
- Portfolio & Official Data: current governed Case analytics
- Evidence & Submission: current Case audit and validation downloads
- Analyst Workspace: reviewed-input local/private mode enabled only by `TRADEGUARD_ENABLE_PRIVATE_WORKSPACE=true`

## Connected context

Portfolio and evidence modes reuse the active governed run and package. If a private reviewed Package has been executed, its Case becomes the active context; otherwise the selected public synthetic scenario remains active.

## Public safety

The public deployment keeps upload and Live AI surfaces disabled by default. The private workspace must be explicitly enabled in a local or access-controlled environment.

## Compatibility

Legacy app files remain for regression and developer compatibility, but documentation and submission instructions use only:

```powershell
python -m streamlit run streamlit_app.py
```
