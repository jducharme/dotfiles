#!/bin/bash
# --- The GardenGnome Cultivator ---
# Sets up this Mac: apps, CLIs, shell, configs, and the multi-model AI toolchain for the agent loop.
# Safe to re-run: every step checks first, and anything it replaces is backed up to ~/.dotfiles-backup/.
#
#   ./install.sh            everything below
#   ./install.sh --models   also pull the local models listed in ai/defaults.sh (~24 GB for the default)
#   ./install.sh --grok     also install xAI's Grok Build CLI (`grok`)
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
. "$DOTFILES/lib/common.sh"

PULL_MODELS=0; WITH_GROK=0
for arg in "$@"; do
  case "$arg" in
    --models) PULL_MODELS=1 ;;
    --grok) WITH_GROK=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install.sh: unknown option '$arg' (see --help)" >&2; exit 2 ;;
  esac
done

say "🌱 Tilling the soil and preparing the environment..."

# 1. Root package management --------------------------------------------------------------------
step "1. Homebrew (the foundation)"
if ! have brew; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
[ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
brew update
ok "Homebrew"

# 2. Everything Homebrew installs lives in the Brewfile -------------------------------------------
step "2. Apps & CLIs (Brewfile)"
brew bundle --file "$DOTFILES/Brewfile"

# 3. Shell ----------------------------------------------------------------------------------------
step "3. Zsh"
if [ ! -d "$HOME/.oh-my-zsh" ]; then
  RUNZSH=no CHSH=no /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi
ok "Oh My Zsh"
migrate_zshrc "$HOME/.zshrc"
source_line "$HOME/.zshrc" "$DOTFILES/zsh/dotfiles.zsh"

# 4. Configs, as symlinks into this repo ----------------------------------------------------------
step "4. Configs"
# Karabiner rewrites karabiner.json when you change settings in its UI, which breaks a file symlink,
# so the whole folder is linked. Its UI changes then show up here as a git diff.
link karabiner "$HOME/.config/karabiner"            # Right Option -> F18
link claude/CLAUDE.md "$HOME/.claude/CLAUDE.md"     # how JD works with Claude Code, in every repo
link ai/defaults.sh "$HOME/.config/agent-loop/defaults.sh"
link ai/profiles/personal.sh "$HOME/.config/agent-loop/profiles/personal.sh"   # other profiles: loop-profile new
link bin/ai-doctor "$HOME/.local/bin/ai-doctor"
link bin/loop-profile "$HOME/.local/bin/loop-profile"
link loop/bin/init-loop "$HOME/.local/bin/init-loop"   # the loop itself lives in loop/

# 5. Multi-model AI toolchain ---------------------------------------------------------------------
step "5. AI toolchain"
# shellcheck source=ai/defaults.sh
. "$DOTFILES/ai/defaults.sh"

if [ "$WITH_GROK" = 1 ] && ! have grok; then
  curl -fsSL https://x.ai/cli/install.sh | bash
fi
if have grok; then ok "grok"; else say "  – grok not installed (optional: ./install.sh --grok)"; fi

# Figma's MCP server, for every repo (user scope): specs can point at Figma frames and builds can
# read them. Sign in the first time Claude Code uses it (/mcp).
if have claude; then
  mcp_servers="$(claude mcp list 2>/dev/null < /dev/null || true)"
  if printf '%s\n' "$mcp_servers" | grep -qi figma; then
    ok "Figma MCP in Claude Code"
  elif claude mcp add --transport http --scope user figma https://mcp.figma.com/mcp; then
    ok "Figma MCP added to Claude Code (authenticate with /mcp in Claude Code)"
  else
    warn "couldn't add the Figma MCP server; try: claude mcp add --transport http --scope user figma https://mcp.figma.com/mcp"
  fi
fi

if [ "$PULL_MODELS" = 1 ]; then
  if ! curl -fsS --max-time 3 "$LOOP_OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    open -a Ollama 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
      curl -fsS --max-time 2 "$LOOP_OLLAMA_URL/api/tags" >/dev/null 2>&1 && break
      sleep 2
    done
  fi
  pulled="$(ollama list 2>/dev/null | awk 'NR > 1 {print $1}' || true)"
  for pair in $LOOP_LOCAL_MODELS; do
    model="${pair#*=}"   # "name=tag" or a bare tag
    if printf '%s\n' "$pulled" | grep -qxF "$model"; then
      ok "$model already pulled"
    else
      say "  pulling $model (large: this takes a while)..."
      ollama pull "$model" && ok "$model"
    fi
  done
else
  say "  – local models not pulled (./install.sh --models pulls everything in LOOP_LOCAL_MODELS)"
fi


# -------------------------------------------------------------------------------------------------
cat <<EOF

==================================================
    GardenGnome Ecosystem Successfully Cultivated
==================================================

FINAL STEPS FOR SYSTEM LAUNCH:
--------------------------------------------------
1. Open a new terminal (or: source ~/.zshrc).
2. Open Google Chrome, log in, and add the 1Password extension from the Web Store.
3. Turn on Raycast and set it to replace Spotlight on Cmd+Space.
4. Sign in to each model CLI once, interactively:
     claude        (Anthropic)       codex login   (OpenAI)
     agy           (Gemini)          grok          (xAI, if installed)
     gh auth login (GitHub)
5. Check the AI toolchain:  ai-doctor        (add --live to ping every model)
   Add the loop to a repo:   init-loop <repo>  (--mode team to commit it for the whole team)
   Work accounts:            loop-profile new <company> --reviewers "..."  (then: login, use)
6. VS Code is for browsing code; drive changes with Claude Code or the other agents in Ghostty.
7. Right Option is remapped to F18 (Karabiner). MacWhisper is the first building block for a
   spoken -> agent workflow, but that pipeline (F18 -> dictation -> agent) still needs wiring up.
EOF
if [ -d "$BACKUP_DIR" ]; then
  echo
  echo "Files this run replaced are in $BACKUP_DIR"
fi
