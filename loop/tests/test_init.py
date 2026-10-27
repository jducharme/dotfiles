#!/usr/bin/env python3
"""Tests for init-loop and for the review.sh paths it sets up: both install modes, re-runs,
detection, the account check, Claude and custom-command reviewers. No real model is called:
fake `agy`, `claude` and custom commands stand in for them.

Run:  python3 loop/tests/test_init.py   (or bash loop/tests/run.sh for everything)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

LOOP_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(LOOP_HOME, "bin", "init-loop")
GIT = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]

VERDICT = {"verdict": "approve", "summary": "fake reviewer",
           "acceptance_criteria": [{"id": "AC-1", "status": "met", "evidence": "spec.md:1"}],
           "findings": [], "missing_tests": []}
SPEC = "# Spec 001: test\n\nstatus: ready\n\n- **AC-1**: something observable\n  - verify: n/a\n"

FAKE_AGY = """#!/usr/bin/env bash
[ "${1:-}" = "--version" ] && { echo "fake-agy"; exit 0; }
echo called >> "$FAKE_CALLS/agy"
printf '%s' '""" + json.dumps({"status": "SUCCESS", "response": json.dumps(VERDICT)}) + """'
"""
FAKE_CLAUDE = """#!/usr/bin/env bash
[ "${1:-}" = "--version" ] && { echo "fake-claude"; exit 0; }
echo "$*" >> "$FAKE_CALLS/claude"
cat > /dev/null
printf '%s' '""" + json.dumps({"type": "result", "subtype": "success", "is_error": False,
                               "result": json.dumps(VERDICT)}) + """'
"""


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="agent-loop-init-")
        self.home = os.path.join(self.tmp, "home")
        self.calls = os.path.join(self.tmp, "calls")
        self.bin = os.path.join(self.tmp, "bin")
        for d in (self.home, self.calls, self.bin):
            os.makedirs(d)
        for name, body in (("agy", FAKE_AGY), ("claude", FAKE_CLAUDE)):
            write(os.path.join(self.bin, name), body)
            os.chmod(os.path.join(self.bin, name), 0o755)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        write(os.path.join(self.repo, "README.md"), "# a repo\n")
        self.commit("initial")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update({"HOME": self.home, "PATH": self.bin + os.pathsep + env.get("PATH", ""), "FAKE_CALLS": self.calls})
        env.update(extra)
        return env

    def commit(self, msg):
        subprocess.run(GIT + ["-C", self.repo, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.repo, "commit", "-q", "--allow-empty", "-m", msg], check=True)

    def init(self, *args, check=True, **env):
        p = subprocess.run(["bash", INIT, self.repo] + list(args), capture_output=True, text=True, env=self.env(**env))
        if check:
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p

    def status(self):
        return subprocess.run(["git", "-C", self.repo, "status", "--porcelain"], capture_output=True, text=True).stdout

    def path(self, *p):
        return os.path.join(self.repo, *p)

    def review(self, spec_dir, *args, **env):
        return subprocess.run(["bash", ".agent-loop/review.sh", spec_dir, "--phase", "spec"] + list(args),
                              cwd=self.repo, capture_output=True, text=True, env=self.env(**env), timeout=120)

    def called(self, name):
        return os.path.exists(os.path.join(self.calls, name))


