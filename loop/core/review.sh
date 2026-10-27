#!/usr/bin/env bash
# agent-loop: other models independently review the current change (or the spec) against a spec.
#
# Same script on a laptop and in CI, so both give the same verdict. Portable to macOS's bash 3.2.
#
# Two directories are involved:
#   CORE  the directory holding this script: the prompt, schema and verdict code. Either a pinned
#         copy committed in the repo (.agent-loop/core/, "team" mode) or the developer's own
#         install ("local" mode). .agent-loop/review.sh is a thin wrapper that finds it.
#   LOOP  .agent-loop/ in the repo under review: config.sh, guard.sh, test.sh, local.sh, .runs/.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash .agent-loop/review.sh <spec-dir> [options]

  <spec-dir>            e.g. specs/004-csv-upload-validation (must contain spec.md)

Options:
  --phase code|spec     code (default): grade the change on this branch against the spec
                        spec: review the spec itself, before any code is written
  --base <ref>          what to diff against (default: $LOOP_BASE, else origin/main, else main)
  --only <reviewer>     run just one reviewer (overrides LOOP_REVIEWERS)
  --no-tests            skip the test step (code phase)

Reviewers (LOOP_REVIEWERS in .agent-loop/config.sh, space-separated):
  claude   Claude Code (`claude -p`, file-reading tools only)
  codex    Codex CLI (`codex exec --sandbox read-only`)
  gemini   Antigravity CLI (`agy`, plan mode)
  local/<model>  a model on Ollama on this machine. <model> is a name from LOOP_LOCAL_MODELS
           ("name=ollama-tag ...", in config.sh or ~/.config/agent-loop/defaults.sh) or an Ollama
           tag itself, e.g. local/qwen or local/deepseek-r1:32b. Plain `local` is the first one listed.
           Local reviewers run one at a time (big models don't fit in memory together), alongside
           the cloud reviewers.
  <name>   any other model: set LOOP_CMD_<name> in config.sh to a command that reads the prompt on
           stdin and prints the JSON verdict on stdout (e.g. a company CLI or an internal gateway).
           It also gets LOOP_PROMPT_FILE, LOOP_SCHEMA_FILE and LOOP_CORE in its environment.

Accounts: if .agent-loop/local.sh sets LOOP_PROFILE, the active profile ($LOOP_ACTIVE_PROFILE) must
match, and every reviewer must be allowed by LOOP_ALLOWED_REVIEWERS (config.sh, the repo's policy)
and by $LOOP_PROFILE_REVIEWERS (the profile's), when those are set. Otherwise nothing is sent.

Env: LOOP_REVIEWERS    which reviewers run (beats config.sh)
     LOOP_CLAUDE_MODEL   claude --model (default: Claude Code's own)
     LOOP_CLAUDE_ARGS    extra args for claude -p
     LOOP_GEMINI_MODEL   agy model slug (default: agy's own; list them with `agy models`)
     LOOP_AGY_MODE       agy --mode (default "plan" = read-only; set "" to omit the flag)
     LOOP_AGY_SCHEMA     1 (default) enforces the verdict with --json-schema; 0 relies on the prompt
     LOOP_AGY_MAX_PROMPT max prompt bytes for agy (default 120000; the prompt goes in as an argument)
     LOOP_AGY_TIMEOUT    agy --print-timeout (default 15m)
     LOOP_CODEX_MODEL    (default: Codex's own default)
     LOOP_CLI_GRACE      watchdog: seconds a CLI may keep running after its result is complete on disk
                         before it is stopped and the result kept (default 60)
     LOOP_CLI_HARD_TIMEOUT  watchdog: seconds before a reviewer CLI is stopped regardless (default 1500,
                         i.e. 25m; keep it above LOOP_AGY_TIMEOUT). A stopped reviewer errors (exit 2)

Exit: 0 pass · 1 changes requested · 2 tool/reviewer error · 3 refused by the guard or the account
      check (nothing was sent)
EOF
}

die() { echo "agent-loop: $*" >&2; exit 2; }
CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || die "can't resolve the agent-loop directory"

SPEC_DIR=""; PHASE=code; BASE="${LOOP_BASE:-}"; ONLY=""; RUN_TESTS=1
while [ $# -gt 0 ]; do
  case "$1" in
    --phase) PHASE="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --only) ONLY="${2:-}"; shift 2 ;;
    --no-tests) RUN_TESTS=0; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) usage >&2; exit 2 ;;
    *) [ -z "$SPEC_DIR" ] || die "only one spec dir, got '$SPEC_DIR' and '$1'"; SPEC_DIR="$1"; shift ;;
  esac
done
[ -n "$SPEC_DIR" ] || { usage >&2; exit 2; }
case "$PHASE" in code|spec) ;; *) die "--phase must be 'code' or 'spec'" ;; esac

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"
cd "$ROOT"
LOOP=".agent-loop"   # this repo: config.sh, guard.sh, test.sh, .runs/
SPEC_DIR="${SPEC_DIR%/}"
SPEC_DIR="${SPEC_DIR#./}"
[ -f "$SPEC_DIR/spec.md" ] || die "$SPEC_DIR/spec.md not found"

