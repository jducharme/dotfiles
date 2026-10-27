# shellcheck shell=bash
# Account profile: __NAME__. Created by `loop-profile new`; edit freely.
# It lives in ~/.config/agent-loop/profiles/, not in dotfiles, so employer details stay off your repo.
# direnv loads it in folders set up with:  loop-profile use __NAME__ <folder>
# Every tool that runs there (Claude Code, the loop's reviewers, git, gh) then uses these accounts.

export LOOP_ACTIVE_PROFILE="__NAME__"

# Models this profile may send code to: only what this employer has approved.
# The loop refuses any other reviewer here. Leave it empty only if anything is fine.
# local/* allows every local model: they run on this machine, so the code never leaves it.
export LOOP_PROFILE_REVIEWERS="__REVIEWERS__"

_acct="$HOME/.config/agent-loop/accounts/__NAME__"
unset LOOP_PROFILE_WARNINGS

# Claude Code. On macOS its normal login sits in a single Keychain entry shared by every config
# folder, so this profile uses its own long-lived token instead (`loop-profile login __NAME__ claude`
# stores it in the Keychain as agent-loop.__NAME__.claude). Never run /login in these folders: it
# would overwrite your personal login. If the company gives you an API key or Bedrock instead,
# replace this block with e.g. `export ANTHROPIC_API_KEY=...` or `export CLAUDE_CODE_USE_BEDROCK=1`.
export CLAUDE_CONFIG_DIR="$_acct/claude"
_tok="$(security find-generic-password -s "agent-loop.__NAME__.claude" -w 2>/dev/null || true)"
if [ -n "$_tok" ]; then
  export CLAUDE_CODE_OAUTH_TOKEN="$_tok"
else
  # Fail closed: an unusable token makes Claude Code error out instead of quietly using your
  # personal Keychain login.
  export CLAUDE_CODE_OAUTH_TOKEN="agent-loop-no-token-for-__NAME__"
  export LOOP_PROFILE_WARNINGS="claude: no token yet. Run: loop-profile login __NAME__ claude"
fi

# Codex keeps its login in CODEX_HOME (`loop-profile login __NAME__ codex`).
export CODEX_HOME="$_acct/codex"

# GitHub CLI (`loop-profile login __NAME__ gh`).
export GH_CONFIG_DIR="$_acct/gh"

# Gemini (agy) can't switch accounts: its one login is machine-wide. Keep gemini out of
# LOOP_PROFILE_REVIEWERS here unless this employer gave you a Gemini API key.

# Git identity for commits made in these folders.
export GIT_AUTHOR_EMAIL="__EMAIL__"
export GIT_COMMITTER_EMAIL="__EMAIL__"

unset _acct _tok
