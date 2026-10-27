# The agent loop in this repo

<!-- agent-loop: managed by init-loop; `init-loop --update` replaces this file. Repo specifics go in config.sh. -->

Work that changes behaviour goes **intent → spec → reviewed spec → approval → build → reviewed code → PR**. One model (the author, usually Claude Code) writes the spec and the code. Other models review both, independently and read-only. The author decides on every finding, and the human approves the spec and settles anything the spec doesn't.

```
 human + author agree the intent
        │  /spec            → <specs>/NNN-slug/spec.md, reviewed by the other models (--phase spec)
        │  human approves   → status: ready
        │  /build           → branch spec/NNN-slug: code + a test per acceptance criterion
        │  /review-loop     → review.sh: guard → account check → tests → reviewers → merged verdict
        │                     CHANGES: triage every finding in log.md (fix / reject + reason / ask-human), re-run (≤ 3 rounds)
        ▼  /ship            → PR
```

**The spec is the contract.** Reviewers grade the code against it, acceptance criterion by acceptance criterion, and flag anything outside its scope as drift.

## Files

| Path | What | Committed? |
|---|---|---|
| `.agent-loop/config.sh` | Reviewers, test command, rule files, paths never sent, allowed reviewers, specs folder | team mode |
| `.agent-loop/guard.sh` | The repo's veto. Runs before anything is sent; non-zero means nothing leaves the machine | team mode |
| `.agent-loop/test.sh` | The checks whose output reviewers see. A failure blocks a pass | team mode |
| `.agent-loop/templates/` | This repo's spec and triage-log templates | team mode |
| `.agent-loop/core/` | The pinned loop engine (`VERSION` says which) | team mode only; local mode uses the developer's install |
| `.agent-loop/review.sh` | Wrapper that finds the engine | team mode |
| `.agent-loop/local.sh` | This developer's own settings: mode, account profile, engine path | never |
| `<specs>/NNN-slug/` | `spec.md` (contract), `log.md` (triage decisions), `reviews/` (verdicts) | team mode |
| `.agent-loop/.runs/` | Scratch: prompts, raw output, logs | never |

In **local** mode none of this is committed: `init-loop` hides it through `.git/info/exclude`, so the loop works for one developer without changing the team's repo.

## Running a review by hand

```bash
bash .agent-loop/review.sh <specs>/004-csv-validation                 # code review
bash .agent-loop/review.sh <specs>/004-csv-validation --phase spec    # review the spec before building
bash .agent-loop/review.sh <specs>/004-csv-validation --only codex    # one reviewer
bash .agent-loop/review.sh --help                                     # reviewers, custom models, env knobs
```

Exit codes: `0` pass · `1` changes requested · `2` a reviewer errored (doesn't use up a round) · `3` refused by the guard or the account check (nothing was sent).

## The gate

A round passes only when the tests pass and *each* reviewer, on its own, returns `approve`, reports no `blocker` or `major` finding, and grades every AC `met`.

## Accounts

If `local.sh` names a profile (`LOOP_PROFILE`), reviews only run when that profile is active, so this repo's code never goes out through the wrong accounts. `LOOP_ALLOWED_REVIEWERS` in `config.sh` is the repo's list of approved models (`local/*` = every model on Ollama, which never leaves the machine). The active profile can narrow it further.
