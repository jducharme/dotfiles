#!/usr/bin/env python3
"""Tests for the review.sh watchdog. No real reviewer is called: a fake `agy` stands in for it.

Each test builds a throwaway git repo, installs the loop in it with the real init-loop (team mode,
so the engine is copied in), puts a fake `agy` first on PATH and runs the real review.sh through the .agent-loop/ wrapper. The fake starts a child process (standing in for agy's language
server) so the tests also check that the watchdog stops the whole process tree.

Run:  python3 loop/tests/test_watchdog.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

LOOP_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # loop/

VERDICT = {
    "verdict": "approve", "summary": "fake reviewer",
    "acceptance_criteria": [{"id": "AC-1", "status": "met", "evidence": "spec.md:1"}],
    "findings": [], "missing_tests": [],
}
AGY_OUTPUT = json.dumps({"conversation_id": "fake", "status": "SUCCESS", "response": json.dumps(VERDICT)})

FAKE_AGY = r'''#!/usr/bin/env bash
[ "${1:-}" = "--version" ] && { echo "fake-agy 0.0"; exit 0; }
sleep 300 &                      # stands in for agy's language server
child=$!
echo "$child" > "$FAKE_PIDFILE"
case "$FAKE_AGY_MODE" in
  normal)            kill "$child"; printf '%s' "$FAKE_OUTPUT"; exit 0 ;;
  hang_after_result) printf '%s' "$FAKE_OUTPUT"; wait "$child" ;;
  hang_no_result)    wait "$child" ;;
esac
'''

SPEC = "# Spec 900: watchdog test\n\n- **AC-1**: the fake reviewer grades this\n  - verify: n/a\n"


def read(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie still answers kill(0); ask ps for its state
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout
    return bool(out.strip()) and not out.strip().startswith("Z")


class WatchdogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="agent-loop-watchdog-")
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write(".agent-loop/.runs/\n__pycache__/\n")
        os.makedirs(os.path.join(repo, "specs", "900-watchdog-test"))
        with open(os.path.join(repo, "specs", "900-watchdog-test", "spec.md"), "w") as fh:
            fh.write(SPEC)
        with open(os.path.join(repo, "specs", "900-watchdog-test", "log.md"), "w") as fh:
            fh.write("# Triage log: spec 900\n")
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir)
        with open(os.path.join(bin_dir, "agy"), "w") as fh:
            fh.write(FAKE_AGY)
        os.chmod(os.path.join(bin_dir, "agy"), 0o755)
        git = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env["HOME"] = self.tmp
        subprocess.run(["bash", os.path.join(LOOP_HOME, "bin", "init-loop"), repo, "--mode", "team",
                        "--reviewers", "gemini", "--test-cmd", "true"], check=True, capture_output=True, env=env)
        subprocess.run(git + ["-C", repo, "add", "-A"], check=True)
        subprocess.run(git + ["-C", repo, "commit", "-q", "-m", "fixture"], check=True)
        self.repo, self.bin_dir = repo, bin_dir
        self.pidfile = os.path.join(self.tmp, "child.pid")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_review(self, mode, **env_extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LOOP_", "WORKSPACE_CDR"))}
        env.update({
            "PATH": self.bin_dir + os.pathsep + env.get("PATH", ""),
            "LOOP_REVIEWERS": "gemini", "FAKE_AGY_MODE": mode,
            "FAKE_OUTPUT": AGY_OUTPUT, "FAKE_PIDFILE": self.pidfile,
        })
        env.update(env_extra)
        t0 = time.time()
        p = subprocess.run(["bash", ".agent-loop/review.sh", "specs/900-watchdog-test", "--phase", "spec"],
                           cwd=self.repo, env=env, capture_output=True, text=True, timeout=120)
        log_path = os.path.join(self.repo, ".agent-loop", ".runs", "900-watchdog-test", "spec-round-1", "gemini.log")
        log = read(log_path) or ""
        child = int(read(self.pidfile).strip()) if os.path.exists(self.pidfile) else None
        return p, time.time() - t0, log, child

    def test_normal_exit_untouched(self):
        p, secs, log, _ = self.run_review("normal", LOOP_CLI_GRACE="2", LOOP_CLI_HARD_TIMEOUT="30")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("watchdog", log)
        self.assertLess(secs, 30)

    def test_hang_after_result_is_stopped_and_result_kept(self):
        p, secs, log, child = self.run_review("hang_after_result", LOOP_CLI_GRACE="2", LOOP_CLI_HARD_TIMEOUT="60")
        self.assertEqual(p.returncode, 0, p.stderr)       # the fake approved; its verdict was used
        self.assertIn("stopped it and kept the result", log)
        self.assertLess(secs, 40)
        self.assertFalse(alive(child), "the fake language server survived the watchdog")
        summary = os.path.join(self.repo, "specs", "900-watchdog-test", "reviews", "spec-round-1-summary.md")
        self.assertTrue(os.path.exists(summary))

    def test_hang_without_result_hits_hard_limit(self):
        p, secs, log, child = self.run_review("hang_no_result", LOOP_CLI_GRACE="2", LOOP_CLI_HARD_TIMEOUT="4")
        self.assertEqual(p.returncode, 2, p.stderr)       # reviewer error, not a silent pass
        self.assertIn("without a complete result", log)
        self.assertIn("watchdog limit", p.stderr)
        self.assertLess(secs, 40)
        self.assertFalse(alive(child), "the fake language server survived the watchdog")

    def test_code_phase_with_bsd_head(self):
        """macOS head rejects `-c 0`; a code-phase round must still reach the reviewer"""
        with open(os.path.join(self.bin_dir, "head"), "w") as fh:
            fh.write('#!/usr/bin/env bash\nfor a in "$@"; do [ "$a" = "0" ] && [ "$prev" = "-c" ] && '
                     '{ echo "head: illegal byte count -- 0" >&2; exit 1; }; prev="$a"; done\n'
                     'PATH="${PATH#*:}" exec head "$@"\n')
        os.chmod(os.path.join(self.bin_dir, "head"), 0o755)
        git = ["git", "-C", self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=test",
               "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["switch", "-q", "-c", "spec/900-watchdog-test"], check=True)
        with open(os.path.join(self.repo, "change.py"), "w") as fh:
            fh.write("x = 1\n" * 200)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "change"], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LOOP_", "WORKSPACE_CDR"))}
        env.update({"PATH": self.bin_dir + os.pathsep + env.get("PATH", ""), "LOOP_REVIEWERS": "gemini",
                    "FAKE_AGY_MODE": "normal", "FAKE_OUTPUT": AGY_OUTPUT, "FAKE_PIDFILE": self.pidfile,
                    "LOOP_AGY_MAX_PROMPT": "4000"})
        p = subprocess.run(["bash", ".agent-loop/review.sh", "specs/900-watchdog-test", "--base", "main", "--no-tests"],
                           cwd=self.repo, env=env, capture_output=True, text=True, timeout=120)
        self.assertNotIn("illegal byte count", p.stderr)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_code_phase_saves_base_versions(self):
        """Reviewers can't run git: the merge-base version of each changed or deleted file is saved for them"""
        git = ["git", "-C", self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=test",
               "-c", "commit.gpgsign=false"]
        for name, body in (("legacy.py", "old = 1\n"), ("keep.py", "v = 1\n")):
            with open(os.path.join(self.repo, name), "w") as fh:
                fh.write(body)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "base files"], check=True)
        subprocess.run(git + ["switch", "-q", "-c", "spec/900-watchdog-test"], check=True)
        os.remove(os.path.join(self.repo, "legacy.py"))
        with open(os.path.join(self.repo, "keep.py"), "w") as fh:
            fh.write("v = 2\n")
        with open(os.path.join(self.repo, "new.py"), "w") as fh:
            fh.write("n = 1\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "change"], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LOOP_", "WORKSPACE_CDR"))}
        env.update({"PATH": self.bin_dir + os.pathsep + env.get("PATH", ""), "LOOP_REVIEWERS": "gemini",
                    "FAKE_AGY_MODE": "normal", "FAKE_OUTPUT": AGY_OUTPUT, "FAKE_PIDFILE": self.pidfile})
        p = subprocess.run(["bash", ".agent-loop/review.sh", "specs/900-watchdog-test", "--base", "main", "--no-tests"],
                           cwd=self.repo, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        run = os.path.join(self.repo, ".agent-loop", ".runs", "900-watchdog-test", "round-1")
        self.assertEqual(read(os.path.join(run, "base", "legacy.py")), "old = 1\n")   # deleted file
        self.assertEqual(read(os.path.join(run, "base", "keep.py")), "v = 1\n")       # modified file, old version
        self.assertFalse(os.path.exists(os.path.join(run, "base", "new.py")))         # new file: nothing to save
        prompt = read(os.path.join(run, "prompt-gemini.txt"))
        self.assertIn("You cannot run shell commands", prompt)
        self.assertIn(os.path.join(".agent-loop", ".runs", "900-watchdog-test", "round-1", "base"), prompt)

    def test_tests_never_see_review_runs(self):
        """test.sh runs before the base copies exist, and review output is never listed as repo files"""
        git = ["git", "-C", self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=test",
               "-c", "commit.gpgsign=false"]
        with open(os.path.join(self.repo, "keep.py"), "w") as fh:
            fh.write("v = 1\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "base file"], check=True)
        # A test command that fails if anything under .agent-loop/.runs/ is visible to it.
        cfg = os.path.join(self.repo, ".agent-loop", "config.sh")
        with open(cfg, "a") as fh:
            fh.write("\nLOOP_TEST_CMD='! git ls-files --others --exclude-standard | grep \"^\\.agent-loop/\\.runs/\"'\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "test cmd"], check=True)
        subprocess.run(git + ["switch", "-q", "-c", "spec/900-watchdog-test"], check=True)
        with open(os.path.join(self.repo, "keep.py"), "w") as fh:
            fh.write("v = 2\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "change"], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LOOP_", "WORKSPACE_CDR"))}
        env.update({"PATH": self.bin_dir + os.pathsep + env.get("PATH", ""), "LOOP_REVIEWERS": "gemini",
                    "FAKE_AGY_MODE": "normal", "FAKE_OUTPUT": AGY_OUTPUT, "FAKE_PIDFILE": self.pidfile})
        for rnd in (1, 2):   # round 2 runs with round 1's base copies already on disk
            p = subprocess.run(["bash", ".agent-loop/review.sh", "specs/900-watchdog-test", "--base", "main"],
                               cwd=self.repo, env=env, capture_output=True, text=True, timeout=120)
            run = os.path.join(self.repo, ".agent-loop", ".runs", "900-watchdog-test", "round-%d" % rnd)
            self.assertIn("tests exited 0", p.stderr, read(os.path.join(run, "tests.txt")))
            self.assertTrue(os.path.exists(os.path.join(run, "base", "keep.py")))

    def test_rejects_non_numeric_limits(self):
        p, _, _, _ = self.run_review("normal", LOOP_CLI_HARD_TIMEOUT="25m")
        self.assertEqual(p.returncode, 2)
        self.assertIn("whole seconds", p.stderr)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=2).result.wasSuccessful() else 1)
