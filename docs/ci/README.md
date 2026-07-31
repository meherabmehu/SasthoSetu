# Continuous integration

`github-actions-ci.yml` is the project's CI pipeline: lint, test and a smoke
job that starts a real server and asserts the safety-critical endpoints.

To activate it, copy the file into place and push from an account or token
carrying the `workflow` scope:

```
mkdir -p .github/workflows
cp docs/ci/github-actions-ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml && git commit -m "Enable CI workflow" && git push
```

It lives here rather than under `.github/workflows` because GitHub rejects
pushes that add or modify workflow files unless the credential has that scope.

## What it checks

| Job | Purpose |
|---|---|
| `lint` | `ruff` across `backend`, `ml`, `scripts`, `tools` |
| `test` | Builds datasets, trains models, runs migrations, runs the suite |
| `smoke` | Boots the API and asserts triage, ML triage, surge, drug screening and FHIR |

The test job deliberately runs `ml/prepare_all.py` first. The AI layer once
shipped as code without the data it loads, and building the pipeline in CI is
what stops that recurring.
