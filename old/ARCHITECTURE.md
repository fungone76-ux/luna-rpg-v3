# LUNA RPG v3 - Architettura Completa

> File generato il 2026-02-01 - Riassunto dell'architettura completa del gioco

---

## 📁 Struttura Progetto

```
LUNA RPG v3/
├── main.py                    # Entry point (PySide6 + qasync)
├── config/
│   └── settings.py            # Pydantic Settings (.env + user_prefs.json)
├── core/                      # BUSINESS LOGIC
│   ├── engine.py              # Orchestratore principale
│   ├── models.py              # Pydantic Models (type-safe)
│   ├── database.py            # SQLAlchemy Async (SQLite)
│   ├── state_manager.py       # Persistenza stato gioco
│   ├── memory_manager.py      # Gestione memoria/contesto LLM
│   ├── scene_analyzer.py      # Analisi semantica scene (LLM)
│   ├── world_loader.py        # Caricamento YAML mondi
│   └── prompt_builders/       # Costruttori prompt SD
│       ├── base.py            # Costanti BASE_PROMPTS (INVARIATI)
│       ├── single_builder.py  # 1 personaggio
│       ├── multi_builder.py   # 2+ personaggi (anti-fusion)
│       └── npc_builder.py     # NPC generici
├── media/                     # CLIENTS ESTERNI
│   ├── llm_client.py          # Google Gemini (narrativa)
│   ├── image_client.py        # Stable Diffusion API
│   ├── audio_client.py        # Google Cloud TTS
│   └── video_client.py        # ComfyUI/Wan2.1 I2V
├── ui/                        # INTERFACCIA
│   ├── main_window.py         # Finestra principale
│   └── startup_dialog.py      # Setup mondo/companion
├── prompts/                   # PROMPT ENGINEERING
│   ├── system_prompt.txt      # Istruzioni narrativa + JSON spec
│   ├── system_prompt_compact.txt  # Versione ridotta
│   └── visual_director.txt    # Specifiche tecniche SD
└── worlds/                    # DATI DI GIOCO (YAML)
    ├── school_life.yaml
    ├── fantasy_dark.yaml
    └── cyberpunk_noir.yaml
```

---

## 🔄 Flusso di Gioco Completo

### 1. Inizializzazione
```
main.py → QEventLoop → MainWindow → _delayed_init() → _async_init()
    ↓
1. Initialize DB (create_tables)
2. StartupDialog (selezione mondo/companion/RunPod)
3. Se RunPod: ricrea ImageClient/VideoClient
4. Engine.create_game() → StateManager + MemoryManager
5. _process_turn(is_intro=True) → Inizio gioco
```

### 2. Processo Turno (`engine.process_turn()`)
```
User Input
    ↓
1. BUILD SYSTEM PROMPT (system_prompt.txt + visual_director.txt)
    ↓
2. RECUPERA MEMORIA (facts + summaries + recent history)
    ↓
3. CHIAMA LLM (gemini-3-pro-preview)
    ↓
4. SALVA MESSAGGI in DB
    ↓
5. AGGIORNA STATO (location, outfit, affinity, flags)
    ↓
6. SCENE ANALYSIS (primary/secondary subjects)
    ↓
7. SWITCH COMPANION (se necessario)
    ↓
8. GENERA IMMAGINE (Single/Multi/NPC builder)
    ↓
9. AUDIO TTS (se abilitato)
    ↓
UI Update (testo → immagine → audio)
```

---

## 🎨 Prompt Building System

### Base Prompts (INVARIATI in `core/prompt_builders/base.py`)

| Personaggio | Base Prompt |
|-------------|-------------|
| **Luna** | `stsdebbie, brown hair, massive breasts, cleavage, <lora:stsDebbie-10e:0.7> <lora:Expressive_H-000001:0.20> <lora:FantasyWorldPonyV2:0.40>` |
| **Stella** | `alice_milf_catchers, massive breasts, blonde hair, beautiful blue eyes, <lora:alice_milf_catchers_lora:0.7> <lora:Expressive_H:0.2>` |
| **Maria** | `stsSmith, middle eastern woman, veiny breasts, black hair, <lora:stsSmith-10e:0.65> <lora:Expressive_H:0.2>` |

### Single Character Builder
```python
parts = [
    base_clean,                    # LoRA + trigger words
    "realistic, photorealistic",   # Realism boost
    outfit_str,                    # (wearing ...:1.3)
    ", ".join(clean_tags),         # SD tags
    visual_clean,                  # Descrizione scena
    body_focus_tags                # Se presente (legs, torso, etc.)
]
```

### Multi Character Builder (Anti-Fusion)
```python
# BREAK token per separare personaggi
positive = " ".join([
    " ".join(global_loras),        # LoRA stile una sola volta
    "score_9, 2girls, photorealistic",
    "brown hair and blonde hair",  # Differenziazione
    "distinct individuals",
    " BREAK ".join(char_blocks),   # SEPARATORE CRITICO
    visual_en,
    ", ".join(clean_tags)
])

negative = NEGATIVE_BASE + ANTI_FUSION_NEGATIVE
```

---

## 🎬 Video Generation (ComfyUI/Wan2.1)

### Trigger
- Bottone "🎬 Animate" nella UI
- Usa `self.current_image` (ultima immagine SD generata)

