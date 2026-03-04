#!/usr/bin/env bash
# Start local vLLM inference stack on 8x H100 GPUs
# Primary: Qwen3-Coder-30B-FP8 (GPU 0-3, tensor_parallel=4) → quality mutations
# Secondary: Qwen3-8B (GPU 4) → fast cascade filter, cheap evals

VENV="/home/mekashirskiy/llm-evaluation/llm-eval"
HF_HOME="/home/mekashirskiy/.cache/huggingface"

echo "[vllm] Starting primary model (Qwen3-Coder-30B-FP8) on GPU 0-3..."
CUDA_VISIBLE_DEVICES=0,1,2,3 \
HF_HOME="$HF_HOME" \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
  $VENV/bin/python -m vllm.entrypoints.openai.api_server \
  --model "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8" \
  --tensor-parallel-size 4 \
  --max-model-len 32768 \
  --port 8000 \
  --host 0.0.0.0 \
  --enable-prefix-caching \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.88 \
  --served-model-name "qwen3-coder-30b" \
  --trust-remote-code \
  2>/tmp/vllm_primary.log &
PRIMARY_PID=$!
echo $PRIMARY_PID >> /tmp/evolutor_pids.txt
echo "[vllm] Primary PID=$PRIMARY_PID"

echo "[vllm] Starting secondary model (Qwen3-8B) on GPU 4..."
CUDA_VISIBLE_DEVICES=4 \
HF_HOME="$HF_HOME" \
  $VENV/bin/python -m vllm.entrypoints.openai.api_server \
  --model "Qwen/Qwen3-8B" \
  --tensor-parallel-size 1 \
  --max-model-len 16384 \
  --port 8001 \
  --host 0.0.0.0 \
  --gpu-memory-utilization 0.85 \
  --served-model-name "qwen3-8b" \
  --trust-remote-code \
  2>/tmp/vllm_secondary.log &
SECONDARY_PID=$!
echo $SECONDARY_PID >> /tmp/evolutor_pids.txt
echo "[vllm] Secondary PID=$SECONDARY_PID"

# Wait for primary to be ready (can take 60-90s for model loading)
echo "[vllm] Waiting for models to load (up to 120s)..."
for i in $(seq 1 24); do
  sleep 5
  if curl -s --max-time 2 http://localhost:8000/health > /dev/null 2>&1; then
    echo "[vllm] PRIMARY READY after ${i}x5=${i*5}s"
    break
  fi
  echo "[vllm] Waiting... ($((i*5))s)"
done

if curl -s --max-time 2 http://localhost:8001/health > /dev/null 2>&1; then
  echo "[vllm] SECONDARY READY"
fi

echo "[vllm] Models status:"
curl -s http://localhost:8000/v1/models 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  {m[\"id\"]}') for m in d.get('data',[])]" 2>/dev/null || echo "  primary not responding yet"
