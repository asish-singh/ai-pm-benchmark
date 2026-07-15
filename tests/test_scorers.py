"""Unit tests for the code scorers, run with python3 -m unittest
(or pytest) from the project root."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import scorers


def load_key(task_id):
    with open(os.path.join(ROOT, "tasks", "keys", task_id + ".json")) as f:
        return json.load(f)


class TestScoreA(unittest.TestCase):
    def test_perfect_answer_a1(self):
        key = load_key("A1")
        result = scorers.score_A(json.dumps(key), key)
        self.assertFalse(result["parse_error"])
        self.assertEqual(result["duration_correct"], 1)
        self.assertEqual(result["slack_fraction"], 1.0)
        self.assertEqual(result["critical_path_correct"], 1)
        self.assertEqual(result["code_score"], 1.0)

    def test_perfect_answer_a2(self):
        key = load_key("A2")
        result = scorers.score_A(json.dumps(key), key)
        self.assertEqual(result["code_score"], 1.0)

    def test_wrong_duration_and_partial_slack(self):
        key = load_key("A1")
        answer = {
            "critical_path": ["T1", "T2", "T4", "T6", "T7", "T8"],
            "project_duration_days": 21,
            "slack_days": {"T1": 0, "T2": 0, "T3": 2, "T4": 0, "T5": 1, "T6": 0, "T7": 0, "T8": 0},
        }
        result = scorers.score_A(json.dumps(answer), key)
        self.assertEqual(result["duration_correct"], 0)
        self.assertEqual(result["critical_path_correct"], 0)
        self.assertEqual(result["slack_fraction"], 0.75)

    def test_json_in_code_fence_still_parses(self):
        key = load_key("A1")
        text = "Here is my answer:\n```json\n" + json.dumps(key) + "\n```"
        result = scorers.score_A(text, key)
        self.assertEqual(result["code_score"], 1.0)

    def test_unparseable_scores_zero(self):
        key = load_key("A1")
        result = scorers.score_A("The critical path is T1 to T8.", key)
        self.assertTrue(result["parse_error"])
        self.assertEqual(result["code_score"], 0.0)

    def test_none_answer_scores_zero(self):
        key = load_key("A1")
        result = scorers.score_A(None, key)
        self.assertTrue(result["parse_error"])
        self.assertEqual(result["code_score"], 0.0)


class TestScoreC(unittest.TestCase):
    def test_perfect_answer_c1(self):
        key = load_key("C1")
        answer = {"scores": key["scores"], "ranking": key["ranking"], "top_justification": "x"}
        result = scorers.score_C(json.dumps(answer), key)
        self.assertEqual(result["score_fraction"], 1.0)
        self.assertEqual(result["ranking_fraction"], 1.0)
        self.assertEqual(result["code_score"], 1.0)

    def test_perfect_answer_c2(self):
        key = load_key("C2")
        answer = {"scores": key["scores"], "ranking": key["ranking"]}
        result = scorers.score_C(json.dumps(answer), key)
        self.assertEqual(result["code_score"], 1.0)

    def test_rounding_tolerated(self):
        key = load_key("C1")
        scores = dict(key["scores"])
        scores["F1"] = 1600.4  # within 1 percent
        answer = {"scores": scores, "ranking": key["ranking"]}
        result = scorers.score_C(json.dumps(answer), key)
        self.assertEqual(result["score_fraction"], 1.0)

    def test_one_adjacent_swap(self):
        key = load_key("C1")  # correct: F3 F5 F1 F2 F4, 10 pairs
        answer = {"scores": key["scores"], "ranking": ["F3", "F5", "F1", "F4", "F2"]}
        result = scorers.score_C(json.dumps(answer), key)
        self.assertEqual(result["ranking_fraction"], 0.9)

    def test_wrong_scores(self):
        key = load_key("C1")
        answer = {"scores": {k: 1.0 for k in key["scores"]}, "ranking": list(key["scores"])}
        result = scorers.score_C(json.dumps(answer), key)
        self.assertEqual(result["score_fraction"], 0.0)

    def test_unparseable_scores_zero(self):
        key = load_key("C1")
        result = scorers.score_C("F3 first, then F5.", key)
        self.assertTrue(result["parse_error"])
        self.assertEqual(result["code_score"], 0.0)


class TestScoreB(unittest.TestCase):
    def test_full_coverage(self):
        key = load_key("B1")
        text = ("submission form with star rating, photo upload, moderation queue, "
                "average rating display, backend API, testing, deployment, "
                "spam filtering, caching for performance")
        result = scorers.score_B_checklist(text, key)
        self.assertEqual(result["checklist_fraction"], 1.0)

    def test_partial_coverage(self):
        key = load_key("B1")
        result = scorers.score_B_checklist("build a form with a star rating", key)
        self.assertEqual(result["checklist_fraction"], 0.2)


class TestScoreE(unittest.TestCase):
    def test_clean_answer(self):
        key = load_key("E1")
        text = "Login rework done in 9 days. QA found 34 bugs, 6 critical. Budget at 61 percent."
        result = scorers.score_E_fabrication(text, key)
        self.assertEqual(result["fabricated_numbers"], [])
        self.assertEqual(result["code_score"], 1.0)

    def test_fabricated_number_detected(self):
        key = load_key("E1")
        text = "QA found 34 bugs. We expect launch in 45 days."
        result = scorers.score_E_fabrication(text, key)
        self.assertIn("45", result["fabricated_numbers"])
        self.assertLess(result["code_score"], 1.0)

    def test_thousands_separator_normalized(self):
        key = load_key("E2")
        result = scorers.score_E_fabrication("Crane repair quote is 14,500.", key)
        self.assertEqual(result["fabricated_numbers"], [])

    def test_no_numbers_is_grounded(self):
        key = load_key("E1")
        result = scorers.score_E_fabrication("All on track, no blockers.", key)
        self.assertEqual(result["code_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
