"""Blind rubric judging.

The judge model never sees which model produced an answer. Each answer
is judged alone (no pairwise comparison) against a rubric whose
dimensions carry anchored descriptions of what 1, 3, and 5 look like.
For skill D the judge also maps identified risks to the hidden planted
risk list, and recall is then computed by code, not by the judge.
"""

import json

from scorers import extract_json

RUBRICS = {
    "B": {
        "dimensions": {
            "mece_structure": {
                "1": "Components overlap heavily or leave obvious gaps, no coherent hierarchy.",
                "3": "Mostly distinct components with minor overlaps or gaps, a usable two level structure.",
                "5": "Components are mutually exclusive and collectively exhaustive with a clean hierarchy.",
            },
            "estimate_quality": {
                "1": "Estimates missing, uniform, or clearly arbitrary, no total.",
                "3": "Estimates present at subtask level and roughly plausible, total stated.",
                "5": "Estimates plausible and differentiated by task size, total consistent with the parts.",
            },
            "assumptions": {
                "1": "No assumptions stated, or assumptions that contradict the request.",
                "3": "A few relevant assumptions stated.",
                "5": "Assumptions are specific, relevant, and clearly tied to the estimates they affect.",
            },
        }
    },
    "C": {
        "dimensions": {
            "justification_quality": {
                "1": "Justification missing, circular, or contradicts the numbers.",
                "3": "Justification restates the RICE result correctly in plain terms.",
                "5": "Justification is accurate, concise, and notes the trade off that drives the ranking.",
            }
        }
    },
    "D": {
        "dimensions": {
            "mitigation_quality": {
                "1": "Mitigations missing, generic (such as monitor closely), or impractical.",
                "3": "Mitigations mostly concrete and matched to the right risks.",
                "5": "Every mitigation is specific, actionable, and proportionate to its risk.",
            },
            "clarity": {
                "1": "Disorganized, hard to follow, or ignores the required format.",
                "3": "Follows the format, readable, some redundancy.",
                "5": "Crisp one sentence risk and mitigation statements, no filler.",
            },
        }
    },
    "E": {
        "dimensions": {
            "accuracy": {
                "1": "Misstates several facts from the notes.",
                "3": "Facts broadly correct with minor imprecision.",
                "5": "Every statement traceable to the notes with no distortion.",
            },
            "completeness": {
                "1": "Omits most of the material points including blockers or decisions.",
                "3": "Covers most material points, one or two omissions.",
                "5": "All material points covered, including the decision the audience must make.",
            },
            "audience_fit": {
                "1": "Wrong register entirely, such as raw engineering jargon for an executive.",
                "3": "Mostly appropriate tone and level of detail for the stated audience.",
                "5": "Pitched exactly at the stated audience, leads with what they care about.",
            },
            "clarity": {
                "1": "Rambling, unstructured, or ignores the required sections.",
                "3": "Follows the sections and is readable.",
                "5": "Scannable, concise, well ordered within each section.",
            },
            "no_fabrication": {
                "1": "Contains invented facts or numbers not in the notes.",
                "3": "No inventions but some unsupported interpretation.",
                "5": "Nothing beyond what the notes support.",
            },
        }
    },
}


def _rubric_text(skill):
    lines = []
    for dim, anchors in RUBRICS[skill]["dimensions"].items():
        lines.append("Dimension: " + dim)
        for level in ("1", "3", "5"):
            lines.append("  Score %s: %s" % (level, anchors[level]))
    return "\n".join(lines)


def build_judge_prompt(skill, task_prompt, answer_text, key=None):
    """Build the blind judge prompt. The answer is labeled Response and
    carries no model identity."""
    parts = [
        "You are grading one anonymous response to a project management task.",
        "Score each rubric dimension as an integer 1 to 5 using the anchors. 2 and 4 are allowed for in between quality.",
        "",
        "## Task given to the respondent",
        task_prompt,
        "",
        "## Rubric",
        _rubric_text(skill),
    ]
    if skill == "D" and key:
        parts += [
            "",
            "## Hidden planted risk list (the respondent never saw this)",
            "\n".join("%s: %s" % (r["id"], r["risk"]) for r in key["planted_risks"]),
            "",
            "Also map the response's risks to this list. A planted risk counts as matched only if the response clearly describes the same underlying risk.",
        ]
    parts += [
        "",
        "## Response",
        answer_text,
        "",
        "## Output format",
        "Respond with a single JSON object and nothing else, no code fences:",
    ]
    schema = {"scores": {dim: 0 for dim in RUBRICS[skill]["dimensions"]}}
    if skill == "D" and key:
        schema["matched_planted_risks"] = ["R1"]
    parts.append(json.dumps(schema))
    return "\n".join(parts)


def judge_answer(client, judge_model, skill, task_prompt, answer_text, key=None):
    """Run one blind judge call. Returns a dict with per dimension scores
    on a 0 to 1 scale, plus recall for skill D. Returns judge_error on
    failure so the caller can record it."""
    if not answer_text:
        return {"judge_error": "empty answer, not judged"}
    prompt = build_judge_prompt(skill, task_prompt, answer_text, key)
    messages = [
        {"role": "system", "content": "You are a strict, consistent grader. Follow the output format exactly."},
        {"role": "user", "content": prompt},
    ]
    result = client.chat(judge_model["id"], judge_model["tier"], messages)
    if result["status"] != "ok":
        return {"judge_error": result.get("error", "judge call failed")}
    data = extract_json(result["content"])
    if not isinstance(data, dict) or "scores" not in data:
        return {"judge_error": "judge output did not parse", "judge_raw": result["content"]}
    dims = RUBRICS[skill]["dimensions"]
    scores = {}
    for dim in dims:
        try:
            val = int(data["scores"].get(dim))
        except (TypeError, ValueError):
            val = None
        scores[dim] = val if val is not None and 1 <= val <= 5 else None
    valid = [v for v in scores.values() if v is not None]
    out = {
        "dimension_scores": scores,
        "judge_score": round(sum((v - 1) / 4 for v in valid) / len(valid), 4) if valid else None,
    }
    if skill == "D" and key:
        planted_ids = {r["id"] for r in key["planted_risks"]}
        matched = [m for m in (data.get("matched_planted_risks") or []) if m in planted_ids]
        out["matched_planted_risks"] = sorted(set(matched))
        out["recall"] = round(len(set(matched)) / len(planted_ids), 4)
    return out
