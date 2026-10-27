# How JD works with Claude Code, in every repo

Managed in `~/Workspace/dotfiles/claude/CLAUDE.md` and linked to `~/.claude/CLAUDE.md`. A repo's own CLAUDE.md wins where they disagree.

## Intent → spec → reviewed code
- If the repo has `.agent-loop/`, anything that changes behaviour goes through the loop: `/spec` → JD approves → `/build` → `/review-loop` → `/ship`. Read `.agent-loop/LOOP.md` first; `.agent-loop/config.sh` says who reviews and where specs live. (In local mode the loop's files are hidden from git on purpose: never commit them.)
- If it doesn't, suggest `init-loop` for anything substantial. Either way, anything bigger than a small fix still starts as a short written spec before code: why, in scope / out of scope, acceptance criteria that each say how they're verified, open questions. Get JD's OK on it first.
- Put only what JD agreed into scope and the acceptance criteria. Anything you inferred goes under Open questions.
- Reviewers (other models) can be wrong. Decide every finding on its merits: fix, reject with a concrete reason, or ask JD. Agreeing by default is a failure.
- Never weaken a test, a guard or an acceptance criterion to get a pass.

## When to stop and ask JD
- The spec is silent or ambiguous on something that changes what gets built.
- Reviewers disagree on something the spec doesn't settle.
- Something looks off: surprising data, a dependency or tool behaving unexpectedly, or the change growing well past the spec.
Batch the questions, and give a recommendation with each.

## This Mac
- Other model CLIs: `agy` (Gemini), `codex`, `grok` (if installed), and Ollama at `127.0.0.1:11434`. Run `ai-doctor` to see which are ready.
- Loop defaults (which model plays which role) live in `~/.config/agent-loop/defaults.sh`.
- Accounts follow the folder (`loop-profile` shows the active one). Never sign in, switch accounts, or change which models a repo may use on your own: if the loop refuses for accounts, show JD what it said.
