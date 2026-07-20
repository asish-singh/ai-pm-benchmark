# AI PM Benchmark

Which AI model is best at project management work? Models are benchmarked heavily on coding, math, and general knowledge, but there is no credible public benchmark for project management competence. This study measures how well freely available AI models perform core PM tasks, tracked daily over time, with every claim traceable to raw result files committed in this repository.

## The lineup

Eight models from GitHub Models across five providers, all in the free tier. Exact IDs are pinned in `config/models.json` and recorded in every result file, so a silent model swap by a provider is detectable.

| Slot | Model | Provider | Tier |
|---|---|---|---|
| M1 | openai/gpt-4.1 | OpenAI | High |
| M2 | openai/gpt-4o-mini | OpenAI | Low |
| M3 | meta/llama-4-maverick-17b-128e-instruct-fp8 | Meta | High |
| M4 | meta/llama-3.3-70b-instruct | Meta | High |
| M5 | mistral-ai/mistral-small-2503 | Mistral | Low |
| M6 | microsoft/phi-4 | Microsoft | Low |
| M7 | deepseek/deepseek-v3-0324 | DeepSeek | High |
| M8 | cohere/cohere-command-a | Cohere | High |

## Leaderboard

<!-- LEADERBOARD:START -->
Scores are on a 0 to 1 scale. A model is marked preliminary until it has at least 30 scored task reps.

| Model | Overall | Scheduling | Estimation | Prioritization | Risk | Communication | Task reps | Status |
|---|---|---|---|---|---|---|---|---|
| openai/gpt-4.1 | 0.96 | 0.95 | 0.93 | 0.94 | 0.97 | 1.00 | 12 | preliminary |
| cohere/cohere-command-a | 0.91 | 0.80 | 0.91 | 0.90 | 0.94 | 0.99 | 12 | preliminary |
| meta/llama-4-maverick-17b-128e-instruct-fp8 | 0.84 | 0.59 | 0.78 | 1.00 | 0.88 | 0.97 | 12 | preliminary |
| microsoft/phi-4 | 0.82 | 0.40 | 0.85 | 0.97 | 0.91 | 0.97 | 12 | preliminary |
| meta/llama-3.3-70b-instruct | 0.77 | 0.40 | 0.80 | 0.74 | 0.94 | 0.96 | 12 | preliminary |
| mistral-ai/mistral-small-2503 | 0.77 | 0.59 | 0.80 | 0.58 | 0.88 | 1.00 | 12 | preliminary |
| openai/gpt-4o-mini | 0.75 | 0.50 | 0.82 | 0.56 | 0.91 | 0.96 | 12 | preliminary |
<!-- LEADERBOARD:END -->

## How it works

Every model answers the same fixed battery of project management tasks across five skill areas, scheduling and critical path, estimation and breakdown, prioritization with RICE, risk identification, and stakeholder communication. Each task is answered three times on different days to measure consistency. Objective tasks are scored by code against hand verified answer keys. Subjective tasks are scored by a blind LLM judge against anchored rubrics, with the judge never seeing which model wrote an answer. Full detail lives in [METHODOLOGY.md](METHODOLOGY.md).

A GitHub Actions job runs daily, calls each model through the GitHub Models API, scores the answers, and commits a dated findings report to `reports/daily/`. The repository is the database and the audit trail, raw responses in `results/raw/`, scored records in `results/scores/`.

## Zero cost, rate limit safe by construction

The study runs entirely on GitHub Actions and the GitHub Models free tier, no API keys, no spend. The runner paces requests at least 8 seconds apart, backs off on rate limit responses, and hard stops when a per tier daily counter reaches its cap (40 high tier and 60 low tier requests, well under the documented limits). Unfinished work carries over to the next day through a committed state file, so even a manually retried run cannot exceed the limits.

## Limitations

- Free tier models only, so no Claude, no Gemini, and no paid frontier models.
- Subjective skills use an LLM judge, and the judge (openai/gpt-4.1) is also a model under test, so objective code scored results are always reported separately.
- Tasks were authored with AI assistance, use a single prompt style, and are English only.
- The current battery is a 10 task pilot, expansion to 30 tasks is planned before cycle 1 formally starts.
- Daily numbers are preliminary. A model keeps a preliminary label until it has at least 30 scored task reps, and no overall winner is claimed before the end of cycle writeup.
