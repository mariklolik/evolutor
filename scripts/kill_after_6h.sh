#!/usr/bin/env bash
# 6-hour safety kill — started at $(date)
START=$(date +%s)
echo "KILL MONITOR STARTED: $(date) PID=$$" >> /tmp/evolutor.log
sleep 21600
echo "6h LIMIT REACHED: killing all Evolutor processes $(date)" >> /tmp/evolutor.log
# Kill our processes
cat /tmp/evolutor_pids.txt 2>/dev/null | while read p; do kill -SIGTERM "$p" 2>/dev/null; done
pkill -f "vllm serve" 2>/dev/null || true
pkill -f "vllm.entrypoints" 2>/dev/null || true
pkill -f "litellm" 2>/dev/null || true
pkill -f "run_overnight" 2>/dev/null || true
pkill -f "evolutor evolve" 2>/dev/null || true
echo "KILL COMPLETE: $(date)" >> /tmp/evolutor.log
