---
description: Open the PR for a spec whose review loop has passed
argument-hint: "<specs>/NNN-slug"
---
<!-- agent-loop: managed by init-loop; `init-loop --update` replaces this file -->

Spec: $ARGUMENTS.

1. Check that the newest `reviews/round-N-summary.md` says **PASS** and that its `head` matches the current commit. If code changed after that round, re-run `bash .agent-loop/review.sh <spec-dir>` first.
2. Check the working tree is clean (apart from the loop's own files in `local` mode) and you're on `spec/NNN-slug`.
3. `git push -u origin spec/NNN-slug`
4. Open the PR (`gh pr create --base <default branch> --title "spec NNN: <title>"`, or the repo's own process if it uses something else; ask the user if unsure). The body must include:
   - in `team` mode: `Spec: <specs>/NNN-slug` on its own line (a CI gate can read it). In `local` mode the spec isn't in the repo, so don't link it: describe the change in the repo's usual PR style instead
   - the outcome in one or two sentences
   - the ACs as a checklist, with the test that proves each one
   - how many review rounds it took, and any finding you **rejected**, with the reason
5. Tell the user the PR link. Leave `status: in-review` until it's merged; then set it to `done`.
