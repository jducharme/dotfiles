---
description: Turn the intent agreed in this conversation into a spec (the contract), have the other models review it, and get the user's approval
argument-hint: "[short title]"
---
<!-- agent-loop: managed by init-loop; `init-loop --update` replaces this file -->

You are writing the **contract** for a piece of work. Other models will later grade the code against exactly what you write, so precision matters more than length. Don't write implementation code in this command.

1. Read `.agent-loop/LOOP.md`, `.agent-loop/config.sh` (`LOOP_SPECS_DIR` is the specs folder, default `specs`; `LOOP_REVIEWERS` are the reviewers) and the repo rules that CLAUDE.md or AGENTS.md point to.
2. Number and name it: the highest existing `<specs>/NNN-*` + 1, zero-padded to 3 digits. The slug comes from "$ARGUMENTS" or the conversation, in kebab-case, 5 words at most.
3. Copy `.agent-loop/templates/spec.md` and `.agent-loop/templates/log.md` to `<specs>/NNN-slug/`. Fill in the spec from this conversation:
   - Write only what the user actually agreed. Anything you're inferring goes under **Open questions**, not into scope or the ACs.
   - Every acceptance criterion needs an ID (`AC-1`, `AC-2`, …), observable behaviour, and a `verify:` line naming the test or command that proves it.
   - Fill in **Out of scope** every time. Reviewers use it to catch drift.
   - Read the code the spec touches, so the design notes match how the code really works.
4. If Open questions holds anything that blocks the build, ask the user now, all in one batch, each with your recommendation. Update the spec and repeat.
5. Spec review: `bash .agent-loop/review.sh <specs>/NNN-slug --phase spec` (Bash timeout 600000).
   - Exit 3 (refused by the guard or the account check): stop and show the user exactly what it printed. Never work around it.
   - Exit 2 (a reviewer errored): show the user the error from the run folder's `*.log`; retry once if it looks transient.
   - Fold in findings that make the spec clearer or more testable, and record every decision in `log.md`.
   - Anything that would change *what* gets built goes back to the user as a question. Don't decide it yourself.
   - One spec round is normally enough. Re-run only if you changed the ACs substantially.
6. **Ask the user to approve the spec.** Show the ACs, the out-of-scope list, and any reviewer points you didn't take, with your reasons. Also raise anything that seems off: reviewers disagreeing, a risk nobody asked about, scope that grew. Only when the user explicitly approves: set `status: ready`, add `approved: YYYY-MM-DD` under the status line, and tell them `/build <specs>/NNN-slug` is next.
