# Sourced from ~/.zshrc (install.sh adds the one line). Edit this file, not ~/.zshrc.
# --- GardenGnome toolchain initializers

typeset -U path
path=("$HOME/.local/bin" $path)        # ai-doctor, init-loop, loop-profile

# Account profile: personal by default. Folders set up with `loop-profile use` switch it through direnv.
[ -f "$HOME/.config/agent-loop/profiles/personal.sh" ] && source "$HOME/.config/agent-loop/profiles/personal.sh"
command -v direnv >/dev/null && eval "$(direnv hook zsh)"

# Starship modern prompt
command -v starship >/dev/null && eval "$(starship init zsh)"

# Fast Node Manager: switches Node version on cd
command -v fnm >/dev/null && eval "$(fnm env --use-on-cd)"

# uv completion
command -v uv >/dev/null && eval "$(uv generate-shell-completion zsh)"
