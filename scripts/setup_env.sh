#!/usr/bin/env bash
# PERMANENTLY disable paid APIs — ALL calls go to local vLLM only
unset ANTHROPIC_API_KEY
unset OPENAI_API_KEY
export ANTHROPIC_API_KEY="local-vllm-PAID-API-DISABLED-$(hostname)"
export OPENAI_API_KEY="local-vllm-PAID-API-DISABLED"
export ANTHROPIC_BASE_URL="http://localhost:4000"
export OPENAI_BASE_URL="http://localhost:8000/v1"
export EVOLUTOR_MODEL="claude-sonnet-4-6"
export EVOLUTOR_PROJECT_ROOT="/home/mekashirskiy/evolutor"
export HF_HOME="/home/mekashirskiy/.cache/huggingface"
export CUDA_VISIBLE_DEVICES_VLLM_PRIMARY="0,1,2,3"
export CUDA_VISIBLE_DEVICES_VLLM_SECONDARY="4"
# Critical: bypass system HTTP_PROXY for all local vLLM calls
export no_proxy="localhost,127.0.0.1,0.0.0.0,::1"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
echo "[setup_env] Paid API neutralized. ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
echo "[setup_env] no_proxy=$no_proxy (bypasses system proxy for local LLM)"
