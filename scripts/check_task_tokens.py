"""CI guard: fail if any task prompt exceeds the token limit.

Token counts are approximated as characters divided by 3.5, a
conservative rule of thumb for English text."""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 6000

failed = False
for path in sorted(glob.glob(os.path.join(ROOT, "tasks", "*.md"))):
    with open(path) as f:
        text = f.read()
    approx_tokens = int(len(text) / 3.5)
    status = "ok" if approx_tokens <= LIMIT else "TOO LONG"
    print("%-40s ~%5d tokens  %s" % (os.path.basename(path), approx_tokens, status))
    if approx_tokens > LIMIT:
        failed = True

if failed:
    print("FAIL: at least one task prompt exceeds %d approximate tokens." % LIMIT)
    sys.exit(1)
print("All task prompts are within the %d token limit." % LIMIT)
