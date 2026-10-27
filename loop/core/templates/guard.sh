#!/usr/bin/env bash
# Last check before anything leaves this machine for a reviewer model. This is the repo's to edit:
# add whatever this codebase must never send out (data files, regulated content, internal hosts...).
# Args: <base-ref> <diff-file> <phase>. Exit non-zero to refuse; review.sh then sends nothing.
set -uo pipefail
diff_file="${2:-}"
[ -s "$diff_file" ] || exit 0

# Added lines that look like live credentials. Only the file and patch line are printed,
# never the value, so the secret doesn't land in a terminal log or CI output either.
patterns='-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36}|xox[abprs]-[A-Za-z0-9-]{10,}|(PRIVATE_KEY|CLIENT_SECRET|API_KEY|DATABASE_URL)[[:space:]]*[=:][[:space:]]*["'"'"']?[^"'"'"'[:space:]$<{]{12,}'
hits=$(grep -nE '^\+' "$diff_file" | grep -E -- "$patterns" | grep -vE 'example|placeholder|your[-_]|<[A-Z_]+>|xxxx' || true)
if [ -n "$hits" ]; then
  echo "guard: the change adds something that looks like a secret. Remove it (or move it to .env) and re-run:" >&2
  echo "$hits" | cut -d: -f1 | while read -r n; do
    f=$(head -n "$n" "$diff_file" | grep -E '^\+\+\+ b/' | tail -1 | sed 's#^+++ b/##')
    echo "  ${f:-?} (patch line $n)" >&2
  done
  exit 1
fi
exit 0