# ---- repo config ---------------------------------------------------------------------
ENV_REVIEWERS="${LOOP_REVIEWERS:-}"   # an env var beats config.sh
LOOP_REVIEWERS=""
LOOP_TEST_CMD=""
LOOP_RULES_FILES=()
LOOP_DIFF_EXCLUDES=()
LOOP_MAX_DIFF_BYTES=300000
LOOP_SPECS_DIR="specs"
LOOP_SPEC_REVIEWERS=""
LOOP_ALLOWED_REVIEWERS=""
LOOP_PROFILE=""
LOOP_LOCAL_MODELS=""
# shellcheck source=/dev/null
[ -f "$LOOP/config.sh" ] && . "$LOOP/config.sh"
# local.sh is this developer's own, never committed: install mode, profile, where the core lives.
# shellcheck source=/dev/null
[ -f "$LOOP/local.sh" ] && . "$LOOP/local.sh"
SPECS="${LOOP_SPECS_DIR%/}"
# This machine's local models (names -> Ollama tags) and Ollama URL. Only those two settings are read
# from the machine defaults; everything else comes from the repo.
MACHINE_DEFAULTS="${LOOP_DEFAULTS:-$HOME/.config/agent-loop/defaults.sh}"
MACHINE_LOCAL_MODELS=""; MACHINE_OLLAMA_URL=""
if [ -f "$MACHINE_DEFAULTS" ]; then
  # shellcheck source=/dev/null
  MACHINE_LOCAL_MODELS="$(LOOP_LOCAL_MODELS=""; . "$MACHINE_DEFAULTS" >/dev/null 2>&1; printf '%s' "$LOOP_LOCAL_MODELS")"
  # shellcheck source=/dev/null
  MACHINE_OLLAMA_URL="$(LOOP_OLLAMA_URL=""; . "$MACHINE_DEFAULTS" >/dev/null 2>&1; printf '%s' "$LOOP_OLLAMA_URL")"
fi
CLAUDE_MODEL="${LOOP_CLAUDE_MODEL:-}"
CLAUDE_ARGS="${LOOP_CLAUDE_ARGS:-}"
GEMINI_MODEL="${LOOP_GEMINI_MODEL:-}"
AGY_MODE="${LOOP_AGY_MODE-plan}"
AGY_SCHEMA="${LOOP_AGY_SCHEMA:-1}"
AGY_MAX_PROMPT="${LOOP_AGY_MAX_PROMPT:-120000}"
AGY_TIMEOUT="${LOOP_AGY_TIMEOUT:-15m}"
CODEX_MODEL="${LOOP_CODEX_MODEL:-}"
CLI_GRACE="${LOOP_CLI_GRACE:-60}"
CLI_HARD_TIMEOUT="${LOOP_CLI_HARD_TIMEOUT:-1500}"
case "$CLI_GRACE$CLI_HARD_TIMEOUT" in *[!0-9]*) die "LOOP_CLI_GRACE and LOOP_CLI_HARD_TIMEOUT must be whole seconds" ;; esac

if [ -n "$ONLY" ]; then
  REVIEWERS="$ONLY"
elif [ "$PHASE" = spec ] && [ -z "$ENV_REVIEWERS" ] && [ -n "${LOOP_SPEC_REVIEWERS:-}" ]; then
  REVIEWERS="$(printf '%s' "$LOOP_SPEC_REVIEWERS" | tr ',' ' ')"
