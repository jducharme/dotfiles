#!/usr/bin/env bash
# The loop's own checks:  bash loop/tests/run.sh   (from anywhere)
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
status=0
run() {
  echo
  echo "\$ $*"
  "$@" || { echo "^^ FAILED (exit $?)"; status=1; }
}

for f in core/review.sh core/templates/guard.sh bin/init-loop tests/run.sh; do run bash -n "$f"; done   # syntax
if command -v shellcheck >/dev/null 2>&1; then run shellcheck -S warning core/review.sh core/templates/guard.sh bin/init-loop; fi
run python3 tests/test_verdict.py    # the review gate itself
run python3 tests/test_watchdog.py   # review.sh stops a reviewer CLI that hangs
run python3 tests/test_init.py       # init-loop in both modes, the account check, every reviewer kind

echo
[ $status -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $status
