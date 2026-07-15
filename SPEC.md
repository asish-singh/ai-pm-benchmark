# AI PM Benchmark, Research Specification

**Working title:** Which AI model is best at project management work?
**Status:** Specification, v1.1, 15 July 2026 (eight model lineup, daily findings publishing)
**Author:** Asish Singh
**Cost:** Zero. Runs entirely on GitHub Actions (free on public repos) and GitHub Models (free tier).

## 1. Research question

Large language models are benchmarked heavily on coding, math, and general knowledge. There is no credible public benchmark for project management competence. This study measures and compares how well freely available AI models perform core PM tasks, tracked over time.

Primary question. Which model produces the most accurate and useful output across five core PM skill areas?

Secondary questions.
1. Do models differ more on objective skills (scheduling math) than on judgment skills (risk identification)?
2. Are results stable across repeated runs, or do models give inconsistent answers to identical tasks?
3. Do results change as providers update their models over the study period?

## 2. Models under test

Eight models from GitHub Models across five providers, all in the free tier. Exact model IDs are pinned in `config/models.json` and recorded in every result file, so a provider silently swapping a model version is detectable.

| Slot | Model (example ID) | Provider | Tier |
|---|---|---|---|
| M1 | openai/gpt-4.1 | OpenAI | High |
| M2 | openai/gpt-4o-mini | OpenAI | Low |
| M3 | meta/llama-4-maverick-17b-128e-instruct-fp8 | Meta | High |
| M4 | meta/llama-3.3-70b-instruct | Meta | High |
| M5 | mistral-ai/mistral-small-2503 | Mistral | Low |
| M6 | microsoft/phi-4 | Microsoft | Low |
| M7 | deepseek/deepseek-v3-0324 | DeepSeek | High |
| M8 | cohere/cohere-command-a | Cohere | High |

Excluded on purpose. OpenAI reasoning models (o1, o3, gpt-5 family) have no free tier allowance. DeepSeek-R1 and xAI Grok-3 are capped at roughly 8 to 15 requests per day with 4,000 input tokens, too tight for this battery.

The final lineup is confirmed against the GitHub Models catalog at build time (models come and go). Rule, at least two providers must be represented in each tier, and any model removed from the catalog mid-study is marked "discontinued" in results rather than deleted.

**Judge model:** the strongest available model NOT under test if possible; otherwise gpt-4o with the bias controls in section 6. The judge choice is a stated limitation in the writeup.

## 3. Task battery

30 tasks total, 6 per skill area. Every task is a fixed, versioned markdown file in `tasks/` with a machine readable header (id, skill, scoring type, answer key where applicable). Tasks never change after the study starts; corrections create a new task version and old results are kept but flagged.

### Skill areas and scoring

**A. Scheduling and critical path (objective, scored by code)**
Given a task list with durations and dependencies, compute the critical path, project duration, and slack per task. Answer keys are computed independently by a Python reference implementation. Score = exact match on duration (pass/fail) plus fraction of correct slack values.

**B. Estimation and breakdown (semi objective)**
Turn a one paragraph feature request into a work breakdown structure with estimates. Scored by rubric (coverage of required components from a hidden checklist, MECE structure, presence of estimates and assumptions). Checklist items are code checked where possible (does the WBS mention testing, deployment, etc.), rubric judge covers structure quality.

**C. Prioritization (objective math, subjective inputs held fixed)**
Given a backlog with fixed reach, impact, confidence, and effort numbers, produce RICE scores and a ranked list. Score = correctness of arithmetic and ranking (code checked), plus judge score on the justification quality.

**D. Risk identification (subjective, judge scored)**
Given a project brief seeded with 8 known planted risks (hidden from the model), identify risks and mitigations. Score = recall against the planted risk list (judge maps model answers to planted risks, then code computes recall), plus judge score for mitigation quality.

**E. Stakeholder communication (subjective, judge scored)**
Turn messy meeting notes into a status update for a named audience. Judge scores against a 5 point rubric per dimension, accuracy to the notes, completeness, audience fit, clarity, no fabrication. Fabrication is also spot checked by code (every number in the output must appear in the notes).

### Task size constraint

Every prompt must fit in 8,000 input tokens and expect under 4,000 output tokens (the free tier cap). Tasks are validated for token count in CI before being accepted into the battery.

## 4. Experimental design

- **Repetitions.** Each model answers each task 3 times, on different days, to measure consistency. Total answer calls per full cycle, 8 models x 30 tasks x 3 reps = 720.
- **Determinism.** temperature=0 and fixed seed where the API supports it. Actual parameters echoed into every result record.
- **Prompting.** One shared system prompt ("You are assisting with project management analysis. Follow the output format exactly.") and identical user prompts across models. No model specific tuning, this measures out of the box competence.
- **Output format.** Tasks require structured output (JSON or fixed markdown sections) so code scoring is possible. A parse failure after one retry scores zero on code checked components (that is itself a finding, format compliance is a PM relevant skill).
- **Cycles.** After a full cycle completes (about 5 to 6 weeks, see section 5), a new cycle begins with the same tasks, giving the longitudinal series for secondary question 3.

## 5. Daily schedule and rate limit budget

GitHub Models free tier limits (docs.github.com, retrieved 15 July 2026, "subject to change"):