else
  REVIEWERS="$(printf '%s' "${ENV_REVIEWERS:-${LOOP_REVIEWERS:-}}" | tr ',' ' ')"
fi
[ -n "$(printf '%s' "$REVIEWERS" | tr -d ' ')" ] || die "no reviewers: set LOOP_REVIEWERS in $LOOP/config.sh"

custom_cmd() { # reviewer -> its LOOP_CMD_<name> command, or empty
  local var="LOOP_CMD_$1"
  if [ -z "${!var:-}" ] && [ "$1" = local ]; then
    printf '%s' 'python3 "$LOOP_CORE/lib/ollama_review.py"'   # built in: a model on Ollama
    return
  fi
  printf '%s' "${!var:-}"
}
is_local() { case "$1" in local|local/*) return 0 ;; esac; return 1; }
local_model() { # local reviewer -> the Ollama tag it runs
  local want="${1#local}" pair
  want="${want#/}"
  if [ -z "$want" ]; then
    if [ -n "${LOOP_LOCAL_MODEL:-}" ]; then printf '%s' "$LOOP_LOCAL_MODEL"; return; fi
    for pair in $LOOP_LOCAL_MODELS $MACHINE_LOCAL_MODELS; do printf '%s' "${pair#*=}"; return; done
    printf '%s' "qwen3.6:35b-a3b"; return
  fi
  for pair in $LOOP_LOCAL_MODELS $MACHINE_LOCAL_MODELS; do
    case "$pair" in "$want="*) printf '%s' "${pair#*=}"; return ;; esac
  done
  printf '%s' "$want"   # not a name: an Ollama tag itself
}
slug() { printf '%s' "$1" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9_-' '-'; }   # file-safe: local/qwen -> local-qwen

seen_slugs=" "
for r in $REVIEWERS; do
  s="$(slug "$r")"
  case "$seen_slugs" in *" $s "*) die "reviewer '$r' is listed twice (or shares the file name '$s' with another one)" ;; esac
  seen_slugs="$seen_slugs$s "
  case "$r" in
    claude|codex|gemini) ;;
    local|local/*)
      case "${r#local/}" in *[!A-Za-z0-9._:-]*) die "local model '$r': use letters, digits and . _ : - only" ;; esac ;;
    *[!a-z0-9_]*|[!a-z]*) die "reviewer name '$r': use lowercase letters, digits and _ (or local/<model>)" ;;
    *) [ -n "$(custom_cmd "$r")" ] || die "unknown reviewer '$r': built-ins are claude, codex, gemini, local/<model>; for anything else set LOOP_CMD_$r in $LOOP/config.sh" ;;
  esac
done

# ---- accounts: never send this repo's code through the wrong accounts ----------------------
refuse() { echo "agent-loop: REFUSED. $* Nothing was sent to any reviewer." >&2; exit 3; }
in_list() { # reviewer "list": exact names, or prefix/* (e.g. local/* allows every local model)
  local e
  while IFS= read -r e; do
    [ -n "$e" ] || continue
    case "$e" in
      */\*) [ "$1" = "${e%/\*}" ] && return 0; case "$1" in "${e%\*}"*) return 0 ;; esac ;;
      *) [ "$1" = "$e" ] && return 0 ;;
    esac
  done <<LIST
$(printf '%s' "$2" | tr ' ' '\n')
LIST
  return 1
}
if [ -n "$LOOP_PROFILE" ] && [ "${LOOP_ACTIVE_PROFILE:-}" != "$LOOP_PROFILE" ]; then
  refuse "This repo uses the '$LOOP_PROFILE' accounts but the active profile is '${LOOP_ACTIVE_PROFILE:-none}'. Open a terminal in this repo with that profile active (see: loop-profile), then re-run."
fi
for r in $REVIEWERS; do
  if [ -n "$LOOP_ALLOWED_REVIEWERS" ] && ! in_list "$r" "$LOOP_ALLOWED_REVIEWERS"; then
    refuse "'$r' isn't an approved reviewer for this repo (LOOP_ALLOWED_REVIEWERS=\"$LOOP_ALLOWED_REVIEWERS\" in $LOOP/config.sh)."
  fi
  if [ -n "${LOOP_PROFILE_REVIEWERS:-}" ] && ! in_list "$r" "$LOOP_PROFILE_REVIEWERS"; then
    refuse "The '${LOOP_ACTIVE_PROFILE:-current}' profile doesn't allow sending code to '$r' (LOOP_PROFILE_REVIEWERS=\"$LOOP_PROFILE_REVIEWERS\")."
  fi
