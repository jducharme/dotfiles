# dotfiles: the GardenGnome Cultivator

Sets up JD's Mac. That includes the machine side of the agent loop: every model CLI installed and checked, the global Claude Code setup, and local models.

```bash
git clone git@github.com:jducharme/dotfiles.git ~/Workspace/dotfiles
cd ~/Workspace/dotfiles && ./install.sh            # add --models to pull local models, --grok for Grok Build
ai-doctor --live                                   # is every model installed, signed in and answering?
```

`install.sh` is safe to re-run. It checks before changing anything, and moves anything it replaces into `~/.dotfiles-backup/<timestamp>/`.

| Path | What | Ends up at |
|---|---|---|
| `install.sh` | The bootstrap: Homebrew, Brewfile, zsh, config links, AI toolchain | |
| `Brewfile` | Every app and CLI Homebrew installs. Add tools here | |
| `zsh/dotfiles.zsh` | Shell setup (PATH, starship, fnm, uv) | sourced from `~/.zshrc` |
| `karabiner/` | Right Option → F18 | `~/.config/karabiner` |
| `claude/CLAUDE.md` | How JD works with Claude Code in every repo: intent → spec → reviewed code | `~/.claude/CLAUDE.md` |
| `loop/` | **The agent loop itself**: the engine and `init-loop`, which adds it to any repo. See [`loop/README.md`](loop/README.md) | `~/.local/bin/init-loop` |
| `ai/defaults.sh` | Which model plays which role in the loop (author, spec reviewers, code reviewers, local model, tracker). A repo's `.agent-loop/config.sh` overrides it | `~/.config/agent-loop/defaults.sh` |
| `ai/profiles/personal.sh` | The default account profile. Other profiles (one per employer) are created by `loop-profile new` in `~/.config/agent-loop/profiles/`, outside this repo | `~/.config/agent-loop/profiles/` |
| `bin/loop-profile` | Account profiles: `new`, `login`, `use <name> <folder>` (direnv), `list`, status | `~/.local/bin/loop-profile` |
| `bin/ai-doctor` | Checks each model tool (claude, codex, gemini via agy, grok, local via Ollama) plus gh, the Figma MCP server and Orca | `~/.local/bin/ai-doctor` |
| `lib/common.sh` | Helpers for `install.sh` (linking with backups, `.zshrc` edits) | |

## How the AI pieces fit

- **This repo: the machine.** It installs and checks every model tool, sets the defaults, and manages account profiles.
- **`loop/`: the loop.** `init-loop <repo>` adds it to a repo, either committed for the team (`--mode team`) or hidden just for you (`local`, the default in a repo that doesn't have it yet).
- **Each repo: its own context.** `.agent-loop/config.sh` (reviewers, tests, approved models), `guard.sh`, and its specs.

**Work vs personal accounts.** Each model runs through its vendor's own CLI, because subscriptions only work there. Which account a CLI uses follows the folder:

```bash
loop-profile new acme --email jd@acme.com --reviewers "codex claude"   # the models acme approved
loop-profile login acme all          # its own Claude token, Codex login and GitHub login
loop-profile use acme ~/Work/acme    # every repo under ~/Work/acme now uses acme's accounts
```

direnv switches the environment whenever you `cd` into those folders. Claude Code, the loop's reviewers, `gh` and git commits all use that profile there. The loop refuses to send a repo's code through any other profile or any model the profile doesn't allow. Caveats:
- On macOS, Claude Code keeps one Keychain login per machine, so other profiles use a `claude setup-token` token. Never run `/login` in a work folder.
- agy (Gemini) has one machine-wide login. Leave gemini out of a work profile unless that employer gave you an API key.

To try a new model, install its CLI (Brewfile or `install.sh`), add a check to `bin/ai-doctor`, then add it to a repo as `LOOP_CMD_<name>` (or as a built-in in `loop/core/review.sh`).

## License

[PolyForm Noncommercial 1.0.0](LICENSE): free for personal, hobby, research and other noncommercial use, as long as the `Required Notice` line stays with every copy. Selling it, or using it in or for a for-profit business, needs a separate license from me.
