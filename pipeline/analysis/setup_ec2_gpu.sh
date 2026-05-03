#!/usr/bin/env bash
# Bootstrap script: install CUDA 12.x + PyTorch CUDA wheels on Ubuntu 24.04 EC2
#
# Run once after first SSH into a fresh Ubuntu 24.04 instance:
#   bash ~/marine_risk_mapping/pipeline/analysis/setup_ec2_gpu.sh
#
# Or via the remote launcher:
#   uv run python pipeline/analysis/train_arcface_remote.py \
#       --prepare-command "bash ~/marine_risk_mapping/pipeline/analysis/setup_ec2_gpu.sh" \
#       ...
#
# What this does:
#   1.  Installs CUDA 12.4 toolkit + drivers (Ubuntu 24.04 keyring package from NVIDIA).
#   2.  Installs uv (Astral) if not already present.
#   3.  Runs `uv sync` in the project directory to install all Python deps.
#   4.  Reinstalls torch + torchvision from the PyTorch CUDA 12.4 index,
#       replacing the CPU-only wheels that uv pulled from PyPI.
#
# After this script completes the VM is ready for:
#   uv run python pipeline/analysis/train_arcface_classifier.py
#
# Expected instance: g4dn.xlarge (T4, 16 GB VRAM) or p3.2xlarge (V100, 16 GB VRAM)
# Estimated runtime: ~8 min (mostly CUDA package download)

set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-$HOME/marine_risk_mapping}"
CUDA_VERSION="12-4"           # NVIDIA repo package suffix (12-4 = 12.4.x)
TORCH_CUDA_TAG="cu124"        # torch index tag matching CUDA 12.4
TORCH_VERSION="2.10.0"        # must satisfy pyproject.toml: torch>=2.10.0
TORCHVISION_VERSION="0.25.0"  # matches torch 2.10 release

echo "=== [1/4] Installing CUDA ${CUDA_VERSION} toolkit ==="

# Add NVIDIA package repository for Ubuntu 24.04 (noble)
wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
    -O /tmp/cuda-keyring.deb
sudo dpkg -i /tmp/cuda-keyring.deb
rm /tmp/cuda-keyring.deb
sudo apt-get update -qq

# Install toolkit + driver (open kernel module for modern instances like g4dn/p3)
sudo apt-get install -y \
    "cuda-toolkit-${CUDA_VERSION}" \
    "cuda-drivers" \
    --no-install-recommends

# Persist CUDA paths across sessions
CUDA_PATH_LINE='export PATH=/usr/local/cuda/bin:$PATH'
LIB_PATH_LINE='export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}'
for LINE in "$CUDA_PATH_LINE" "$LIB_PATH_LINE"; do
    grep -qxF "$LINE" ~/.bashrc || echo "$LINE" >> ~/.bashrc
done
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}

echo "CUDA toolkit installed: $(nvcc --version 2>/dev/null | head -1 || echo 'reboot may be required for full driver load')"

echo ""
echo "=== [2/4] Installing uv ==="
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo ""
echo "=== [3/4] Running uv sync in ${REMOTE_DIR} ==="
cd "$REMOTE_DIR"
uv sync

echo ""
echo "=== [4/4] Reinstalling torch + torchvision with CUDA ${TORCH_CUDA_TAG} wheels ==="
# uv sync will have installed CPU-only torch from PyPI.
# We replace them with CUDA wheels from the official PyTorch index.
TORCH_INDEX="https://download.pytorch.org/whl/${TORCH_CUDA_TAG}"

uv pip install \
    "torch==${TORCH_VERSION}+${TORCH_CUDA_TAG}" \
    "torchvision==${TORCHVISION_VERSION}+${TORCH_CUDA_TAG}" \
    --index-url "$TORCH_INDEX" \
    --index-strategy unsafe-best-match

echo ""
echo "=== Verifying GPU visibility ==="
uv run python - << 'PYEOF'
import torch
print(f"torch  : {torch.__version__}")
print(f"CUDA   : {torch.version.cuda}")
print(f"GPUs   : {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"Device : {torch.cuda.get_device_name(0)}")
    print("GPU is READY.")
else:
    print("WARNING: CUDA not available — check driver installation.")
PYEOF

echo ""
echo "=== Setup complete. Run training with: ==="
echo "   uv run python pipeline/analysis/train_arcface_classifier.py"