done

command -v python3 >/dev/null 2>&1 || die "python3 not found"
cli_for() { case "$1" in gemini) echo agy ;; claude|codex) echo "$1" ;; *) echo "" ;; esac; }
for r in $REVIEWERS; do
  cli="$(cli_for "$r")"
  [ -z "$cli" ] || command -v "$cli" >/dev/null 2>&1 || die "'$cli' CLI not found on PATH (run ai-doctor)"
done

if [ -z "$BASE" ]; then
  if git rev-parse -q --verify "origin/main^{commit}" >/dev/null; then BASE=origin/main; else BASE=main; fi
fi
git rev-parse -q --verify "$BASE^{commit}" >/dev/null || die "base ref '$BASE' not found (try: git fetch origin)"
MB="$(git merge-base "$BASE" HEAD)"
HEAD_SHA="$(git rev-parse --short HEAD)"
DIRTY=""; [ -z "$(git status --porcelain --untracked-files=normal)" ] || DIRTY=" + uncommitted changes"

# ---- round bookkeeping -----------------------------------------------------------------
REVIEWS="$SPEC_DIR/reviews"
PREFIX=round; [ "$PHASE" = spec ] && PREFIX=spec-round
ROUND=1
while [ -e "$REVIEWS/$PREFIX-$ROUND-summary.md" ]; do ROUND=$((ROUND + 1)); done
TAG="$PREFIX-$ROUND"
RUN="$LOOP/.runs/$(basename "$SPEC_DIR")/$TAG"
rm -rf "$RUN"; mkdir -p "$RUN"