| Tier | Req/min | Req/day | Tokens per request |
|---|---|---|---|
| Low | 15 | 150 | 8,000 in / 4,000 out |
| High | 10 | 50 | 8,000 in / 4,000 out |

The daily limit is treated conservatively as an aggregate budget per account per tier, not per model, since the docs are ambiguous.

**Daily run (one GitHub Actions job, scheduled 02:30 UTC):**

- 2 tasks per day x 8 models x 1 rep = 16 answer calls (10 high tier, 6 low tier)
- Judge calls (judge is gpt-4.1, high tier) for answers needing rubric scoring, up to 18 calls on a day when both tasks are subjective, typically about 10
- Retry allowance, up to 6 extra calls

Worst case daily total, about 32 high tier requests (64 percent of the 50 cap) and 8 low tier requests (5 percent of the 150 cap). A typical day uses roughly half that. A hard stop counter caps the run at 40 high tier and 60 low tier requests per day, so a violation is impossible even on a manually retried day.

**Pacing inside the run.** The runner sends requests sequentially with a minimum 8 second gap (comfortably under 10/min high tier), backs off exponentially on any 429 response, and hard stops after a per tier call counter reaches the daily budget, carrying unfinished work to the next day via a state file committed to the repo. A run can therefore never exceed limits even if retried by hand.

**Cycle math.** 30 tasks x 3 reps = 90 task-reps, at 2 per day = 45 run days per cycle, about 6.5 calendar weeks allowing for failed days.

## 6. Judge protocol and bias controls

Standard LLM as judge weaknesses are handled explicitly.

1. **Blinding.** The judge never sees which model produced an answer. Answers are relabeled "Response" before judging.
2. **No pairwise comparison.** Each answer is scored alone against the rubric, eliminating position bias.
3. **Rubric anchoring.** Every rubric dimension has written descriptions of what 1, 3, and 5 look like, included in the judge prompt.
4. **Self judging disclosure.** If the judge model shares a provider with a model under test, that is flagged in the results and the writeup, and objective (code scored) results are always reported separately so the headline finding never rests on judge scores alone.
5. **Judge stability check.** Once per cycle, 15 randomly sampled answers are re judged; judge agreement (within 1 point on each dimension) is reported as a quality metric.

## 7. Data, analysis, and reporting

**Storage.** Every model call produces one JSON record in `results/raw/` (task id and version, model id, rep number, timestamp, parameters, full response, latency, token counts). Scores land in `results/scores/`. Everything is committed by the Action, the repo is the database and the audit trail.

**Metrics.**
- Per skill area, mean score per model with 95 percent bootstrap confidence intervals across tasks and reps.
- Overall, unweighted mean of the five skill area means (weighting is disclosed and trivially recomputable from raw data).
- Consistency, standard deviation across the 3 reps of each task, reported per model.
- Format compliance rate per model.

**Daily findings publishing.** Every run commits a dated findings report to `reports/daily/YYYY-MM-DD.md` containing that day's tasks, each model's score, notable failures (parse errors, arithmetic mistakes, fabricated numbers), and the running tally. Daily reports are explicitly labeled preliminary.

**No premature conclusions rule.** The README leaderboard shows running scores from day one but carries a "preliminary" label per model until that model has at least 30 scored task-reps, after which the label drops and confidence intervals appear. Daily reports never claim an overall winner, only the frozen end of cycle writeup does.

**Outputs.**
1. Daily findings report, one per run, committed automatically.
2. Auto updated README leaderboard and per skill breakdown, regenerated by the Action after each run.
3. A methodology page (frozen before data collection starts, any later edit is a visible commit).
4. End of cycle writeup with findings, confidence intervals, limitations, all claims traceable to files in the repo.

**Limitations stated up front.** Free tier models only (no Claude, no Gemini, no paid frontier models), LLM judge for subjective tasks, tasks authored with AI assistance, single prompt style, English only.

## 8. Repository layout and automation

```
ai-pm-benchmark/
  tasks/               30 versioned task files + answer keys (keys in a folder excluded from prompts)
  config/models.json   pinned model IDs, tiers, budgets
  src/                 runner, scorers, judge, report generator (Python, stdlib + requests)
  results/raw/         one JSON per model call
  results/scores/      scored records
  reports/daily/       one findings report per run day
  state/progress.json  what runs next, carry over queue
  .github/workflows/
    daily.yml          scheduled daily run, uses models: read permission on GITHUB_TOKEN
    validate.yml       CI, token count checks on tasks, scorer unit tests
  README.md            auto generated leaderboard
  METHODOLOGY.md       frozen protocol
```

Authentication uses the built in `GITHUB_TOKEN` with `models: read` permission, no secrets, no keys, no cost. The workflow also has a manual trigger for catch up runs, protected by the same per tier budget counter so manual runs cannot breach limits either.

## 9. Timeline

| Week | Milestone |
|---|---|
| 1 | Repo, runner, scorers, 30 tasks written and validated, methodology frozen |
| 2 | Pilot week, 1 task per day, verify scoring and budgets on real responses |
| 3 to 9 | Cycle 1 data collection, fully automatic |
| 10 | Cycle 1 writeup published, cycle 2 begins automatically |
