# shellcheck shell=bash
# Account profile: personal, the default everywhere. Sourced at shell startup (zsh/dotfiles.zsh).
# Folders with their own profile switch away from it through direnv (loop-profile use <name> <folder>);
# leaving those folders switches back. Linked to ~/.config/agent-loop/profiles/personal.sh.

export LOOP_ACTIVE_PROFILE="personal"

# Models this profile may send code to. Empty = any of them.
export LOOP_PROFILE_REVIEWERS=""

# Personal uses each CLI's own default login (claude, codex login, agy, gh auth login), so nothing
# is pointed elsewhere. Clear anything a work profile may have set in this shell.
unset CLAUDE_CONFIG_DIR CLAUDE_CODE_OAUTH_TOKEN CODEX_HOME GH_CONFIG_DIR LOOP_PROFILE_WARNINGS
unset GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL
