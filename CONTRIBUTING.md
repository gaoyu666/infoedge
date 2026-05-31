# Contributing to InfoEdge

Thanks for taking the time to contribute.

## Development Workflow

1. Fork or clone the repository.
2. Create a feature branch from `main`.
3. Make a focused change.
4. Run the relevant checks.
5. Open a pull request with a clear summary and test notes.

## Recommended Checks

Frontend build:

```bash
npm run build
```

Backend tests:

```bash
cd backend
python -m unittest tests.test_source_expansion -v
```

API acceptance scripts:

```bash
npm run accept:opportunity-actions:api
npm run accept:buttons:api
```

## Source and Data Rules

- Prefer public, documented, and authorized data sources.
- Do not add credentials, cookies, session tokens, private datasets, or paid-source dumps to the repository.
- Mark gated sources as `needs_config` until an authorized connector and clear setup instructions exist.
- Avoid adding scrapers for restricted platforms unless the usage is clearly permitted.

## Pull Request Notes

Please include:

- What changed.
- Why the change is useful.
- Screenshots for UI changes.
- The commands you ran to verify it.
