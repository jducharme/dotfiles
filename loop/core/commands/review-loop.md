---
description: The other models grade the change against its spec; triage every finding, fix, and re-run until they all approve (max 3 rounds)
argument-hint: "<specs>/NNN-slug"
---
<!-- agent-loop: managed by init-loop; `init-loop --update` replaces this file -->

Spec: $ARGUMENTS. Run at most **3 rounds** (or `$LOOP_MAX_ROUNDS` if it's set), then hand back to the user.

**Each round:**

1. `bash .agent-loop/review.sh <spec-dir>` (Bash timeout 600000; if a big change times out, re-run it in the background). Reviewers see everything on the branch against the base, including uncommitted and new files.
   - **0**: every reviewer approves and the tests pass. Go to "Done".
   - **1**: changes requested. Go to step 2.
   - **2**: tool error (CLI missing or logged out, unusable output). The summary names the run folder: read its `*.log`, show the user the error, retry once if it looks transient, otherwise stop.
   - **3**: refused by the guard or the account check. Stop and show the user exactly what it printed. Never work around it, edit the guard, switch accounts or reviewers yourself, or retry with a check disabled.
2. Read `reviews/round-N-summary.md`. Decide on every finding, and on every AC that isn't `met`:
   - **fix**: a real issue within the spec's scope.
   - **reject**: the reviewer is wrong, or the point is out of scope. Give the concrete reason and cite the spec section or the code. Reviewers read your reason next round.
   - **ask-human**: the spec is silent or ambiguous, or the reviewers disagree on something the spec doesn't settle.
   The reviewers can be wrong. Agreeing with them by default is a failure, so judge each point on its merits. When reviewers conflict, the spec decides.
3. Add a `## Round N (code)` table to `log.md` (Finding | Decision | Note). Every finding gets a row.
4. Make the fixes, run `bash .agent-loop/test.sh`, commit `spec NNN: address review round N`, and start the next round.

**Done:** when a round passes, set the spec to `status: in-review`, commit `log.md` and (where the repo commits them) `reviews/`, and tell the user it's ready for `/ship`.

**Stop early** if an ask-human item comes up, or after the last round. Give the user a short list: what's still open, what each reviewer says, and your recommendation. Also flag anything weird: a reviewer that keeps raising rejected points, reviewers flatly contradicting each other, or a fix that pulls the change outside the spec.

**Hard rules**
- Never edit the acceptance criteria, the scope, the reviewers' output, the guard, the account settings, or the review prompt to get a pass. Changing the spec needs the user's explicit OK, recorded in `log.md`.
- Never skip, delete or weaken a test to get a pass.
