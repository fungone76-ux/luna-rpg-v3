# 🚀 RunPod Setup Guide - Luna RPG v3

Guida completa per configurare ComfyUI su RunPod per la generazione immagini/video di Luna RPG.

---

## 📋 PREREQUISITI

- Account [RunPod](https://www.runpod.io/) con saldo positivo
- API Key di RunPod (da inserire nel file `.env`)

---

## 🖥️ CREAZIONE POD

### 1. Scegli Template
```
Community Cloud → PyTorch → pytorch-2.1.0-cuda-11.8-devel-ubuntu-22.04
```

### 2. Configura GPU
```
GPU: RTX 3090 (24GB) o superiore
VRAM: 24GB+ (richiesto per SDXL + ControlNet)
```

### 3. Storage
```
Container Disk: 50GB (sistema + modelli base)
Volume Disk: 100GB+ (modelli checkpoint, LoRA, output)
```

---

## 📦 INSTALLAZIONE COMFYUI

### 1. Clona Repository
```bash
cd /workspace
git clone https://github.com/comfyanonymous/ComfyUI.git
```

### 2. Crea Ambiente Virtuale Dedicato
```bash
cd /workspace
python -m venv venv_comfyui_dedicato
source venv_comfyui_dedicato/bin/activate

# Installa dipendenze
cd ComfyUI
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

### 3. Installa Nodi Aggiuntivi (Opzionale ma Consigliato)
```bash
cd /workspace/ComfyUI/custom_nodes

# ComfyUI-Manager (gestione nodi)
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# ComfyUI-ControlNet-Aux
pip install comfyui-controlnet-aux

# WAS Node Suite
pip install WAS-node-suite-comfyui
```

---

## 🤖 MODELLI DA SCARICARE

### 1. Checkpoint Principale (SDXL)
```bash
# Crea cartella
cd /workspace/ComfyUI/models/checkpoints

# Scarica Pony Diffusion V6 (o modello simile)
wget https://huggingface.co/AstraliteHeart/pony-diffusion-v6/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors
```

**Alternativa (consigliata per Luna RPG):**
```bash
# RealVisXL o simile photorealistic
wget https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors
```

### 2. LoRA Personaggi (OBBLIGATORIE)
```bash
cd /workspace/ComfyUI/models/loras

# Luna (stsDebbie)
wget https://civitai.com/api/download/models/12345 -O stsDebbie-10e.safetensors

# Stella (alice_milf_catchers)
wget https://civitai.com/api/download/models/67890 -O alice_milf_catchers_lora.safetensors

# Maria (stsSmith)
wget https://civitai.com/api/download/models/11111 -O stsSmith-10e.safetensors

# Expressive_H (stile)
wget https://civitai.com/api/download/models/22222 -O Expressive_H.safetensors

# FantasyWorldPonyV2 (stile)
wget https://civitai.com/api/download/models/33333 -O FantasyWorldPonyV2.safetensors
```

> ⚠️ **NOTA**: Sostituisci gli URL con quelli corretti da CivitAI o HuggingFace

### 3. ControlNet (Opzionale ma consigliato)
```bash
cd /workspace/ComfyUI/models/controlnet

# OpenPose per pose controllate
wget https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.pth

# Canny per lineart
wget https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_canny.pth
```

### 4. VAE (Variational AutoEncoder)
```bash
cd /workspace/ComfyUI/models/vae

# SDXL VAE
wget https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors
```

---

## 🎬 MODELLI VIDEO (Wan2.1 I2V) - OPZIONALE

Se vuoi generare anche video:

```bash
cd /workspace/ComfyUI/models/checkpoints

# Wan 2.1 I2V 480P
wget https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P/resolve/main/wan2.1_i2v_480p_14B_fp16.safetensors
```

---

## ⚙️ CONFIGURAZIONE

### 1. Avvia ComfyUI
```bash
# Usa lo script incluso nel progetto
cd /workspace/ComfyUI
source /workspace/venv_comfyui_dedicato/bin/activate
python main.py --listen 0.0.0.0 --port 8188
```

### 2. Verifica Connessione
```
Network: Container Port 8188 → HTTP 8188
```

### 3. Carica Workflow
Nel progetto Luna RPG c'è `workflow_image.json`. Caricalo in ComfyUI:
1. Apri ComfyUI nel browser (URL del pod)
2. Menu → Load → Scegli `workflow_image.json`
3. Verifica che tutti i nodi siano collegati correttamente

---

## 🔌 CONNESSIONE CON LUNA RPG

### 1. Ottieni ID Pod RunPod
Dalla dashboard RunPod, copia l'ID del pod (es: `cpc3l0m...`)

### 2. Configura Luna RPG
Nel file `.env` del progetto:
```env
EXECUTION_MODE=RUNPOD
RUNPOD_ID=il_tuo_pod_id
```

Oppure usa la UI di startup di Luna RPG:
- Spunta "Use RunPod (Cloud GPU)"
- Inserisci il Pod ID

### 3. Verifica Connessione
Avvia Luna RPG e prova a generare un'immagine. Se vedi:
```
[ComfyImage] Generating Luna...
[ComfyImage] Success!
```
Tutto funziona! 🎉

---

## 💾 BACKUP VOLUMI

### Salvare Modelli (Persistent Storage)
I modelli in `/workspace` persistono tra i restart del pod.

### Esportare Workflow
Salva il workflow modificato in ComfyUI:
- Menu → Export → Salva come JSON
- Copia nella cartella `luna-rpg-v3/` del tuo PC

---

## 🔧 TROUBLESHOOTING

### Errore: "CUDA out of memory"
```bash
# Riduci risoluzione nel workflow ComfyUI
# Da 896x1152 a 768x1024
```

### Errore: "LoRA not found"
Verifica che le LoRA siano in:
```
/workspace/ComfyUI/models/loras/
```

### Errore: "Connection refused"
Verifica che ComfyUI sia avviato:
```bash
ps aux | grep python
# Se non vedi ComfyUI, riavvialo
```

---

## 📊 COSTI STIMATI

| GPU | Costo/ora | Tempo generazione immagine | Costo/img |
|-----|-----------|---------------------------|-----------|
| RTX 3090 | $0.44 | ~5 secondi | ~$0.0006 |
| RTX 4090 | $0.69 | ~3 secondi | ~$0.0006 |
| A100 | $1.99 | ~2 secondi | ~$0.001 |

Sessione di gioco di 2 ore: ~**$0.50-1.00**

---

## ✅ CHECKLIST PRE-GIOCO

- [ ] Pod creato con GPU 24GB+
- [ ] ComfyUI clonato e installato
- [ ] Modello checkpoint scaricato (SDXL)
- [ ] LoRA personaggi scaricate (3 file)
- [ ] Workflow caricato in ComfyUI
- [ ] Pod ID inserito in Luna RPG
- [ ] Test generazione immagine riuscito

---

**Pronto per giocare!** 🎮🏖️
