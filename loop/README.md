# loop: intent → spec → reviewed code, with any mix of models

A standalone dev loop. One model (the **author**, usually Claude Code) turns your intent into a spec. Other models review the spec, you approve it, the author builds it, and the other models review the code. The author fixes what's real, rejects what isn't (with reasons), and brings you anything ambiguous or odd. Each repo keeps its own context: config, specs and triage log.

```
dotfiles/loop/
  bin/init-loop      installs the loop into a repo (on PATH via dotfiles install.sh)
  core/              the engine: review.sh, the prompt, verdict schema + gate, /spec /build /review-loop /ship, templates
  tests/run.sh       the loop's own tests
```

## Add it to a repo

```bash
init-loop ~/Workspace/my-app --mode team      # your own repo: commit it
init-loop ~/Work/acme/widget                  # someone else's repo: local mode, nothing committed
```

| | team | local |
|---|---|---|
| Who gets it | everyone who clones | only you |
| Engine | pinned copy in `.agent-loop/core/` (`VERSION`) | this machine's `dotfiles/loop/core` |
| Files | committed; CLAUDE.md (and AGENTS.md/GEMINI.md if present) get a pointer section | hidden through `.git/info/exclude`; the team's files are untouched |
| Specs | `specs/` (or `.agent-loop/specs/` if `specs/` is taken) | `.agent-loop/specs/` |
| Claude settings | `.claude/settings.json` | `.claude/settings.local.json` |

`init-loop` detects the test command (make, npm/pnpm/yarn/bun, pytest via uv/poetry, go, cargo, rake) and the rule files (CLAUDE.md, AGENTS.md, CONTRIBUTING.md, Copilot instructions). It picks reviewers from your machine defaults, narrowed to what the active account profile allows. Re-running it is how you update: it refreshes the loop's own files (engine, commands, `LOOP.md`) and never overwrites the repo's (`config.sh`, `guard.sh`, `test.sh`, templates). Moving from local to team later is one re-run with `--mode team`.

## Reviewers

Set in the repo's `.agent-loop/config.sh` (`LOOP_REVIEWERS`, and optionally `LOOP_SPEC_REVIEWERS` for the spec phase):

| Name | Runs | Notes |
|---|---|---|
| `claude` | `claude -p`, shell/edit/web tools removed | Handy when the author is something else, or when Claude is the only approved model |
| `codex` | `codex exec --sandbox read-only --output-schema` | |
| `gemini` | `agy` in plan mode with `--json-schema` | agy has one machine-wide login |
| `local/<name>` | Ollama HTTP API | `<name>` is a name from `LOOP_LOCAL_MODELS` (`"qwen=qwen3.6:35b-a3b deepseek=deepseek-r1:32b"`, machine defaults or repo config) or an Ollama tag itself (`local/deepseek-r1:32b`). Free. Local reviewers run one at a time, alongside the cloud ones. No tools: they grade from what's in the prompt. `local/*` in an allow-list means every local model |
| anything else | `LOOP_CMD_<name>='…'` | A command that reads the prompt on stdin and prints the JSON verdict. This is how a company's own model gets in (an internal CLI, a gateway behind `curl`, …) |

## Accounts

A repo can be tied to an account profile (`init-loop --profile`, by default the active one). Reviews then refuse to run, and send nothing, unless:
- that profile is active, and
- every reviewer is in the repo's `LOOP_ALLOWED_REVIEWERS` (the team's approved models) and in the profile's `LOOP_PROFILE_REVIEWERS`.

Profiles come from dotfiles (`loop-profile`), and direnv switches them per folder.

## The gate

A round passes only when the tests pass and each reviewer, on its own, approves, reports no blocker or major finding, and grades every acceptance criterion `met`. Exit codes: `0` pass · `1` changes · `2` reviewer error · `3` refused (guard or accounts).

## Changing the loop

Edit `core/`, run `bash loop/tests/run.sh`, commit dotfiles. Local-mode repos pick the change up immediately. Team-mode repos keep their pinned copy until you re-run `init-loop` there.