# ---- the change ------------------------------------------------------------------------
# Reviewers never see review output, run folders, or anything the repo config excludes.
PATHSPEC=(. ":(exclude,glob)$SPECS/*/reviews/**" ':(exclude,glob).agent-loop/.runs/**' ':(exclude).agent-loop/local.sh')
[ ${#LOOP_DIFF_EXCLUDES[@]} -gt 0 ] && PATHSPEC+=("${LOOP_DIFF_EXCLUDES[@]}")
: > "$RUN/diff.patch"; : > "$RUN/diffstat.txt"
if [ "$PHASE" = code ]; then
  git diff --no-color --no-ext-diff "$MB" -- "${PATHSPEC[@]}" > "$RUN/diff.patch"
  git diff --no-color --stat=120 "$MB" -- "${PATHSPEC[@]}" > "$RUN/diffstat.txt"
  # New files that aren't staged yet (the author often hasn't `git add`ed them).
  git ls-files --others --exclude-standard -z -- "${PATHSPEC[@]}" > "$RUN/untracked.z"
  while IFS= read -r -d '' f; do
    git diff --no-color --no-index -- /dev/null "$f" >> "$RUN/diff.patch" || true
    echo " $f (new, untracked)" >> "$RUN/diffstat.txt"
  done < "$RUN/untracked.z"
  [ -s "$RUN/diff.patch" ] || die "no changes against $BASE (merge-base ${MB:0:7}), so there's nothing to review"
fi

# ---- guard: the repo can veto sending anything ------------------------------------------
if [ -f "$LOOP/guard.sh" ]; then
  if ! bash "$LOOP/guard.sh" "$BASE" "$RUN/diff.patch" "$PHASE"; then
    rm -rf "$RUN"
    echo "agent-loop: guard refused. Nothing was sent to any reviewer." >&2
    exit 3
  fi
fi

# ---- tests -----------------------------------------------------------------------------
TEST_EXIT=-1
if [ "$PHASE" = code ] && [ "$RUN_TESTS" = 1 ] && [ -n "$LOOP_TEST_CMD" ]; then
  echo "agent-loop: running tests: $LOOP_TEST_CMD" >&2
  set +e
  bash -c "$LOOP_TEST_CMD" > "$RUN/tests.txt" 2>&1
  TEST_EXIT=$?
  set -e
  echo "agent-loop: tests exited $TEST_EXIT" >&2
else
  echo "(tests not run in this phase)" > "$RUN/tests.txt"
fi

# ---- base versions -----------------------------------------------------------------------
# Reviewers can't run shell commands: in headless mode agy refuses any command (even a
# read-only `git show`) and that ends the review with no output. So the pre-change version of
# every changed or deleted file is saved here for them to read. Only paths the diff itself
# covers (same pathspec and excludes), only after the guard has passed, and
# after the tests, so test.sh never picks the copies up as code to run.
BASE_DIR="$RUN/base"
if [ "$PHASE" = code ]; then
  git diff --name-only --no-renames -z "$MB" -- "${PATHSPEC[@]}" > "$RUN/changed.z"
  while IFS= read -r -d '' f; do
    if git cat-file -e "$MB:$f" 2>/dev/null; then
      mkdir -p "$BASE_DIR/$(dirname "$f")"
      git show "$MB:$f" > "$BASE_DIR/$f"
    fi
  done < "$RUN/changed.z"
fi

# ---- prompt ----------------------------------------------------------------------------
section() { # tag attrs file
  printf '\n<%s%s>\n' "$1" "$2"
  if [ -s "$3" ]; then cat "$3"; else printf '(none)'; fi
  printf '\n</%s>\n' "$1"
}

build_prompt() { # reviewer [max diff bytes]
  local prev="$REVIEWS/$PREFIX-$((ROUND - 1))-summary.md" size trunc="" cap="${2:-$LOOP_MAX_DIFF_BYTES}"
  {
    cat "$CORE/review-prompt.md"
    printf '\n<run>\nreviewer: %s\nphase: %s\nround: %s\nspec_dir: %s\nbase: %s (merge-base %s)\nhead: %s%s\n</run>\n' \
      "$1" "$PHASE" "$ROUND" "$SPEC_DIR" "$BASE" "${MB:0:12}" "$HEAD_SHA" "$DIRTY"
    printf '\n<review_environment>\nYou cannot run shell commands in this review: any command (git, python, ls, ...) is refused, and a refused command ends your review with no output. Use your file-reading tools only, with absolute paths under %s.\n' "$ROOT"
    if [ "$PHASE" = code ]; then
      printf 'The version of every changed or deleted file at the merge-base is saved under %s/%s/<path>, where <path> is the repo-relative path. Read those instead of running git show or git diff; a file missing there is new in this change.\n' "$ROOT" "$BASE_DIR"
    fi
    printf '</review_environment>\n'
    if [ ${#LOOP_RULES_FILES[@]} -gt 0 ]; then
      for f in "${LOOP_RULES_FILES[@]}"; do [ -f "$f" ] && section repo_rules " file=\"$f\"" "$f"; done
    fi
    section spec " file=\"$SPEC_DIR/spec.md\"" "$SPEC_DIR/spec.md"
    section triage_log " file=\"$SPEC_DIR/log.md\"" "$SPEC_DIR/log.md"
    section previous_round_summary "" "$prev"
    if [ "$PHASE" = code ]; then
      printf '\n<test_results command="%s" exit_code="%s">\n' "$LOOP_TEST_CMD" "$TEST_EXIT"
      tail -c 30000 "$RUN/tests.txt"
      printf '\n</test_results>\n'
      section diffstat "" "$RUN/diffstat.txt"
      size=$(wc -c < "$RUN/diff.patch" | tr -d ' ')
      if [ "$size" -gt "$cap" ]; then
        trunc=" truncated=\"true\" note=\"diff is ${size} bytes; first ${cap} shown. Read the remaining changed files (see diffstat) from the repo.\""
      fi
      printf '\n<diff base="%s"%s>\n' "${MB:0:12}" "$trunc"
      # macOS (BSD) head rejects "-c 0" and set -e would end the run here, so skip it at 0.
      if [ "$cap" -gt 0 ]; then head -c "$cap" "$RUN/diff.patch"; fi
      printf '\n</diff>\n'
    fi
    section output_schema "" "$CORE/verdict.schema.json"
    printf '\nRespond with ONLY the JSON object. No prose, no code fences.\n'
  } > "$RUN/prompt-$1.txt"
}

# ---- watchdog --------------------------------------------------------------------------
# A reviewer CLI can finish its review and then never exit: agy 1.4.3 sometimes never shuts down its
# language server after print mode, and review.sh would wait on it forever (seen: 15 hours). agy's own
# --print-timeout doesn't help, because the review itself has already finished. So each CLI runs in the
# background and is stopped, with its whole process tree, when either
#   - its result file has held one complete JSON document for $CLI_GRACE seconds and it still hasn't
#     exited: the result is kept and used, and the stop is noted in the reviewer's log; or
#   - it has run for $CLI_HARD_TIMEOUT seconds in total: return 124, so the reviewer errors (exit 2).
result_complete() { # file: true once it holds one complete JSON document
  [ -s "$1" ] && python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$1" >/dev/null 2>&1
}

tree_pids() { # pid: the pid and all its descendants
  local p
  echo "$1"
  for p in $(pgrep -P "$1" 2>/dev/null); do tree_pids "$p"; done
}

stop_tree() { # pid: TERM the whole tree, then KILL whatever is still alive 5s later
  local pids i=0
  pids="$(tree_pids "$1" | tr '\n' ' ')"
  # shellcheck disable=SC2086  # a list of pids
  kill -TERM $pids 2>/dev/null || true
  # shellcheck disable=SC2086
  while [ $i -lt 10 ] && kill -0 $pids 2>/dev/null; do sleep 0.5; i=$((i + 1)); done
  # shellcheck disable=SC2086
  kill -KILL $pids 2>/dev/null || true
}

watch_cli() { # name pid result-file log-file -> the CLI's exit code; 0 if stopped after a result; 124 at the limit
  local name="$1" pid="$2" out="$3" log="$4" start=$SECONDS done_at=""
  while kill -0 "$pid" 2>/dev/null; do
    if [ -z "$done_at" ] && result_complete "$out"; then done_at=$SECONDS; fi
    if [ -n "$done_at" ] && [ $((SECONDS - done_at)) -ge "$CLI_GRACE" ]; then
      echo "agent-loop watchdog: $name wrote a complete result but was still running ${CLI_GRACE}s later; stopped it and kept the result." >> "$log"
      echo "agent-loop: $name finished but didn't exit; the watchdog stopped it (result kept)" >&2
      stop_tree "$pid"; wait "$pid" 2>/dev/null
      return 0
    fi
    if [ $((SECONDS - start)) -ge "$CLI_HARD_TIMEOUT" ]; then
      echo "agent-loop watchdog: $name ran for ${CLI_HARD_TIMEOUT}s without a complete result; stopped it. Re-run the round." >> "$log"
      echo "agent-loop: $name hit the ${CLI_HARD_TIMEOUT}s watchdog limit and was stopped" >&2
      stop_tree "$pid"; wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 2
  done
  wait "$pid"
}

# ---- reviewers -------------------------------------------------------------------------
run_gemini() {
  # Antigravity CLI. The prompt goes in as the -p argument: plain stdin isn't read in print mode,
  # and an open stdin can hang it, hence </dev/null. -p goes last because it takes the next token.
  local args=(--output-format json --print-timeout "$AGY_TIMEOUT")
  [ -n "$AGY_MODE" ] && args+=(--mode "$AGY_MODE")
  [ "$AGY_SCHEMA" = 1 ] && args+=(--json-schema "$CORE/verdict.schema.json")
  [ -n "$GEMINI_MODEL" ] && args+=(--model "$GEMINI_MODEL")
  agy --version > "$RUN/gemini.log" 2>&1 || true
  agy "${args[@]}" -p "$(cat "$RUN/prompt-gemini.txt")" \
    < /dev/null > "$RUN/gemini.out" 2>> "$RUN/gemini.log" &
  watch_cli gemini $! "$RUN/gemini.out" "$RUN/gemini.log"
}

run_codex() {
  local args=(exec --sandbox read-only --output-schema "$CORE/verdict.schema.json" -o "$RUN/codex.out")
  codex exec --help 2>&1 | grep -q -- '--ephemeral' && args+=(--ephemeral)   # don't keep session files
  [ -n "$CODEX_MODEL" ] && args+=(-m "$CODEX_MODEL")
  codex "${args[@]}" - < "$RUN/prompt-codex.txt" > "$RUN/codex.log" 2>&1 &
  watch_cli codex $! "$RUN/codex.out" "$RUN/codex.log"
}

run_claude() {
  # Claude Code in print mode, prompt on stdin. Shell, edit and web tools are taken away, so it can
  # only read files. Repo permission rules (e.g. "allow bash .agent-loop/review.sh") don't apply.
  local args=(-p --output-format json --disallowedTools "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch")
  [ -n "$CLAUDE_MODEL" ] && args+=(--model "$CLAUDE_MODEL")
  claude --version > "$RUN/claude.log" 2>&1 || true
  # shellcheck disable=SC2086  # LOOP_CLAUDE_ARGS is a list of extra flags
  claude "${args[@]}" $CLAUDE_ARGS < "$RUN/prompt-claude.txt" > "$RUN/claude.out" 2>> "$RUN/claude.log" &
  watch_cli claude $! "$RUN/claude.out" "$RUN/claude.log"
}

run_custom() { # name slug: the command reads the prompt on stdin and prints the verdict JSON
  local name="$1" s="$2" cmd model=""
  if is_local "$name"; then
    cmd="$(custom_cmd local)"; model="$(local_model "$name")"
  else
    cmd="$(custom_cmd "$name")"
  fi
  { echo "command: $cmd"; [ -z "$model" ] || echo "model: $model"; } > "$RUN/$s.log"
  LOOP_PROMPT_FILE="$ROOT/$RUN/prompt-$s.txt" LOOP_SCHEMA_FILE="$CORE/verdict.schema.json" LOOP_CORE="$CORE" \
    LOOP_LOCAL_MODEL="${model:-${LOOP_LOCAL_MODEL:-}}" LOOP_OLLAMA_URL="${LOOP_OLLAMA_URL:-$MACHINE_OLLAMA_URL}" \
    bash -c "$cmd" < "$RUN/prompt-$s.txt" > "$RUN/$s.out" 2>> "$RUN/$s.log" &
  watch_cli "$s" $! "$RUN/$s.out" "$RUN/$s.log"
}

# Cloud reviewers run in parallel in the background; local ones then run one at a time, so two big
# models never compete for memory.
SLUGS=""
for r in $REVIEWERS; do SLUGS="$SLUGS $(slug "$r")"; done
for r in $REVIEWERS; do
  is_local "$r" && continue
  if [ "$r" = gemini ]; then
    # Size the diff so the whole prompt fits in one argument (Linux caps a single arg at 128 KB).
    build_prompt gemini 0
    budget=$(( AGY_MAX_PROMPT - $(wc -c < "$RUN/prompt-gemini.txt" | tr -d ' ') - 500 ))
    [ "$budget" -gt "$LOOP_MAX_DIFF_BYTES" ] && budget=$LOOP_MAX_DIFF_BYTES
    [ "$budget" -lt 2000 ] && budget=2000
    build_prompt gemini "$budget"
  else
    build_prompt "$r"
  fi
  echo "agent-loop: $r reviewing ($PHASE phase, round $ROUND)…" >&2
  case "$r" in
    claude|codex|gemini) ( set +e; "run_$r"; echo $? > "$RUN/$r.exit" ) & ;;
    *) ( set +e; run_custom "$r" "$r"; echo $? > "$RUN/$r.exit" ) & ;;
  esac
done
for r in $REVIEWERS; do
  is_local "$r" || continue
  s="$(slug "$r")"
  build_prompt "$s"
  echo "agent-loop: $r ($(local_model "$r")) reviewing ($PHASE phase, round $ROUND)…" >&2
  ( set +e; run_custom "$r" "$s"; echo $? > "$RUN/$s.exit" )
done
wait

META="spec \`$SPEC_DIR\` · base \`$BASE\` @ ${MB:0:7} · head ${HEAD_SHA}${DIRTY}"
set +e
# shellcheck disable=SC2086  # SLUGS is a space-separated list of file-safe reviewer names
python3 "$CORE/lib/verdict.py" merge --phase "$PHASE" --round "$ROUND" --tag "$TAG" \
  --tests-exit "$TEST_EXIT" --run-dir "$RUN" --reviews-dir "$REVIEWS" \
  --spec "$SPEC_DIR/spec.md" --meta "$META" $SLUGS
rc=$?
set -e
exit $rc
