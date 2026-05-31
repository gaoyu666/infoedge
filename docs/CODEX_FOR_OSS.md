# Codex for OSS Application Note

This document summarizes why InfoEdge is a good fit for Codex for Open Source and how API credits would be used for real maintenance work.

## Maintainer Role

The repository is maintained by `gaoyu666`, the primary maintainer and repository owner. Maintenance work includes source registry updates, connector review, FastAPI endpoint quality, frontend usability, issue triage, CI upkeep, and release management.

## Why This Repository Matters

InfoEdge is an open-source intelligence workbench for trend discovery, data-source tracking, and opportunity scoring. It documents and organizes public, gated, third-party, and restricted source categories so contributors can discuss connector coverage and safe data-source usage in the open.

Current repository signals:

- MIT licensed public repository.
- React/Vite frontend and FastAPI backend.
- Source registry for roughly 150 data-source entries.
- Public roadmap, contribution guide, security policy, CI workflow, issues, release, and static demo.
- Architecture documentation and GitHub issue/PR templates for external contributors.
- Offline connector tests for source registration, payload normalization, and malformed payload handling.

## How Codex and API Credits Would Be Used

API credits would support maintenance automation, not private product usage:

- Review pull requests for connector safety, schema drift, and test coverage.
- Triage issues into data-source, backend, frontend, documentation, and security categories.
- Generate and validate connector payload fixtures.
- Assist release notes for source additions and breaking API changes.
- Analyze CI failures and suggest focused fixes.
- Improve security review around credentials, gated sources, and restricted platforms.

Human maintainers remain responsible for final review, merge, release, and data-source compliance decisions.

## Current Open Maintenance Work

- Document PostgreSQL and Redis local setup.
- Add connector health status and refresh metadata.
- Continue expanding connector normalization fixtures as new sources are added.
- Improve dashboard empty states and backend offline messaging.
- Add deployment and demo guidance.
