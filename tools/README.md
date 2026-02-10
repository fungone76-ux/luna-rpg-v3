# 🌙 Luna RPG v3

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/PySide6-6.6+-orange.svg)](https://wiki.qt.io/Qt_for_Python)

> **Visual Novel/RPG AI-driven** con generazione immagini in tempo reale e Quest System modulare.

![Screenshot Placeholder](docs/screenshot.png)

## ✨ Features

- 🤖 **Multi-Provider LLM**: Moonshot (primario) + Gemini (fallback)
- 🎨 **Generazione Immagini**: ComfyUI integrato (locale o RunPod cloud)
- 🎬 **Video Generation**: Wan2.1 I2V per video da immagini
- 📋 **Quest System v3**: State machine modulare da YAML
- 💝 **Personality System**: Stati emotivi dinamici per companion
- 🏆 **Milestones & Achievements**: Progressione relazionale
- 🔊 **Text-to-Speech**: Google TTS integrato
- 💾 **Save/Load**: Database SQLite con SQLAlchemy async

## 🚀 Quick Start

### Prerequisiti

- Python 3.11+
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (opzionale, per immagini) o account [RunPod](https://www.runpod.io/)
- API Keys: [Google AI Studio](https://aistudio.google.com/app/apikey) e/o [Moonshot AI](https://www.kimi.com/)

### Installazione

```bash
# Clona il repository
git clone https://github.com/tuousername/luna-rpg-v3.git
cd luna-rpg-v3

# Crea ambiente virtuale
python -m venv .venv

# Attiva ambiente virtuale
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Installa dipendenze
pip install -e .

# Configura variabili d'ambiente
copy .env.example .env
# Edita .env con le tue API keys
```

### Avvio

```bash
python main.py
```

## 🎮 Come Giocare

1. **Seleziona il Mondo**: Scegli tra i mondi disponibili (School Life, Fantasy Dark, Cyberpunk Noir)
2. **Scegli la Companion**: Ogni personaggio ha personalità, outfit e quest uniche
3. **Gioca**: Scrivi azioni in italiano, l'AI risponde e genera immagini
4. **Sblocca Contenuti**: Completa quest, aumenta affinità, scopri segreti

## 🗂️ Struttura Progetto

```
luna-rpg-v3/
├── main.py                 # Entry point
├── pyproject.toml          # Dipendenze
├── core/                   # Engine principale
│   ├── engine.py          # GameEngine orchestrator
│   ├── quest_engine.py    # Quest System v3
│   ├── database.py        # SQLAlchemy async
│   └── prompt_builders/   # Generatori prompt SD
├── media/                  # Client API esterni
│   ├── llm_client.py      # Multi-provider LLM
│   ├── comfy_image_client.py
│   └── video_client.py
├── ui/                     # Interfaccia PySide6
├── worlds/                 # Mondi di gioco (YAML)
│   ├── school_life.yaml
│   ├── fantasy_dark.yaml
│   └── cyberpunk_noir.yaml
├── prompts/               # System prompts LLM
└── storage/               # Dati utente (gitignored)
```

## 📝 Creare un Nuovo Mondo

I mondi sono definiti in YAML e sono **completamente intercambiabili**:

```yaml
meta:
  id: "my_world"
  name: "Il Mio Mondo"
  genre: "Fantasy"

companions:
  MiaCompanion:
    base_prompt: "score_9, masterpiece, <lora:MyLoRA:0.7>"
    default_outfit: "casual"
    wardrobe:
      casual: "wearing jeans and t-shirt"
      nude: "nude"
    personality_system:
      core_traits:
        role: "Adventurer"
      emotional_states:
        default:
          description: "Friendly and curious"

quests:
  my_quest:
    meta:
      title: "My First Quest"
      type: "main"
    stages:
      start:
        title: "The Beginning"
        narrative_prompt: "You meet her at the tavern..."
```

Salva in `worlds/my_world.yaml` e apparirà automaticamente nel menu!

## ⚙️ Configurazione

### Variabili d'ambiente (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `EXECUTION_MODE` | LOCAL o RUNPOD | LOCAL |
| `LLM_PROVIDER` | gemini o moonshot | gemini |
| `GEMINI_API_KEY` | API key Google | - |
| `MOONSHOT_API_KEY` | API key Moonshot | - |
| `RUNPOD_ID` | ID pod RunPod | - |

### ComfyUI (Locale)

Se usi ComfyUI in locale:
```bash
cd path/to/ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

Il gioco si connetterà automaticamente a `http://127.0.0.1:8188`.

## 🤝 Contributing

1. Fork il repository
2. Crea un branch (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📄 Licenza

Distribuito sotto licenza MIT. Vedi `LICENSE` per dettagli.

## 🙏 Crediti

- [Moonshot AI](https://www.kimi.com/) - LLM primario
- [Google Gemini](https://deepmind.google/technologies/gemini/) - LLM fallback
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Generazione immagini
- [PySide6](https://wiki.qt.io/Qt_for_Python) - UI Framework

---

<p align="center">Made with ❤️ and 🤖</p>
