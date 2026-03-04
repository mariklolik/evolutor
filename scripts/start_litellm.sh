#!/usr/bin/env bash
# Start LiteLLM proxy: accepts Anthropic /v1/messages → forwards to vLLM OpenAI /v1/chat/completions
# This means zero code changes to existing orchestrator (planner/worker/critic use anthropic SDK)

CONFIG="/home/mekashirskiy/evolutor/litellm_config.yaml"

echo "[litellm] Starting proxy on port 4000..."
python3 -m litellm --config "$CONFIG" --port 4000 --host 0.0.0.0 \
  2>/tmp/litellm.log &
LLM_PID=$!
echo $LLM_PID >> /tmp/evolutor_pids.txt
echo "[litellm] PID=$LLM_PID"

sleep 8
if curl -s --max-time 3 http://localhost:4000/health > /dev/null 2>&1; then
  echo "[litellm] READY"
else
  echo "[litellm] Not responding yet — check /tmp/litellm.log"
fi
