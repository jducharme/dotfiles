# shellcheck shell=bash
# Helpers shared by install.sh. Portable to macOS's bash 3.2.

DOTFILES="${DOTFILES:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)}"

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

# backup <path>: move it into this run's backup folder, keeping its path under $HOME.
backup() {
  local src="$1" rel dest
  rel="${src#"$HOME"/}"
  dest="$BACKUP_DIR/$rel"
  mkdir -p "$(dirname "$dest")"
  mv "$src" "$dest"
  warn "moved the existing $src to $dest"
}

# link <path in this repo> <target>: make target a symlink to the repo copy. Whatever was there
# before is backed up first, so nothing is lost. Safe to re-run.
link() {
  local src="$DOTFILES/$1" dest="$2"
  [ -e "$src" ] || { warn "missing $src"; return 1; }
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    ok "$dest"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ] || [ -L "$dest" ]; then backup "$dest"; fi
  ln -s "$src" "$dest"
  ok "$dest -> $src"
}

# migrate_zshrc <rc>: earlier versions of install.sh appended a "GardenGnome Toolchain Initializers"
# block to ~/.zshrc on every run. Remove every copy (they now live in zsh/dotfiles.zsh). Only blank
# lines, comments and the three known eval lines are removed; anything else ends the block.
migrate_zshrc() {
  local rc="$1" marker="# --- GardenGnome Toolchain Initializers ---"
  [ -f "$rc" ] && grep -qF "$marker" "$rc" || return 0
  mkdir -p "$BACKUP_DIR"
  cp "$rc" "$BACKUP_DIR/.zshrc"
  awk -v m="$marker" '
    $0 == m { skip = 1; next }
    skip && ($0 ~ /^[[:space:]]*$/ || $0 ~ /^#/ ||
             index($0, "eval \"$(starship init zsh)\"") == 1 ||
             index($0, "eval \"$(fnm env") == 1 ||
             index($0, "eval \"$(uv generate-shell-completion") == 1) { next }
    { skip = 0; print }
  ' "$rc" > "$rc.dotfiles-tmp"
  mv "$rc.dotfiles-tmp" "$rc"
  warn "removed the old GardenGnome block(s) from $rc (copy in $BACKUP_DIR/.zshrc)"
}

# source_line <rc> <file>: make sure rc sources file, exactly once.
source_line() {
  local rc="$1" file="$2"
  touch "$rc"
  if grep -qF "$file" "$rc"; then
    ok "$rc sources $file"
  else
    printf '\n# dotfiles: everything else lives in this file\n[ -f "%s" ] && source "%s"\n' "$file" "$file" >> "$rc"
    ok "$rc now sources $file"
  fi
}
