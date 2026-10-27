---
description: Implement an approved spec on its own branch with a test per acceptance criterion, then run the review loop
argument-hint: "<specs>/NNN-slug"
---
<!-- agent-loop: managed by init-loop; `init-loop --update` replaces this file -->

Spec: $ARGUMENTS. If that's empty, use the only spec with `status: ready`, or ask.

1. Read `.agent-loop/LOOP.md`, then `spec.md` and `log.md` in full, plus the repo rules that CLAUDE.md or AGENTS.md point to. If the status isn't `ready` (approved by the user), or Open questions has unresolved items, stop and say so.
2. Branch: `git switch -c spec/NNN-slug` from an up-to-date default branch (or switch to the branch if it already exists). Never build on the default branch. If the working tree has unrelated uncommitted changes, stop and ask the user. Don't carry them into the branch.
3. Set `status: in-progress`. Build **only** what's in scope. If the spec turns out to be wrong or incomplete, stop and raise it with the user instead of quietly diverging. Reviewers grade drift.
4. Tests: every AC gets at least one automated test whose name starts with its ID (`AC-2: rejects rows without referenceId`), unless the spec marks it `verify: manual`. Run `bash .agent-loop/test.sh` until it's green.
5. Commit in small logical steps, with messages like `spec NNN: <what>`. In `local` mode (`.agent-loop/local.sh`), the spec folder isn't part of the repo: commit only the code.
6. Follow `.claude/commands/review-loop.md` for this spec.

Stop and tell the user if something looks off while building: a dependency behaving unexpectedly, data that doesn't match the spec's assumptions, or a change growing well past the spec.
