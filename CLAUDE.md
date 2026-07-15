# Project: ai-pm-benchmark

A scientific benchmark comparing free AI models on project management tasks, running daily on GitHub Actions with GitHub Models.

## Status

- Started: 2026-07-15
- Current state: core system built, pilot battery of tasks in place, not yet published to GitHub

## Goal

A credible, fully reproducible public study answering "which AI model is best at project management work," with every claim traceable to committed raw results. Zero running cost. Full spec lives in `../ai-pm-benchmark-spec.md` and is mirrored in `METHODOLOGY.md`.

## How to run it

- Daily run (in CI): `.github/workflows/daily.yml`, scheduled, uses the built in GITHUB_TOKEN with models read permission.
- Local dry run of scorers and report generation: `python3 -m pytest tests/` and `python3 src/report.py`.
- Local live run needs a GitHub personal access token with models read scope in env var `GITHUB_TOKEN`: `python3 src/runner.py`.

## Notes for Claude

- Asish is non-technical: explain in plain language, choose sensible defaults, confirm before anything destructive.
- METHODOLOGY.md is frozen once data collection starts; changes after that must be visible, deliberate commits with a stated reason.
- Never raise the per tier daily call budgets in `config/models.json` without checking current GitHub Models rate limits first.
- Tasks in `tasks/` are versioned; never edit a task in place after data collection starts, add a new version.
- Commit working checkpoints as you go. Repo will be public; commit messages are for a public audience.
