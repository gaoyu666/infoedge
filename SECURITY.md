# Security Policy

## Reporting a Vulnerability

Please do not open a public issue for secrets, vulnerabilities, or data-source abuse risks.

Report privately to the maintainer through GitHub profile contact information or another trusted private channel. Include:

- A concise description of the issue.
- Steps to reproduce.
- Impact and affected files or endpoints.
- Any suggested fix, if available.

## Secret Handling

This repository must not contain real credentials. Keep local values in untracked files such as:

- `.env`
- `.env.local`
- `backend/.env`

If a secret is accidentally committed, rotate it immediately and remove it from history before making the repository public.
