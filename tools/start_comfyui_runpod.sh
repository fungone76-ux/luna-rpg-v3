#!/bin/bash
# Comando per avviare ComfyUI su RunPod
# Usare nella console del pod RunPod

cd /workspace/ComfyUI
source /workspace/venv_comfyui_dedicato/bin/activate
python main.py --listen 0.0.0.0 --port 8188
