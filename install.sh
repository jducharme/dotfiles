# First we install homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Disable Mac hot corner b=bottom t=top l=left r=right
defaults write com.apple.dock wvous-tl-corner -int 0
defaults write com.apple.dock wvous-tr-corner -int 0
defaults write com.apple.dock wvous-bl-corner -int 0
defaults write com.apple.dock wvous-br-corner -int 0

# Install Cask
brew install --cask iterm2
brew install --cask google-chrome
brew install --cask slack
brew install --cask alfred alfred
brew install --cask visual-studio-code
brew install --cask docker
brew install --cask 1password

# Install command line tools
brew install rbenv
brew install npm
brew install awscli

# Install OhMyZsh
sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
