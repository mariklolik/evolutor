#!/usr/bin/env bash
# Clone all competitor repositories (shallow, latest commit only)
set -euo pipefail

COMPETITORS_DIR="${1:-/home/mekashirskiy/competitors}"
mkdir -p "$COMPETITORS_DIR"

echo "Cloning competitor repos into $COMPETITORS_DIR ..."

git clone --depth=1 https://github.com/jennyzzt/dgm                              "$COMPETITORS_DIR/dgm" &
git clone --depth=1 https://github.com/MaximeRobeyns/self_improving_coding_agent  "$COMPETITORS_DIR/self_improving_coding_agent" &
git clone --depth=1 https://github.com/metauto-ai/HGM                             "$COMPETITORS_DIR/HGM" &
git clone --depth=1 https://github.com/codelion/openevolve                        "$COMPETITORS_DIR/openevolve" &
git clone --depth=1 https://github.com/SWE-agent/mini-swe-agent                   "$COMPETITORS_DIR/mini-swe-agent" &
git clone --depth=1 https://github.com/SWE-agent/SWE-agent                        "$COMPETITORS_DIR/SWE-agent" &
git clone --depth=1 https://github.com/All-Hands-AI/OpenHands                     "$COMPETITORS_DIR/OpenHands" &
git clone --depth=1 https://github.com/princeton-nlp/SWE-bench                    "$COMPETITORS_DIR/SWE-bench" &

wait
echo "All repos cloned successfully."
ls "$COMPETITORS_DIR/"
