# Everything install.sh installs with Homebrew. `brew bundle --file Brewfile` installs what's missing
# and is safe to re-run. Add a tool here, not in install.sh.

tap "stablyai/orca"

# --- Peripherals & hardware (the irrigation system)
cask "displaylink"                 # DisplayLink Manager for the multi-display Anker hub

# --- Virtualization (the greenhouse)
cask "docker"                      # Docker Desktop: local databases stay off the host

# --- Productivity, vaults & browser
cask "raycast"
cask "1password"
cask "1password-cli"
cask "google-chrome"
cask "notion"
cask "notion-calendar"

# --- AI coding agents & editor
cask "claude"                      # Claude desktop app
cask "claude-code"                 # claude: the loop's default author
cask "codex"                       # codex: OpenAI
cask "antigravity-cli"             # agy: Gemini (replaces the old gemini CLI)
cask "stablyai/orca/orca"          # Orca: agents across terminals & worktrees
cask "ollama"                      # local models (the loop's "local" reviewer)
cask "visual-studio-code"          # for browsing code; changes go through the agents
# Grok Build has no Homebrew package: `./install.sh --grok` runs xAI's installer.

# --- Terminal, DB & prompt
cask "ghostty"
cask "tableplus"
brew "starship"
brew "direnv"                      # switches account profiles per folder (loop-profile use)

# --- Language runtimes (the high-speed Rust stack)
brew "fnm"                         # Node versions
brew "uv"                          # Python
brew "node"
brew "python@3.14"

# --- Dev CLIs
brew "gh"
cask "gcloud-cli"

# --- Local automation (the little helper)
cask "macwhisper"
cask "karabiner-elements"

# --- Work & comms
cask "slack"
cask "linear-linear"               # Linear (the old "linear" cask is disabled)
cask "zoom"
cask "whatsapp"

# --- Personal
cask "spotify"
cask "steam"
