# Security Policy

## Supported scope

Security reports are accepted for the current public repository and its latest default-branch release state. This competition prototype is not a production banking service and should not process real customer information.

## Reporting a vulnerability

Do not open a public issue containing a credential, personal information, confidential document, exploit detail, or unredacted log.

Use GitHub private vulnerability reporting when it is available for this repository. Otherwise, contact the repository owner through a private channel linked from the GitHub profile and include only the minimum information required to reproduce the issue.

Please include:

- affected commit or version;
- affected file or component;
- reproduction steps using synthetic data;
- expected and observed behavior;
- impact and any known workaround.

## Accidental secret exposure

If a real credential was committed or shown in an Actions log:

1. revoke or rotate it immediately at the issuing provider;
2. remove it from the current repository state and affected logs where possible;
3. review provider access logs and permissions;
4. treat history rewriting as cleanup only—rotation is still required.

Deleting a key from the latest commit does not invalidate copies, forks, caches, or prior Git history.

## Public-data boundary

Reports and reproductions must use synthetic fixtures. Do not attach real contracts, invoices, L/C documents, financial statements, customer identifiers, or API credentials.
