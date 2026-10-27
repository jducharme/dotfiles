# shellcheck shell=bash
# Machine-wide defaults for the agent loop (intent → spec → review → build → review).
# Linked to ~/.config/agent-loop/defaults.sh. A repo's .agent-loop/config.sh overrides any of these.
# Sourced by bash 3.2: plain assignments only, lists are space-separated.
#
# Model names used everywhere in the loop:
#   claude  Claude Code (`claude`)        codex   OpenAI (`codex`)
#   gemini  Antigravity CLI (`agy`)        grok    xAI Grok Build (`grok`, install.sh --grok)
#   local/<name>  a model on Ollama on this Mac (see LOOP_LOCAL_MODELS below)
#
# init-loop copies LOOP_REVIEWERS into a new repo's config (narrowed to what the active profile
# allows). ai-doctor reads all of these to know which tools must be ready.
# shellcheck disable=SC2034  # read by the files that source this one

LOOP_AUTHOR="claude"                    # writes the spec, builds, triages findings
LOOP_SPEC_REVIEWERS="gemini"            # review the spec before anything is built (a repo can set its own)
LOOP_REVIEWERS="gemini"                 # review the code; e.g. "local/qwen gemini codex"

# Local models on Ollama: "name=ollama-tag", space-separated. Use each one anywhere as local/<name>
# (LOOP_REVIEWERS="local/qwen local/deepseek gemini"). An Ollama tag also works directly
# (local/deepseek-r1:32b), and plain `local` means the first one here. `install.sh --models` pulls
# them all, `ai-doctor` checks them. A repo can add its own in .agent-loop/config.sh.
# Local reviewers run one at a time, so several big models are fine on 48 GB.
LOOP_LOCAL_MODELS="qwen=qwen3.6:35b-a3b"
# e.g. LOOP_LOCAL_MODELS="qwen=qwen3.6:35b-a3b deepseek=deepseek-r1:32b coder=qwen3-coder:30b"
LOOP_OLLAMA_URL="http://127.0.0.1:11434"

LOOP_TRACKER="none"                     # none = flat files only; later: github | linear | notion
