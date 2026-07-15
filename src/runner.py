"""Daily benchmark run entry point.

Reads the queue in state/progress.json, takes today's slice plus any
carry over, calls each model, scores the answers, writes raw and score
records, updates state, and regenerates the reports. Hard per tier
budgets and 8 second pacing make it impossible to exceed the GitHub
Models rate limits, even on a manually retried day. Deterministic given
the state file, nothing is randomized.
"""

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report
import scorers
from gh_models import Budget, BudgetExhausted, GitHubModelsClient
from judge import judge_answer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "models.json")
STATE_PATH = os.path.join(ROOT, "state", "progress.json")
BUDGET_PATH = os.path.join(ROOT, "state", "budget.json")
TASKS_DIR = os.path.join(ROOT, "tasks")
KEYS_DIR = os.path.join(ROOT, "tasks", "keys")
RAW_DIR = os.path.join(ROOT, "results", "raw")
SCORES_DIR = os.path.join(ROOT, "results", "scores")

SYSTEM_PROMPT = (
    "You are assisting with project management analysis. "
    "Follow the output format exactly."
)

TASK_PAIRS = [["A1", "A2"], ["B1", "B2"], ["C1", "C2"], ["D1", "D2"], ["E1", "E2"]]
REPS = 3


def run_date():
    return os.environ.get("RUN_DATE") or datetime.date.today().isoformat()


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def parse_task_file(task_id):
    """Return (frontmatter dict, prompt body) for a task file."""
    with open(os.path.join(TASKS_DIR, task_id + ".md")) as f:
        text = f.read()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, match.group(2).strip()


def load_key(task_id):
    with open(os.path.join(KEYS_DIR, task_id + ".json")) as f:
        return json.load(f)


def build_queue(models):
    """Full ordered schedule: each day covers one task pair for all
    eight models at one rep, and the reps of a task land on different
    days (rep r of pair p runs on day (r-1)*5 + p)."""
    queue = []
    for rep in range(1, REPS + 1):
        for pair_index, pair in enumerate(TASK_PAIRS):
            day = (rep - 1) * len(TASK_PAIRS) + pair_index
            for task_id in pair:
                for model in models:
                    queue.append({
                        "task": task_id,
                        "model": model["id"],
                        "tier": model["tier"],
                        "rep": rep,
                        "day": day,
                        "status": "pending",
                    })
    return queue


def load_state(models):
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"next_day": 0, "queue": build_queue(models)}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def model_slug(model_id):
    return model_id.replace("/", "__")


def call_model_with_retry(client, item, prompt, output_format):
    """One answer call, plus one format retry for JSON tasks whose
    first reply does not parse. Returns (final_text, raw_calls)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    result = client.chat(item["model"], item["tier"], messages)
    calls = [result]
    text = result["content"]
    if output_format == "json" and result["status"] == "ok" and scorers.extract_json(text) is None:
        retry_messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "Your previous reply did not parse as JSON. Respond again with only the JSON object, no prose, no code fences."},
        ]
        retry = client.chat(item["model"], item["tier"], retry_messages)
        calls.append(retry)
        if retry["status"] == "ok" and scorers.extract_json(retry["content"]) is not None:
            text = retry["content"]
    return text, calls


def score_answer(client, judge_model, item, meta, prompt, key, answer_text):
    """Combine code scoring and blind judge scoring into one record."""
    skill = meta["skill"]
    components = {}
    judge_result = {}
    if skill == "A":
        components = scorers.score_A(answer_text, key)
        overall = components["code_score"]
    elif skill == "C":
        components = scorers.score_C(answer_text, key)
        judge_result = judge_answer(client, judge_model, "C", prompt, answer_text)
        js = judge_result.get("judge_score")
        overall = (components["code_score"] + js) / 2 if js is not None else components["code_score"]
    elif skill == "B":
        components = scorers.score_B_checklist(answer_text, key)
        judge_result = judge_answer(client, judge_model, "B", prompt, answer_text)
        js = judge_result.get("judge_score")
        overall = (components["code_score"] + js) / 2 if js is not None else components["code_score"]
    elif skill == "D":
        judge_result = judge_answer(client, judge_model, "D", prompt, answer_text, key)
        recall = judge_result.get("recall")
        js = judge_result.get("judge_score")
        parts = [v for v in (recall, js) if v is not None]
        overall = sum(parts) / len(parts) if parts else 0.0
        components = {"parse_error": answer_text is None, "recall": recall}
    elif skill == "E":
        components = scorers.score_E_fabrication(answer_text, key)
        judge_result = judge_answer(client, judge_model, "E", prompt, answer_text)
        js = judge_result.get("judge_score")
        overall = (components["code_score"] + js) / 2 if js is not None else components["code_score"]
    return {
        "task": item["task"],
        "task_version": int(meta.get("version", 1)),
        "skill": skill,
        "model": item["model"],
        "rep": item["rep"],
        "date": run_date(),
        "parse_error": bool(components.get("parse_error")),
        "components": components,
        "judge": judge_result,
        "overall": round(float(overall), 4),
    }


def save_raw(item, meta, calls, config, date):
    record = {
        "task": item["task"],
        "task_version": int(meta.get("version", 1)),
        "model": item["model"],
        "tier": item["tier"],
        "rep": item["rep"],
        "date": date,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "parameters": config["generation"],
        "calls": calls,
    }
    name = "%s_%s_%s_rep%d.json" % (date, item["task"], model_slug(item["model"]), item["rep"])
    with open(os.path.join(RAW_DIR, name), "w") as f:
        json.dump(record, f, indent=2)


def save_score(record):
    name = "%s_%s_%s_rep%d.json" % (
        record["date"], record["task"], model_slug(record["model"]), record["rep"])
    with open(os.path.join(SCORES_DIR, name), "w") as f:
        json.dump(record, f, indent=2)


def main():
    date = run_date()
    config = load_config()
    budgets = config["budgets"]
    budget = Budget(
        BUDGET_PATH, date,
        budgets["high_daily_requests"], budgets["low_daily_requests"],
        budgets["min_seconds_between_requests"],
    )
    client = GitHubModelsClient(
        budget,
        temperature=config["generation"]["temperature"],
        max_tokens=config["generation"]["max_tokens"],
    )
    judge_model = config["judge"]
    state = load_state(config["models"])
    max_day = max(q["day"] for q in state["queue"])

    eligible = [q for q in state["queue"] if q["status"] == "pending" and q["day"] <= state["next_day"]]
    print("Run date %s, day pointer %d, %d eligible task reps" % (date, state["next_day"], len(eligible)))

    stopped = False
    for item in eligible:
        meta, prompt = parse_task_file(item["task"])
        key = load_key(item["task"])
        try:
            answer_text, calls = call_model_with_retry(client, item, prompt, meta["output_format"])
            save_raw(item, meta, calls, config, date)
            record = score_answer(client, judge_model, item, meta, prompt, key, answer_text)
        except BudgetExhausted as exc:
            print("Stopping, %s. Unfinished work carries over." % exc)
            stopped = True
            break
        save_score(record)
        item["status"] = "done"
        save_state(state)
        print("Scored %s %s rep %d: %.3f" % (item["task"], item["model"], item["rep"], record["overall"]))

    if not stopped and state["next_day"] < max_day:
        state["next_day"] += 1
    save_state(state)

    report.generate_daily_report(date)
    report.update_readme_leaderboard()
    print("Done. Reports updated.")


if __name__ == "__main__":
    main()
