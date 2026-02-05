# LUNA RPG v3

Rivisitazione moderna e async del motore RPG AI-driven.

## 🚀 Novità rispetto a v2

- **Architettura Async**: Usa `asyncio` + `qasync` per UI reattiva
- **SceneAnalyzer**: LLM capisce semanticamente chi deve essere nell'immagine
- **Anti-Fusion System**: Prompt negativi avanzati per scene multi-personaggio
- **Database SQLite**: Persistenza robusta con SQLAlchemy async
- **Pydantic Models**: Type safety e validazione automatica
- **Memory Management**: Compressione automatica history con summarization

## 📁 Struttura

```
luna-rpg-v3/
├── core/               # Engine principale
│   ├── engine.py       # Orchestratore
│   ├── scene_analyzer.py   # Analisi semantica LLM
│   ├── prompt_builders/    # Builder SD (single/multi/npc)
│   ├── state_manager.py    # Persistenza DB
│   └── memory_manager.py   # Gestione memoria
├── media/              # Client API
│   ├── llm_client.py   # Google Gemini
│   ├── image_client.py # Stable Diffusion
│   ├── audio_client.py # Google TTS
│   └── video_client.py # ComfyUI/Wan2.1
├── ui/                 # Interfaccia PySide6
├── worlds/             # File YAML mondi
└── prompts/            # System prompts
```

## ⚙️ Setup

```bash
# Crea venv
python -m venv .venv
.venv\Scripts\activate

# Installa
pip install -e .

# Configura
# Copia .env da v2 o crea nuovo:
# GEMINI_API_KEY=xxx
# EXECUTION_MODE=LOCAL

# Avvia
python main.py
```

## 🎮 Flusso Immagine Multi-Personaggio

1. **Narrativa**: "Guardo Luna sedersi vicino a Stella"
2. **SceneAnalyzer**: Capisce che Luna è il focus, Stella è solo contesto
3. **SingleCharacterBuilder**: Genera solo Luna nel prompt
4. **Se** la narrativa fosse "Luna e Stella si abbracciano"
5. **MultiCharacterBuilder**: Combinazione con:
   - BREAK token tra personaggi
   - Tag differenziazione ("different hair color")
   - Negative anti-fusion ("no twins, no same face")
