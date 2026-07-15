# Methodology

This is the frozen protocol for the AI PM Benchmark. Any edit after data collection starts is a visible commit with a stated reason. Version 1.1, dated 15 July 2026.

## Research question

Which freely available AI model produces the most accurate and useful output across five core project management skill areas?

Secondary questions.

1. Do models differ more on objective skills (scheduling math) than on judgment skills (risk identification)?
2. Are results stable across repeated runs, or do models give inconsistent answers to identical tasks?
3. Do results change as providers update their models over the study period?

## Models under test

Eight models from GitHub Models across five providers, all in the free tier, pinned by exact ID in `config/models.json`. The IDs are recorded in every result file so a provider silently swapping a model version is detectable. At least two providers are represented in each rate limit tier. A model removed from the catalog mid study is marked discontinued in results rather than deleted.

OpenAI reasoning models are excluded because they have no free tier allowance. DeepSeek R1 and xAI Grok 3 are excluded because their daily caps are too tight for this battery.

The judge model is openai/gpt-4.1. It is also a model under test, which is a stated limitation, so objective code scored results are always reported separately and the headline finding never rests on judge scores alone.

## Task battery

The pilot battery is 10 tasks, 2 per skill area. Expansion to 30 tasks (6 per area) is planned before cycle 1 formally starts. Every task is a fixed, versioned markdown file in `tasks/` with a machine readable header (id, version, skill, scoring type, output format). Tasks never change after the study starts, corrections create a new task version and old results are kept but flagged. Answer keys live in `tasks/keys/` and are never sent to the models under test.

### Skill areas and scoring

**A. Scheduling and critical path (objective, scored by code).** Given a task list with durations and dependencies, compute the critical path, project duration, and slack per task. Keys were verified with an independent critical path implementation. Score combines exact duration match, fraction of correct slack values, and critical path match.

**B. Estimation and breakdown (semi objective).** Turn a feature request into a work breakdown structure with estimates. Scored by a hidden coverage checklist checked in code, plus a rubric judge for structure quality, estimate quality, and assumptions.

**C. Prioritization (objective math, subjective inputs held fixed).** Given a backlog with fixed reach, impact, confidence, and effort numbers, produce RICE scores and a ranking. Code checks arithmetic within a 1 percent rounding tolerance and ranking quality as the fraction of correctly ordered pairs. The judge scores justification quality.

**D. Risk identification (subjective, judge scored).** Given a project brief seeded with 8 planted risks hidden from the model, identify risks and mitigations. The judge maps the model's risks to the planted list, then code computes recall. The judge also scores mitigation quality and clarity.

**E. Stakeholder communication (subjective, judge scored).** Turn messy meeting notes into a status update for a named audience. Judged on accuracy, completeness, audience fit, clarity, and no fabrication. Fabrication is also checked by code, every number in the output must appear in the source notes.

### Task size constraint

Every prompt must fit in 8,000 input tokens and expect under 4,000 output tokens. CI enforces a conservative approximate limit (characters divided by 3.5, capped at 6,000) on every push.

## Experimental design

- **Repetitions.** Each model answers each task 3 times, on different days, to measure consistency.
- **Determinism.** temperature 0, parameters echoed into every result record.
- **Prompting.** One shared system prompt and identical user prompts across models, no model specific tuning. This measures out of the box competence.
- **Output format.** Tasks require structured output (JSON or fixed markdown sections). A parse failure after one retry scores zero on code checked components and is recorded as a parse error, format compliance is itself a PM relevant skill.
- **Cycles.** After a full cycle completes, a new cycle begins with the same tasks, giving the longitudinal series for secondary question 3.

## Daily schedule and rate limit budget

One GitHub Actions job runs daily at 02:30 UTC. Each day covers 2 tasks for all 8 models at 1 repetition, 16 answer calls, plus judge calls and a small retry allowance. A hard stop counter caps the run at 40 high tier and 60 low tier requests per day, well under the documented free tier limits of 50 and 150. Requests are sequential with a minimum 8 second gap and exponential backoff on rate limit responses. Unfinished work carries over to the next day through a state file committed to the repository, so a run can never exceed limits even if retried by hand.

At the pilot size, 10 tasks by 3 repetitions is 30 task reps per model, 15 run days. At the full 30 task battery, a cycle takes 45 run days, about 6.5 calendar weeks allowing for failed days.

## Judge protocol and bias controls

1. **Blinding.** The judge never sees which model produced an answer. Answers are relabeled Response before judging.
2. **No pairwise comparison.** Each answer is scored alone against the rubric, eliminating position bias.
3. **Rubric anchoring.** Every rubric dimension has written descriptions of what 1, 3, and 5 look like, included in the judge prompt.
4. **Self judging disclosure.** The judge shares a provider with two models under test. This is flagged here and in the writeup, and code scored results are always reported separately.
5. **Judge stability check.** Once per cycle, 15 randomly sampled answers are re judged, and judge agreement within 1 point per dimension is reported as a quality metric.

## Data, analysis, and reporting

Every model call produces one JSON record in `results/raw/` with task id and version, model id, repetition number, timestamp, parameters, full response, latency, and token counts. Scores land in `results/scores/`. Everything is committed by the Action, the repository is the database and the audit trail.

Metrics.

- Per skill area, mean score per model, with 95 percent bootstrap confidence intervals across tasks and repetitions once samples allow.
- Overall, unweighted mean of the five skill area means, trivially recomputable from raw data.
- Consistency, standard deviation across the 3 repetitions of each task, per model.
- Format compliance rate per model.

Every run commits a dated findings report to `reports/daily/` with that day's tasks, each model's score, notable failures, and the running tally, all explicitly labeled preliminary. The README leaderboard shows running scores from day one but carries a preliminary label per model until that model has at least 30 scored task reps. Daily reports never claim an overall winner, only the frozen end of cycle writeup does.

## Limitations stated up front

Free tier models only (no Claude, no Gemini, no paid frontier models), an LLM judge for subjective tasks with the judge also under test, tasks authored with AI assistance, a single prompt style, English only, and a pilot battery of 10 tasks pending expansion to 30.
