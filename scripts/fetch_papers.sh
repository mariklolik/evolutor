#!/usr/bin/env bash
# Download research papers from arXiv
set -euo pipefail

PAPERS_DIR="${1:-/home/mekashirskiy/papers}"
mkdir -p "$PAPERS_DIR"

echo "Downloading papers into $PAPERS_DIR ..."

# Papers related to self-improving agents and coding agent research
curl -L "https://arxiv.org/pdf/2505.22954" -o "$PAPERS_DIR/dgm.pdf"             &  # Darwin Godel Machine
curl -L "https://arxiv.org/pdf/2504.15228" -o "$PAPERS_DIR/sica.pdf"            &  # Self-Improving Coding Agent
curl -L "https://arxiv.org/pdf/2510.21614" -o "$PAPERS_DIR/hgm.pdf"             &  # Hierarchical Godel Machine
curl -L "https://arxiv.org/pdf/2511.13646" -o "$PAPERS_DIR/live_swe_agent.pdf"  &  # Live SWE-agent
curl -L "https://arxiv.org/pdf/2602.16891" -o "$PAPERS_DIR/opensage.pdf"        &  # OpenSAGE
curl -L "https://arxiv.org/pdf/2511.05931" -o "$PAPERS_DIR/sage_abstraction.pdf" & # SAGE Abstraction

wait
echo "All papers downloaded."
ls -lh "$PAPERS_DIR/"
