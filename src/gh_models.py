"""Client for the GitHub Models chat completions API.

Handles authentication, request pacing, per tier daily budgets, and
retries with exponential backoff. The budget object is shared between
the runner and the judge so the two can never jointly exceed the caps.
"""

import json
import os
import time

import requests

API_URL = "https://models.github.ai/inference/chat/completions"


class BudgetExhausted(Exception):
    """Raised when a tier has hit its hard daily request cap."""


class Budget:
    """Per tier daily request counters, persisted to a JSON file.

    Counters reset automatically when the stored date differs from
    today's run date, so a single file tracks every day.
    """

    def __init__(self, path, run_date, high_cap, low_cap, min_gap_seconds):
        self.path = path
        self.run_date = run_date
        self.caps = {"high": high_cap, "low": low_cap}
        self.min_gap_seconds = min_gap_seconds
        self.counts = {"high": 0, "low": 0}
        self._last_request_time = 0.0
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                data = json.load(f)
            if data.get("date") == self.run_date:
                self.counts = data.get("counts", {"high": 0, "low": 0})

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"date": self.run_date, "counts": self.counts}, f, indent=2)

    def remaining(self, tier):
        return self.caps[tier] - self.counts[tier]

    def check(self, tier):
        if self.counts[tier] >= self.caps[tier]:
            raise BudgetExhausted(
                "Daily budget reached for %s tier (%d requests)" % (tier, self.caps[tier])
            )

    def record_request(self, tier):
        self.check(tier)
        self.counts[tier] += 1
        self.save()

    def pace(self):
        """Sleep so that at least min_gap_seconds pass between requests."""
        elapsed = time.time() - self._last_request_time
        wait = self.min_gap_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.time()


class GitHubModelsClient:
    def __init__(self, budget, token=None, temperature=0, max_tokens=3500):
        self.budget = budget
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, model_id, tier, messages, max_tries=3):
        """Send one chat completion request. Returns the parsed response dict.

        Counts against the tier budget before sending, paces to the
        minimum gap, and backs off exponentially on 429 or 5xx.
        """
        self.budget.check(tier)
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        }
        last_error = None
        for attempt in range(max_tries):
            self.budget.pace()
            self.budget.record_request(tier)
            started = time.time()
            try:
                resp = requests.post(API_URL, headers=headers, json=body, timeout=180)
            except requests.RequestException as exc:
                last_error = str(exc)
                time.sleep(2 ** attempt * 5)
                continue
            latency = time.time() - started
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "usage": data.get("usage", {}),
                    "latency_seconds": round(latency, 2),
                    "status": "ok",
                }
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = "HTTP %d: %s" % (resp.status_code, resp.text[:300])
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(int(retry_after))
                else:
                    time.sleep(2 ** attempt * 10)
                continue
            # Client errors other than 429 will not improve with retries.
            return {
                "content": None,
                "usage": {},
                "latency_seconds": round(latency, 2),
                "status": "error",
                "error": "HTTP %d: %s" % (resp.status_code, resp.text[:300]),
            }
        return {
            "content": None,
            "usage": {},
            "latency_seconds": None,
            "status": "error",
            "error": "gave up after %d tries: %s" % (max_tries, last_error),
        }
