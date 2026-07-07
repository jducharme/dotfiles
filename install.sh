#!/bin/bash

# --- The GardenGnome Cultivator ---
# Chrome Edition: Multi-Display, Docker, Rust Runtimes, & Secure Vaults
set -e

echo "🌱 Tilling the soil and preparing the environment..."

# 1. Root Package Management
if ! command -v brew &>/dev/null; then
    echo "🧑‍🌾 Installing Homebrew (The Foundation)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "✨ Foundation already secure."
fi

echo "🔄 Fetching the latest package blueprints..."
brew update

# 2. Peripherals & Hardware (The Irrigation System)
echo "🖥️ Deploying DisplayLink Manager for Multi-Display Anker Hub..."
brew tap wwmoraes/tap
brew install --cask wwmoraes/tap/displaylink-manager

# 3. Virtualization Infrastructure (The Greenhouse)
echo "🐳 Deploying Docker Desktop (Keeping local databases off the host system)..."
brew install --cask docker

# 4. Productivity Frameworks, Secure Vaults, & Chrome
echo "🚀 Seeding Raycast, 1Password, & Google Chrome..."
brew install --cask raycast
brew install --cask 1password
brew install --cask 1password-cli
brew install --cask google-chrome

# 5. Interface, Terminal & DB Utilities
echo "⚡ Planting Ghostty Terminal, TablePlus, & Starship Prompts..."
brew install --cask ghostty
brew install --cask tableplus
brew install starship

# 6. Language Runtimes (The High-Speed Rust Stack)
echo "🦀 Installing fnm (Node) and uv (Python)..."
brew install fnm
brew install uv

# 7. Local Automation Layer (The Little Helper)
echo "🤖 Setting up Ollama, MacWhisper, and Karabiner-Elements..."
brew install --cask ollama
brew install --cask macwhisper
brew install --cask karabiner-elements

# 8. Shell Optimization & Oh-My-Zsh
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "🐚 Tending to the Zsh Shell layout..."
    RUNZSH=no CHSH=no /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
else
    echo "✨ Zsh shell layout is already configured."
fi

# 9. Writing Modern Shell Initializations directly to .zshrc
echo "📝 Injecting high-speed tool configurations into ~/.zshrc..."
cat << 'EOF' >> "$HOME/.zshrc"

# --- GardenGnome Toolchain Initializers ---
# Starship Modern Prompt
eval "$(starship init zsh)"

# Fast Node Manager - Instant execution, auto-switches version on directory change
eval "$(fnm env --use-on-cd)"

# Enable uv autocompletion
eval "$(uv generate-shell-completion zsh)"
EOF

# 10. Automated Keyboard Rebinding (Right Option Hardware Hack)
echo "⌨️ Provisioning Karabiner-Elements Keymaps..."
KARABINER_DIR="$HOME/.config/karabiner"
mkdir -p "$KARABINER_DIR"

cat <<EOF > "$KARABINER_DIR/karabiner.json"
{
  "profiles": [
    {
      "name": "GardenGnome Intercom Profile",
      "selected": true,
      "simple_modifications": [
        {
          "from": { "key_code": "right_option" },
          "to": [ { "key_code": "f18" } ]
        }
      ]
    }
  ]
}
EOF

echo "=================================================="
echo "    GardenGnome Ecosystem Successfully Cultivated "
echo "=================================================="
echo ""
echo "FINAL STEPS FOR SYSTEM LAUNCH:"
echo "--------------------------------------------------"
echo "1. Run: source ~/.zshrc to balance the shell environment."
echo "2. Open Google Chrome, log in, and download the 1Password Extension from the Web Store."
echo "3. Turn on Raycast and set it to replace default Cmd+Space Spotlight."
echo "4. Hold Right Option and dictate your first mission to Antigravity inside Ghostty."
echo ""