class LocalMode(Base):
    def test_local_leaves_git_clean_and_hides_everything(self):
        self.init("--mode", "local", "--reviewers", "gemini")
        self.assertEqual(self.status(), "", "local mode must leave nothing to commit")
        for f in (".agent-loop/config.sh", ".agent-loop/guard.sh", ".agent-loop/test.sh", ".agent-loop/LOOP.md",
                  ".agent-loop/templates/spec.md", ".agent-loop/specs/README.md",
                  ".claude/commands/spec.md", ".claude/commands/review-loop.md", ".claude/settings.local.json"):
            self.assertTrue(os.path.exists(self.path(f)), f)
        self.assertFalse(os.path.exists(self.path(".agent-loop", "core")), "local mode doesn't copy the engine")
        self.assertFalse(os.path.exists(self.path("CLAUDE.md")), "local mode doesn't touch the team's files")
        self.assertIn('LOOP_CORE="%s/core"' % LOOP_HOME, read(self.path(".agent-loop", "local.sh")))

    def test_works_through_a_symlink_on_path(self):
        link = os.path.join(self.bin, "init-loop")
        os.symlink(INIT, link)   # what dotfiles install.sh does with ~/.local/bin/init-loop
        p = subprocess.run(["bash", link, self.repo, "--mode", "local", "--reviewers", "gemini"],
                           capture_output=True, text=True, env=self.env())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('LOOP_CORE="%s/core"' % os.path.realpath(LOOP_HOME), read(self.path(".agent-loop", "local.sh")))

    def test_rerun_is_idempotent(self):
        self.init("--mode", "local", "--reviewers", "gemini")
        exclude = read(self.path(".git", "info", "exclude"))
        config = read(self.path(".agent-loop", "config.sh"))
        self.init()  # mode comes from local.sh
        self.assertEqual(read(self.path(".git", "info", "exclude")), exclude)
        self.assertEqual(read(self.path(".agent-loop", "config.sh")), config)
        self.assertEqual(exclude.count("agent-loop:begin"), 1)

    def test_review_runs_from_this_machines_engine(self):
        self.init("--mode", "local", "--reviewers", "gemini")
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        p = self.review(".agent-loop/specs/001-test")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(self.called("agy"))
        self.assertEqual(self.status(), "", "a review in local mode leaves nothing to commit either")

    def test_local_refused_when_loop_is_committed(self):
        self.init("--mode", "team", "--reviewers", "gemini")
        self.commit("add loop")
        p = self.init("--mode", "local", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("--mode team", p.stderr)

    def test_switch_local_to_team_unhides(self):
        self.init("--mode", "local", "--reviewers", "gemini")
        self.init("--mode", "team", "--specs-dir", "specs")
        self.assertNotIn("agent-loop:begin", read(self.path(".git", "info", "exclude")))
        self.assertIn("?? .agent-loop/", self.status())   # visible to git again, ready to commit


class TeamMode(Base):
    def test_team_vendors_engine_and_points_instruction_files(self):
        write(self.path("CLAUDE.md"), "# Team rules\n\nUse tabs.\n")
        write(self.path("AGENTS.md"), "# Agents\n")
        write(self.path(".claude", "settings.json"), json.dumps({"model": "x", "permissions": {"allow": ["Bash(make:*)"]}}))
        self.init("--mode", "team", "--reviewers", "gemini")
        self.assertTrue(os.path.exists(self.path(".agent-loop", "core", "review.sh")))
        self.assertIn("agent-loop engine", read(self.path(".agent-loop", "core", "VERSION")))
        if os.path.exists(os.path.join(LOOP_HOME, "..", "LICENSE")):
            self.assertIn("Required Notice:", read(self.path(".agent-loop", "core", "LICENSE")))
        claude_md = read(self.path("CLAUDE.md"))
        self.assertIn("Use tabs.", claude_md)
        self.assertIn(".agent-loop/LOOP.md", claude_md)
        self.assertIn(".agent-loop/LOOP.md", read(self.path("AGENTS.md")))
        settings = json.loads(read(self.path(".claude", "settings.json")))
        self.assertEqual(settings["model"], "x")
        self.assertIn("Bash(make:*)", settings["permissions"]["allow"])
        self.assertIn("Bash(bash .agent-loop/review.sh:*)", settings["permissions"]["allow"])
        self.assertIn("Edit(./.agent-loop/guard.sh)", settings["permissions"]["deny"])
        gi = read(self.path(".gitignore"))
        self.assertIn(".agent-loop/local.sh", gi)
        self.assertIn(".agent-loop/.runs/", gi)
        self.assertTrue(os.path.exists(self.path("specs", "README.md")))

    def test_rerun_keeps_repo_files_and_refreshes_loop_files(self):
        self.init("--mode", "team", "--reviewers", "gemini")
        cfg = self.path(".agent-loop", "config.sh")
        write(cfg, read(cfg).replace('LOOP_REVIEWERS="gemini"', 'LOOP_REVIEWERS="gemini codex"'))
        write(self.path(".agent-loop", "core", "review.sh"), "tampered\n")
        self.init()
        self.assertIn('LOOP_REVIEWERS="gemini codex"', read(cfg))
        self.assertNotEqual(read(self.path(".agent-loop", "core", "review.sh")), "tampered\n")
        self.assertEqual(read(self.path("CLAUDE.md")).count("agent-loop:begin"), 1)

    def test_existing_command_of_the_same_name_is_kept(self):
        write(self.path(".claude", "commands", "spec.md"), "the team's own /spec\n")
        p = self.init("--mode", "team", "--reviewers", "gemini")
        self.assertEqual(read(self.path(".claude", "commands", "spec.md")), "the team's own /spec\n")
        self.assertIn("kept .claude/commands/spec.md", p.stdout)

    def test_specs_dir_moves_aside_when_specs_is_taken(self):
        write(self.path("specs", "openapi.yaml"), "openapi: 3.0.0\n")
        self.init("--mode", "team", "--reviewers", "gemini")
        self.assertIn('LOOP_SPECS_DIR=".agent-loop/specs"', read(self.path(".agent-loop", "config.sh")))


class Detection(Base):
    def test_pnpm(self):
        write(self.path("package.json"), json.dumps({"scripts": {"test": "vitest run"}}))
        write(self.path("pnpm-lock.yaml"), "")
        self.init("--mode", "local", "--reviewers", "gemini")
        self.assertIn("pnpm test", read(self.path(".agent-loop", "test.sh")))

    def test_npm_placeholder_script_is_not_a_test(self):
        write(self.path("package.json"), json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}))
        self.init("--mode", "local", "--reviewers", "gemini")
        p = subprocess.run(["bash", ".agent-loop/test.sh"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("NO TESTS CONFIGURED", p.stdout)

    def test_uv_python(self):
        write(self.path("pyproject.toml"), "[project]\nname='x'\n")
        write(self.path("uv.lock"), "")
        self.init("--mode", "local", "--reviewers", "gemini")
        self.assertIn("uv run pytest", read(self.path(".agent-loop", "test.sh")))

    def test_rules_files_found(self):
        write(self.path("AGENTS.md"), "# rules\n")
        write(self.path("CONTRIBUTING.md"), "# how\n")
        self.init("--mode", "local", "--reviewers", "gemini")
        self.assertIn("LOOP_RULES_FILES=( AGENTS.md CONTRIBUTING.md )", read(self.path(".agent-loop", "config.sh")))


class Accounts(Base):
    def setUp(self):
        super().setUp()
        write(os.path.join(self.home, ".config", "agent-loop", "defaults.sh"), 'LOOP_REVIEWERS="gemini codex claude"\n')

    def spec(self):
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        return ".agent-loop/specs/001-test"

    def test_defaults_narrowed_by_profile(self):
        self.init("--mode", "local", LOOP_ACTIVE_PROFILE="work", LOOP_PROFILE_REVIEWERS="claude")
        self.assertIn('LOOP_REVIEWERS="claude"', read(self.path(".agent-loop", "config.sh")))
        self.assertIn('LOOP_PROFILE="work"', read(self.path(".agent-loop", "local.sh")))

    def test_falls_back_to_the_profiles_reviewers(self):
        write(os.path.join(self.home, ".config", "agent-loop", "defaults.sh"), 'LOOP_REVIEWERS="gemini"\n')
        self.init("--mode", "local", LOOP_ACTIVE_PROFILE="work", LOOP_PROFILE_REVIEWERS="codex claude")
        self.assertIn('LOOP_REVIEWERS="codex claude"', read(self.path(".agent-loop", "config.sh")))

    def test_nothing_allowed_is_an_error(self):
        p = self.init("--mode", "local", "--allowed", "claude", check=False,
                      LOOP_ACTIVE_PROFILE="work", LOOP_PROFILE_REVIEWERS="codex")
        self.assertEqual(p.returncode, 2)
        self.assertIn("--reviewers", p.stderr)

    def test_wrong_profile_sends_nothing(self):
        self.init("--mode", "local", "--reviewers", "gemini", "--profile", "work")
        p = self.review(self.spec(), LOOP_ACTIVE_PROFILE="personal")
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn("'work' accounts", p.stderr)
        self.assertFalse(self.called("agy"))

    def test_right_profile_runs(self):
        self.init("--mode", "local", "--reviewers", "gemini", "--profile", "work")
        p = self.review(self.spec(), LOOP_ACTIVE_PROFILE="work")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(self.called("agy"))

    def test_profile_disallows_reviewer(self):
        self.init("--mode", "local", "--reviewers", "gemini", "--profile", "work")
        p = self.review(self.spec(), LOOP_ACTIVE_PROFILE="work", LOOP_PROFILE_REVIEWERS="claude")
        self.assertEqual(p.returncode, 3)
        self.assertFalse(self.called("agy"))

    def test_repo_allowed_list_blocks_override(self):
        self.init("--mode", "local", "--reviewers", "claude", "--allowed", "claude")
        p = self.review(self.spec(), LOOP_REVIEWERS="gemini")
        self.assertEqual(p.returncode, 3)
        self.assertIn("approved reviewer", p.stderr)
        self.assertFalse(self.called("agy"))


class Reviewers(Base):
    def spec(self):
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        return ".agent-loop/specs/001-test"

    def test_claude_reviewer_is_read_only_and_unwrapped(self):
        self.init("--mode", "local", "--reviewers", "claude")
        p = self.review(self.spec())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        args = read(os.path.join(self.calls, "claude"))
        self.assertIn("-p", args)
        self.assertIn("--disallowedTools Bash,Edit,Write", args)

    def test_custom_command_reviewer(self):
        self.init("--mode", "local", "--reviewers", "claude")
        cfg = self.path(".agent-loop", "config.sh")
        fake = os.path.join(self.tmp, "xyz-review")
        write(fake, "#!/usr/bin/env bash\ncat > \"$FAKE_CALLS/xyz-prompt\"\necho \"$LOOP_SCHEMA_FILE\" > \"$FAKE_CALLS/xyz-schema\"\n"
                    "cat <<'JSON'\n%s\nJSON\n" % json.dumps(VERDICT))
        os.chmod(fake, 0o755)
        write(cfg, read(cfg) + "\nLOOP_CMD_xyz='%s --stdin'\n" % fake)
        p = self.review(self.spec(), LOOP_REVIEWERS="xyz")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("AC-1", read(os.path.join(self.calls, "xyz-prompt")))
        self.assertTrue(read(os.path.join(self.calls, "xyz-schema")).strip().endswith("verdict.schema.json"))

    def test_unknown_reviewer_is_explained(self):
        self.init("--mode", "local", "--reviewers", "claude")
        p = self.review(self.spec(), LOOP_REVIEWERS="mystery")
        self.assertEqual(p.returncode, 2)
        self.assertIn("LOOP_CMD_mystery", p.stderr)

    def test_spec_reviewers_used_for_spec_phase(self):
        self.init("--mode", "local", "--reviewers", "gemini")
        cfg = self.path(".agent-loop", "config.sh")
        write(cfg, read(cfg).replace('LOOP_SPEC_REVIEWERS=""', 'LOOP_SPEC_REVIEWERS="claude"'))
        p = self.review(self.spec())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(self.called("claude"))
        self.assertFalse(self.called("agy"))


class LocalModel(Base):
    """The built-in `local` reviewer talks to Ollama over HTTP; a stub server plays Ollama."""
    def setUp(self):
        super().setUp()
        import http.server
        import threading
        seen = self.seen = []
        state = self.state = {"now": 0, "max": 0}
        lock = threading.Lock()

        class Ollama(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, body))
                with lock:
                    state["now"] += 1
                    state["max"] = max(state["max"], state["now"])
                time.sleep(0.5)   # long enough that two parallel requests would overlap
                with lock:
                    state["now"] -= 1
                out = json.dumps({"message": {"role": "assistant", "content": json.dumps(VERDICT)}}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(out)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Ollama)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def test_local_reviewer_posts_schema_and_model(self):
        self.init("--mode", "local", "--reviewers", "local")
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        p = self.review(".agent-loop/specs/001-test", LOOP_OLLAMA_URL=self.url, LOOP_LOCAL_MODEL="tiny:1b")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        path, body = self.seen[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["model"], "tiny:1b")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"]["required"][0], "verdict")
        self.assertIn("you have no tools", body["messages"][0]["content"])

    def test_ollama_down_is_a_reviewer_error(self):
        self.init("--mode", "local", "--reviewers", "local")
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        p = self.review(".agent-loop/specs/001-test", LOOP_OLLAMA_URL="http://127.0.0.1:9")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("ollama", (p.stdout + p.stderr).lower())

    def spec(self):
        write(self.path(".agent-loop", "specs", "001-test", "spec.md"), SPEC)
        return ".agent-loop/specs/001-test"

    def models_asked(self):
        return [body["model"] for _, body in self.seen]

    def test_named_models_from_the_machine_run_one_at_a_time(self):
        write(os.path.join(self.home, ".config", "agent-loop", "defaults.sh"),
              'LOOP_LOCAL_MODELS="fast=tiny:1b big=huge:70b"\nLOOP_OLLAMA_URL="%s"\n' % self.url)
        self.init("--mode", "local", "--reviewers", "local/fast local/big")
        p = self.review(self.spec())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(self.models_asked()), ["huge:70b", "tiny:1b"])
        self.assertEqual(self.state["max"], 1, "two local models must never run at the same time")
        reviews = os.listdir(self.path(".agent-loop", "specs", "001-test", "reviews"))
        self.assertIn("spec-round-1-local-fast.json", reviews)
        self.assertIn("spec-round-1-local-big.json", reviews)

    def test_an_ollama_tag_works_directly(self):
        self.init("--mode", "local", "--reviewers", "local/deepseek-r1:32b")
        p = self.review(self.spec(), LOOP_OLLAMA_URL=self.url)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.models_asked(), ["deepseek-r1:32b"])
        self.assertIn("local-deepseek-r1-32b", p.stdout)

    def test_repo_names_win_over_the_machines(self):
        write(os.path.join(self.home, ".config", "agent-loop", "defaults.sh"), 'LOOP_LOCAL_MODELS="fast=tiny:1b"\n')
        self.init("--mode", "local", "--reviewers", "local/fast")
        cfg = self.path(".agent-loop", "config.sh")
        write(cfg, read(cfg).replace('LOOP_LOCAL_MODELS=""', 'LOOP_LOCAL_MODELS="fast=tiny:3b"'))
        p = self.review(self.spec(), LOOP_OLLAMA_URL=self.url)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.models_asked(), ["tiny:3b"])

    def test_local_wildcard_in_a_profile(self):
        self.init("--mode", "local", "--reviewers", "local/tiny:1b", "--profile", "work")
        ok = self.review(self.spec(), LOOP_OLLAMA_URL=self.url, LOOP_ACTIVE_PROFILE="work",
                         LOOP_PROFILE_REVIEWERS="claude local/*")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        refused = self.review(self.spec(), LOOP_OLLAMA_URL=self.url, LOOP_ACTIVE_PROFILE="work",
                              LOOP_PROFILE_REVIEWERS="claude local/*", LOOP_REVIEWERS="gemini")
        self.assertEqual(refused.returncode, 3)
        self.assertFalse(self.called("agy"))

    def test_bad_local_name_is_explained(self):
        self.init("--mode", "local", "--reviewers", "local/fast")
        p = self.review(self.spec(), LOOP_REVIEWERS="local/a;b")
        self.assertEqual(p.returncode, 2)
        self.assertIn("local model", p.stderr)

    def test_finding_ids_name_the_local_model(self):
        sys.path.insert(0, os.path.join(LOOP_HOME, "core", "lib"))
        import verdict
        self.assertEqual(verdict.id_prefix("local-deepseek"), "L-DEEPSEEK-")
        self.assertEqual(verdict.id_prefix("gemini"), "G")
        self.assertEqual(verdict.id_prefix("xyz"), "XYZ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
