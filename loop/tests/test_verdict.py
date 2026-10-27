#!/usr/bin/env python3
"""Tests for the agent-loop gate (verdict.py). Synthetic reviewer output only.

Run:  python3 loop/tests/test_verdict.py (or bash loop/tests/run.sh for everything)
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "lib"))
import verdict  # noqa: E402

SPEC = """# Spec
<!-- example: - **AC-9**: ignored because it's in a comment -->
- **AC-1**: first
  - verify: x
- **AC-2**: second
Prose that mentions AC-7 doesn't define it.
"""


def review(verdict_="approve", acs=(("AC-1", "met"), ("AC-2", "met")), findings=()):
    return {
        "verdict": verdict_, "summary": "s",
        "acceptance_criteria": [{"id": i, "status": st, "evidence": "e"} for i, st in acs],
        "findings": [{"severity": sev, "category": "correctness", "file": "a", "line": 1, "title": "t",
                      "detail": "", "suggested_fix": "", "acceptance_criterion": ""} for sev in findings],
        "missing_tests": [],
    }


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.spec = os.path.join(self.tmp, "spec.md")
        with open(self.spec, "w") as fh:
            fh.write(SPEC)
        self.run_dir = os.path.join(self.tmp, ".runs", "001-x", "round-1")
        self.reviews = os.path.join(self.tmp, "reviews")
        os.makedirs(self.run_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def merge(self, outputs, tests_exit=0, phase="code"):
        """outputs: {reviewer: (exit_code, raw_text)}"""
        for name, (code, raw) in outputs.items():
            with open(os.path.join(self.run_dir, name + ".exit"), "w") as fh:
                fh.write(str(code))
            with open(os.path.join(self.run_dir, name + ".out"), "w") as fh:
                fh.write(raw)
        argv = ["merge", "--phase", phase, "--round", "1", "--tag", "round-1", "--tests-exit", str(tests_exit),
                "--run-dir", self.run_dir, "--reviews-dir", self.reviews, "--spec", self.spec] + list(outputs)
        stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            return verdict.main(argv)
        finally:
            sys.stdout.close()
            sys.stdout = stdout

    def agy(self, r):
        return json.dumps({"status": "SUCCESS", "response": "ok", "structured_output": r})

    def both(self, g, c, **kw):
        return self.merge({"gemini": (0, self.agy(g)), "codex": (0, json.dumps(c))}, **kw)

    def test_spec_ac_ids_only_counts_definitions(self):
        self.assertEqual(verdict.spec_ac_ids(self.spec), ["AC-1", "AC-2"])

    def test_both_approve_passes(self):
        self.assertEqual(self.both(review(), review()), 0)

    def test_approve_with_major_finding_fails(self):
        self.assertEqual(self.both(review(findings=["major"]), review()), 1)

    def test_minor_findings_still_pass(self):
        self.assertEqual(self.both(review(findings=["minor", "nit"]), review()), 0)

    def test_partial_ac_fails(self):
        self.assertEqual(self.both(review(acs=(("AC-1", "met"), ("AC-2", "partial"))), review()), 1)

    def test_omitted_ac_fails(self):
        # GS1.3: a reviewer that skips AC-2 must not pass vacuously
        self.assertEqual(self.both(review(acs=(("AC-1", "met"),)), review()), 1)

    def test_failing_tests_fail_even_if_both_approve(self):
        self.assertEqual(self.both(review(), review(), tests_exit=1), 1)

    def test_request_changes_fails(self):
        self.assertEqual(self.both(review("request_changes"), review()), 1)

    def test_unusable_output_is_an_error_not_a_round(self):
        rc = self.merge({"gemini": (0, ""), "codex": (0, json.dumps(review()))})
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(os.path.join(self.reviews, "round-1-summary.md")))

    def test_agy_error_status_is_an_error(self):
        rc = self.merge({"gemini": (0, json.dumps({"status": "ERROR", "error": {"message": "quota"}})),
                         "codex": (0, json.dumps(review()))})
        self.assertEqual(rc, 2)

    def test_error_summary_quotes_the_cli_log(self):
        with open(os.path.join(self.run_dir, "codex.log"), "w") as fh:
            fh.write("starting\nERROR: unexpected status 401 Unauthorized\n")
        self.merge({"codex": (1, "")})
        with open(os.path.join(self.run_dir, "round-1-summary.md")) as fh:
            self.assertIn("401 Unauthorized", fh.read())

    def test_fenced_json_in_agy_response_is_accepted(self):
        raw = json.dumps({"status": "SUCCESS", "response": "```json\n" + json.dumps(review()) + "\n```"})
        self.assertEqual(self.merge({"gemini": (0, raw)}), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
