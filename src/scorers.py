"""Code based scoring for the objective and semi objective task components.

Skill A: scheduling. Duration exact match, slack fraction correct,
critical path exact sequence match.
Skill C: RICE. Score arithmetic within rounding tolerance, ranking
quality as the fraction of correctly ordered pairs (Kendall tau style).
Skill B: hidden checklist coverage via keyword matching.
Skill E: fabrication check, every number in the answer must appear in
the source notes.

A parse failure (after the runner's one retry) scores 0 on every code
component and is recorded as a parse error.
"""

import itertools
import json
import re


def extract_json(text):
    """Parse a JSON object from model output, tolerating code fences
    and surrounding prose. Returns None if nothing parses."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # Strip code fences.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except ValueError:
            pass
    # Last resort, first { to last }.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            pass
    return None


def parse_error_result(skill):
    components = {"parse_error": True}
    if skill == "A":
        components.update({"duration_correct": 0, "slack_fraction": 0.0, "critical_path_correct": 0})
    elif skill == "C":
        components.update({"score_fraction": 0.0, "ranking_fraction": 0.0})
    components["code_score"] = 0.0
    return components


def score_A(answer_text, key):
    """Score a scheduling answer against the key. Returns component dict
    with code_score on a 0 to 1 scale."""
    data = extract_json(answer_text)
    if not isinstance(data, dict):
        return parse_error_result("A")
    duration_correct = int(data.get("project_duration_days") == key["project_duration_days"])
    slack_answer = data.get("slack_days") or {}
    correct = 0
    for task, expected in key["slack_days"].items():
        try:
            if float(slack_answer.get(task)) == float(expected):
                correct += 1
        except (TypeError, ValueError):
            pass
    slack_fraction = correct / len(key["slack_days"])
    path = data.get("critical_path")
    critical_path_correct = int(path == key["critical_path"])
    code_score = (duration_correct + slack_fraction + critical_path_correct) / 3
    return {
        "parse_error": False,
        "duration_correct": duration_correct,
        "slack_fraction": round(slack_fraction, 4),
        "critical_path_correct": critical_path_correct,
        "code_score": round(code_score, 4),
    }


def _pairwise_ranking_fraction(answer_ranking, key_ranking):
    """Fraction of item pairs ordered the same way as the key.
    Missing items count every pair they appear in as wrong."""
    positions = {item: i for i, item in enumerate(answer_ranking or [])}
    pairs = list(itertools.combinations(key_ranking, 2))
    if not pairs:
        return 0.0
    correct = 0
    for earlier, later in pairs:
        if earlier in positions and later in positions and positions[earlier] < positions[later]:
            correct += 1
    return correct / len(pairs)


def score_C(answer_text, key, rel_tolerance=0.01):
    """Score a RICE answer. Arithmetic within 1 percent (covers rounding),
    ranking as fraction of correctly ordered pairs."""
    data = extract_json(answer_text)
    if not isinstance(data, dict):
        return parse_error_result("C")
    scores_answer = data.get("scores") or {}
    correct = 0
    for item, expected in key["scores"].items():
        try:
            got = float(scores_answer.get(item))
        except (TypeError, ValueError):
            continue
        if abs(got - expected) <= rel_tolerance * abs(expected):
            correct += 1
    score_fraction = correct / len(key["scores"])
    ranking_fraction = _pairwise_ranking_fraction(data.get("ranking"), key["ranking"])
    code_score = (score_fraction + ranking_fraction) / 2
    return {
        "parse_error": False,
        "score_fraction": round(score_fraction, 4),
        "ranking_fraction": round(ranking_fraction, 4),
        "code_score": round(code_score, 4),
    }


def score_B_checklist(answer_text, key):
    """Coverage of the hidden checklist. An item counts as covered when
    any of its keywords appears in the answer, case insensitive."""
    text = (answer_text or "").lower()
    hits = []
    for entry in key["checklist"]:
        covered = any(kw.lower() in text for kw in entry["keywords"])
        hits.append({"item": entry["item"], "covered": covered})
    fraction = sum(1 for h in hits if h["covered"]) / len(hits)
    return {
        "parse_error": answer_text is None,
        "checklist_hits": hits,
        "checklist_fraction": round(fraction, 4),
        "code_score": round(fraction, 4),
    }


_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*")


def _normalize_number(raw):
    cleaned = raw.replace(",", "").rstrip(".")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned


def score_E_fabrication(answer_text, key):
    """Every number in the answer must appear in the source notes.
    Score is the fraction of numbers that are grounded, 1.0 when the
    answer contains no numbers at all."""
    if answer_text is None:
        return {"parse_error": True, "fabricated_numbers": [], "fabrication_free": 0.0, "code_score": 0.0}
    allowed = {_normalize_number(n) for n in key["allowed_numbers"]}
    found = [_normalize_number(m) for m in _NUMBER_RE.findall(answer_text)]
    fabricated = sorted({n for n in found if n not in allowed})
    grounded = 1.0 if not found else (len(found) - sum(1 for n in found if n not in allowed)) / len(found)
    return {
        "parse_error": False,
        "fabricated_numbers": fabricated,
        "fabrication_free": round(grounded, 4),
        "code_score": round(grounded, 4),
    }
