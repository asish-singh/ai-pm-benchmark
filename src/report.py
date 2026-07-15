"""Report generation.

Writes the dated daily findings report and rewrites the README
leaderboard between its markers. The run date comes from the RUN_DATE
environment variable when set, otherwise the system date.
"""

import datetime
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES_DIR = os.path.join(ROOT, "results", "scores")
DAILY_DIR = os.path.join(ROOT, "reports", "daily")
README_PATH = os.path.join(ROOT, "README.md")

SKILLS = ["A", "B", "C", "D", "E"]
SKILL_NAMES = {
    "A": "Scheduling",
    "B": "Estimation",
    "C": "Prioritization",
    "D": "Risk",
    "E": "Communication",
}
PRELIMINARY_THRESHOLD = 30


def run_date():
    return os.environ.get("RUN_DATE") or datetime.date.today().isoformat()


def load_scores():
    records = []
    for path in sorted(glob.glob(os.path.join(SCORES_DIR, "*.json"))):
        with open(path) as f:
            records.append(json.load(f))
    return records


def mean(values):
    return sum(values) / len(values) if values else None


def fmt(value):
    return "%.2f" % value if value is not None else "-"


def model_summary(records):
    """Per model: task-rep count, per skill means, overall mean
    (unweighted mean of the skill means that have data)."""
    models = sorted({r["model"] for r in records})
    summary = {}
    for model in models:
        mine = [r for r in records if r["model"] == model]
        skill_means = {
            s: mean([r["overall"] for r in mine if r["skill"] == s]) for s in SKILLS
        }
        available = [v for v in skill_means.values() if v is not None]
        summary[model] = {
            "count": len(mine),
            "skill_means": skill_means,
            "overall": mean(available),
            "preliminary": len(mine) < PRELIMINARY_THRESHOLD,
            "parse_errors": sum(1 for r in mine if r.get("parse_error")),
        }
    return summary


def notable_failures(records):
    notes = []
    for r in records:
        if r.get("parse_error"):
            notes.append("%s on %s rep %d: output did not parse, code components scored 0." % (r["model"], r["task"], r["rep"]))
        comp = r.get("components", {})
        if r["skill"] == "A" and not r.get("parse_error") and comp.get("duration_correct") == 0:
            notes.append("%s on %s rep %d: wrong project duration." % (r["model"], r["task"], r["rep"]))
        if r["skill"] == "C" and comp.get("score_fraction", 1) is not None and comp.get("score_fraction") == 0 and not r.get("parse_error"):
            notes.append("%s on %s rep %d: every RICE score wrong." % (r["model"], r["task"], r["rep"]))
        if r["skill"] == "E" and comp.get("fabricated_numbers"):
            notes.append("%s on %s rep %d: numbers not in the notes: %s." % (r["model"], r["task"], r["rep"], ", ".join(comp["fabricated_numbers"])))
        if r.get("judge", {}).get("judge_error"):
            notes.append("%s on %s rep %d: judge scoring failed (%s)." % (r["model"], r["task"], r["rep"], r["judge"]["judge_error"]))
    return notes


def leaderboard_table(summary):
    header = ("| Model | Overall | " + " | ".join(SKILL_NAMES[s] for s in SKILLS)
              + " | Task reps | Status |")
    sep = "|---" * (len(SKILLS) + 4) + "|"
    rows = [header, sep]
    ordered = sorted(summary.items(), key=lambda kv: -(kv[1]["overall"] or 0))
    for model, s in ordered:
        rows.append("| %s | %s | %s | %d | %s |" % (
            model,
            fmt(s["overall"]),
            " | ".join(fmt(s["skill_means"][sk]) for sk in SKILLS),
            s["count"],
            "preliminary" if s["preliminary"] else "stable",
        ))
    return "\n".join(rows)


def generate_daily_report(date):
    records = load_scores()
    today = [r for r in records if r["date"] == date]
    lines = [
        "# Daily findings, %s" % date,
        "",
        "**These results are preliminary.** They come from a partial run of the full schedule and must not be read as a final ranking. No overall winner is claimed until the end of cycle writeup.",
        "",
    ]
    if not today:
        lines += ["No task reps were scored on this date.", ""]
    else:
        tasks = sorted({r["task"] for r in today})
        lines += ["## Tasks run", "", ", ".join(tasks), "", "## Scores", ""]
        lines.append("| Model | Task | Rep | Overall | Parse error |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(today, key=lambda r: (r["task"], -r["overall"])):
            lines.append("| %s | %s | %d | %s | %s |" % (
                r["model"], r["task"], r["rep"], fmt(r["overall"]),
                "yes" if r.get("parse_error") else "no"))
        failures = notable_failures(today)
        lines += ["", "## Notable failures", ""]
        lines += ["- " + n for n in failures] if failures else ["None recorded today."]
    lines += ["", "## Running tally (all runs so far, preliminary)", ""]
    summary = model_summary(records)
    lines.append(leaderboard_table(summary) if summary else "No scores recorded yet.")
    lines.append("")
    os.makedirs(DAILY_DIR, exist_ok=True)
    path = os.path.join(DAILY_DIR, "%s.md" % date)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def update_readme_leaderboard():
    records = load_scores()
    summary = model_summary(records)
    if summary:
        body = [
            "Scores are on a 0 to 1 scale. A model is marked preliminary until it has at least %d scored task reps." % PRELIMINARY_THRESHOLD,
            "",
            leaderboard_table(summary),
        ]
        content = "\n".join(body)
    else:
        content = "No results yet. The leaderboard appears here after the first daily run."
    with open(README_PATH) as f:
        readme = f.read()
    start_marker = "<!-- LEADERBOARD:START -->"
    end_marker = "<!-- LEADERBOARD:END -->"
    start = readme.index(start_marker) + len(start_marker)
    end = readme.index(end_marker)
    updated = readme[:start] + "\n" + content + "\n" + readme[end:]
    with open(README_PATH, "w") as f:
        f.write(updated)
    return README_PATH


if __name__ == "__main__":
    date = run_date()
    print("Wrote", generate_daily_report(date))
    print("Updated", update_readme_leaderboard())