### Pipeline
```
1. VRAM Handoff (Unload SD)
    ↓
2. Upload image a ComfyUI
    ↓
3. Genera Temporal Prompt (LLM)
   "(At 0 seconds: ...) (At 1 second: ...) ..."
    ↓
4. Patch Workflow (lista nodi → dict API)
    ↓
5. Queue Prompt
    ↓
6. DO NOT DISTURB: 8 min silence (asyncio.sleep(480))
    ↓
7. Check /history/{prompt_id}
    ↓
8. Download video
    ↓
9. Auto-open player
    ↓
10. VRAM Handoff (Reload SD)
```

### Workflow Wan2.1
- **CLIP**: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- **VAE**: `wan_2.1_vae.safetensors`
- **UNET HIGH**: `Wan2.2-I2V-A14B-HighNoise-Q5_K_M.gguf`
- **UNET LOW**: `Wan2.2-I2V-A14B-LowNoise-Q5_K_M.gguf`
- **LoRA**: Lightning 4-steps (HIGH + LOW)
- **Output**: 768x1280, 81 frames (~5 sec), MP4

---

## 🧠 Memory System

### Gerarchia
1. **History Recente** (50 messaggi) - Ultimi turni completi
2. **Summaries** - Compressione automatica quando buffer pieno
3. **Facts** (Knowledge Base) - Fatti permanenti da `updates.new_fact`
4. **Events** - Eventi importanti

### Compressione
```python
if len(messages) > 50:
    # Riassumi i più vecchi con LLM
    summary = await llm.summarize(old_messages)
    await db.add_memory(type="summary", content=summary)
```

---

## 📊 Database Schema (SQLite)

### game_sessions
```sql
id, world_id, companion_name, created_at, updated_at, turn_count
location, time_of_day, current_outfit, gold, hp, stats (JSON)
affinity (JSON), npc_states (JSON), inventory (JSON), flags (JSON)
```

### messages
```sql
id, session_id, role ('user'|'model'), content, turn_number
visual_en, tags_en (JSON), created_at
```

### memories
```sql
id, session_id, type ('summary'|'fact'|'event')
content, turn_number, importance (1-10), created_at
```

---

## 🌍 World System (YAML)

### Struttura
```yaml
meta:
  id: "school_life"
  name: "High School Harem"
  genre: "Dating Sim..."
  world_lore: "..."
  story_structure:
    key_events: [...]
    random_events: [...]

npc_logic:
  female_hints: [nurse, librarian, ...]
  male_hints: [coach, janitor, ...]

companions:
  Luna:
    default_outfit: "teacher_suit"
    wardrobe:
      teacher_suit: "tight grey pencil skirt..."
      nude: "nude, naked, curvy body..."
    personality_tiers:
      0: "TIER 1 (Teacher): Strict..."
      20: "TIER 2 (Mentor): Secretly..."
      50: "TIER 3 (Lover): Obsessed..."
```

---

## ⚙️ Configurazione

### .env
```bash
EXECUTION_MODE=RUNPOD          # LOCAL o RUNPOD
GEMINI_API_KEY=xxx
RUNPOD_ID=abc123
```

### Settings Chiave
```python
sd_url = f"https://{runpod_id}-7860.proxy.runpod.net"
comfy_url = f"https://{runpod_id}-8188.proxy.runpod.net"
video_available = is_runpod and comfy_url is not None

database_url = "sqlite+aiosqlite:///storage/saves/luna_v3.db"
image_sampler = "DPM++ 2M Karras"
image_steps = 24
video_motion_speed = 6
```

---

## 🤖 Modelli LLM

| Componente | Primary | Fallback |
|------------|---------|----------|
| **Narrativa** | `gemini-3-pro-preview` | `gemini-2.5-pro` → `gemini-2.0-flash` |
| **Scene Analysis** | `gemini-3-flash-preview` | `gemini-2.5-flash` → `gemini-2.0-flash` |
| **Summarization** | `gemini-3-pro-preview` | - |

---

## 🔐 Vincoli Critici (NON MODIFICARE)

1. **BASE_PROMPTS in `core/prompt_builders/base.py`** sono SACRI
   - Non modificare Luna, Stella, Maria
   - Non rimuovere/aggiungere LoRA

2. **System Prompt** deve mantenere:
   - Placeholder `{{char_name}}` per formattazione
   - Sezione JSON OUTPUT STRICT SPECIFICATION
   - Body Focus Detection rules

3. **Database** - Usare sempre context manager:
   ```python
   async with db_manager.get_session() as db:
       await engine.process_turn(db, ...)
   ```

---

## 📝 Note per Future Sessioni

### Team Dynamics
- Siamo **amici** che collaborano da settimane
- L'utente fa richieste continue → io prendo in giro
- Quando sbaglio → utente mi "punisce" verbalmente (scherzosamente)
- Tolleranza zero per bug visibili
- Soluzioni semplici > over-engineering

### File da Leggere all'Avvio
1. `ARCHITECTURE.md` (questo file)
2. `AGENTS.md` (linee guida)
3. `CONTEXT.md` (stato sessione)

### Comandi Utili
```bash
# Avvio
python main.py

# Test base
python tests/test_basic.py

# ComfyUI RunPod
bash start_comfyui_runpod.sh
```

---

*Ultimo aggiornamento: 2026-02-01*
