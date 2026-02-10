#!/bin/bash
# Script di verifica file ComfyUI per Luna RPG v3
# Eseguire in: /workspace/ComfyUI

echo "=========================================="
echo "🔍 LUNA RPG v3 - ComfyUI File Check"
echo "=========================================="
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contatori
FOUND=0
MISSING=0
WARNINGS=0

# Funzione per verificare file
check_file() {
    local path=$1
    local name=$2
    local required=$3
    
    if [ -f "$path" ]; then
        size=$(du -h "$path" | cut -f1)
        echo -e "${GREEN}✅${NC} $name (${size})"
        ((FOUND++))
    else
        if [ "$required" = "required" ]; then
            echo -e "${RED}❌${NC} $name - MANCANTE (Obbligatorio)"
            ((MISSING++))
        else
            echo -e "${YELLOW}⚠️${NC} $name - Mancante (Opzionale)"
            ((WARNINGS++))
        fi
    fi
}

# Funzione per verificare cartella
check_dir() {
    local path=$1
    local name=$2
    
    if [ -d "$path" ]; then
        count=$(find "$path" -type f | wc -l)
        echo -e "${GREEN}📁${NC} $name (${count} files)"
    else
        echo -e "${RED}📁${NC} $name - Cartella non esiste!"
        ((MISSING++))
    fi
}

echo "📂 STRUTTURA CARTELLE"
echo "---------------------"
check_dir "/workspace/ComfyUI" "ComfyUI Root"
check_dir "/workspace/ComfyUI/models" "Models"
check_dir "/workspace/ComfyUI/models/checkpoints" "Checkpoints"
check_dir "/workspace/ComfyUI/models/loras" "LoRAs"
check_dir "/workspace/ComfyUI/models/vae" "VAE"
check_dir "/workspace/ComfyUI/models/clip" "CLIP (per video)"
check_dir "/workspace/ComfyUI/models/diffusers" "Diffusers/Unet"
check_dir "/workspace/ComfyUI/models/controlnet" "ControlNet"
check_dir "/workspace/ComfyUI/input" "Input (immagini sorgente)"
check_dir "/workspace/ComfyUI/output" "Output (risultati)"
echo ""

echo "🤖 CHECKPOINT (Modelli Base) - Scegli almeno uno"
echo "------------------------------------------------"
check_file "/workspace/ComfyUI/models/checkpoints/ponyDiffusionV6XL_v6.safetensors" "Pony Diffusion V6" "required"
check_file "/workspace/ComfyUI/models/checkpoints/ponyDiffusionV6XL_v6StartWithThisOne.safetensors" "Pony Diffusion V6 Start" "required"
check_file "/workspace/ComfyUI/models/checkpoints/RealVisXL_V4.0.safetensors" "RealVisXL V4.0" "optional"
check_file "/workspace/ComfyUI/models/checkpoints/SDXL_base.safetensors" "SDXL Base" "optional"
echo ""

echo "👤 LORA PERSONAGGI (Obbligatori)"
echo "---------------------------------"
check_file "/workspace/ComfyUI/models/loras/stsDebbie-10e.safetensors" "Luna (stsDebbie)" "required"
check_file "/workspace/ComfyUI/models/loras/alice_milf_catchers_lora.safetensors" "Stella (Alice)" "required"
check_file "/workspace/ComfyUI/models/loras/stsSmith-10e.safetensors" "Maria (stsSmith)" "required"
echo ""

echo "🎨 LORA STILI (Consigliati)"
echo "---------------------------"
check_file "/workspace/ComfyUI/models/loras/Expressive_H.safetensors" "Expressive H (stile)" "optional"
check_file "/workspace/ComfyUI/models/loras/Expressive_H-000001.safetensors" "Expressive H v2" "optional"
check_file "/workspace/ComfyUI/models/loras/FantasyWorldPonyV2.safetensors" "Fantasy World Pony" "optional"
check_file "/workspace/ComfyUI/models/loras/FantasyWorldPony.safetensors" "Fantasy World" "optional"
echo ""

echo "🎬 VIDEO (Wan2.1 I2V) - Opzionale per video"
echo "--------------------------------------------"
check_file "/workspace/ComfyUI/models/clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors" "UMT5 XXL CLIP" "optional"
check_file "/workspace/ComfyUI/models/vae/wan_2.1_vae.safetensors" "Wan 2.1 VAE" "optional"
check_file "/workspace/ComfyUI/models/unet/Wan2.1-I2V-14B-480P-Q5_K_M.gguf" "Wan 480P (GGUF)" "optional"
check_file "/workspace/ComfyUI/models/unet/Wan2.1-I2V-14B-720P-Q5_K_M.gguf" "Wan 720P (GGUF)" "optional"
check_file "/workspace/ComfyUI/models/diffusers/Wan2.1-I2V-14B-480P.safetensors" "Wan 480P (Full)" "optional"
check_file "/workspace/ComfyUI/models/checkpoints/wan_2.1_i2v_480p_14B.safetensors" "Wan Checkpoint" "optional"
echo ""

echo "🎨 VAE"
echo "------"
check_file "/workspace/ComfyUI/models/vae/sdxl_vae.safetensors" "SDXL VAE" "optional"
check_file "/workspace/ComfyUI/models/vae/vae-ft-mse-840000-ema-pruned.safetensors" "VAE FT MSE" "optional"
echo ""

echo "🎮 CONTROLNET (Opzionale)"
echo "-------------------------"
check_file "/workspace/ComfyUI/models/controlnet/control_v11p_sd15_openpose.pth" "OpenPose" "optional"
check_file "/workspace/ComfyUI/models/controlnet/control_v11p_sd15_canny.pth" "Canny" "optional"
check_file "/workspace/ComfyUI/models/controlnet/control_v11f1p_sd15_depth.pth" "Depth" "optional"
echo ""

echo "📋 WORKFLOW"
echo "-----------"
check_file "/workspace/ComfyUI/workflow_image.json" "Workflow Immagini" "optional"
check_file "/workspace/ComfyUI/workflow_video.json" "Workflow Video" "optional"
check_file "/workspace/ComfyUI/user/default/workflows/workflow_image.json" "Workflow User" "optional"
echo ""

echo "=========================================="
echo "📊 RIEPILOGO"
echo "=========================================="
echo -e "File trovati: ${GREEN}$FOUND${NC}"
echo -e "File mancanti obbligatori: ${RED}$MISSING${NC}"
echo -e "File opzionali mancanti: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $MISSING -eq 0 ]; then
    echo -e "${GREEN}✅ Tutti i file obbligatori sono presenti!${NC}"
    echo "Pronto per generare immagini con Luna RPG!"
    exit 0
else
    echo -e "${RED}❌ Mancano file obbligatori!${NC}"
    echo "Scarica i file mancanti prima di iniziare."
    exit 1
fi
