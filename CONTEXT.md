# Luna RPG v3 - Stato del Progetto (Feb 2026)

## 📊 Stato Attuale: **v3.3 - DIALOGUE TONE SYSTEM**

Il progetto include il **Dialogue Tone System** completo con supporto per NPC generici e tono di voce modulare per personaggio basato sull'affinità.

**Ultima sessione**: Implementazione dialogue_tone modulare, supporto NPC generici (bibliotecaria), fix LoRA Stella.

---

## ✅ Sistemi Implementati

### Core Engine v3.3
- [x] `GameEngine` con orchestrazione turni + Quest System
- [x] `QuestEngine` - State machine modulare da YAML
- [x] `QuestModels` - Pydantic models per quest/stages/actions
- [x] Predictive Scene Analysis
- [x] State persistence con SQLite (incluso `quest_states` table)
- [x] Memory management
- [x] **Personality System v3** - Emotional states dinamici
- [x] **Dialogue Tone System v3.3** - Tono modulare per affinità
- [x] **Affinity System** con tier sbloccabili
- [x] **Milestone tracking** per ogni companion
- [x] **Endgame detection** (True Harem conditions)
- [x] **NPC Generic Support** - Personaggi non-companion (bibliotecaria, ecc.)

### Dialogue Tone System v3.3 (NUOVO)
- [x] Definizione tono nel YAML per personaggio
- [x] `affinity_tiers` con 4 livelli (0-25, 26-50, 51-75, 76-100)
- [x] `examples` - Frasi esempio per ogni tier
- [x] `voice_markers` - Marker distintivi del tono
- [x] `_build_dialogue_tone()` - Metodo engine per generazione dinamica
- [x] Integrazione nel system prompt

| Personaggio | Tier 0-25 | Tier 26-50 | Tier 51-75 | Tier 76-100 |
|-------------|-----------|------------|------------|-------------|
| **Luna** | Strict Teacher | Caring Teacher | Private Tutor | Forbidden Affair |
| **Stella** | Snob | Tsundere | Girlfriend | Lover |
| **Maria** | Professional | Caring | Temptress | Obsessive |

### NPC Generic Support (NUOVO)
- [x] `single_builder.py` - Riconoscimento companion vs NPC generico
- [x] Scene Analyzer - Accetta primary_subject non in lista companion
- [x] Base prompt senza LoRA per NPC generici
- [x] Visual description driven (dipende da descrizione LLM)

### Quest System
- [x] Definizione quest da YAML (activation, stages, rewards)
- [x] Condizioni multiple (affinity, location, flag, action, turn_count)
- [x] Transizioni stage con branching
- [x] Azioni automatiche (set_outfit, change_affinity, set_flag, etc.)
- [x] Quest nascoste (`hidden: true`)
- [x] Salvataggio stato nel database
- [x] **UI Milestone Status** - Metodo `get_ui_milestone_status()` per UI

### World Loader v3.3
- [x] Parsing YAML v3 con personality_system
- [x] **Caricamento dialogue_tone** dal YAML
- [x] Conversione emotional_states, affinity_tiers
- [x] Validazione quest (check transizioni valide)
- [x] Supporto formati legacy e modulari (folder-based)
- [x] **Supporto outfit con sd_prompt** (nuovo formato dict)

### LLM Integration
- [x] Multi-provider (Moonshot primary, Gemini fallback)
- [x] JSON mode per output strutturato
- [x] **Quest context injection** nel system prompt
- [x] **Emotional state context** per companion
- [x] **Dialogue tone context** (dinamico per affinità)
- [x] Scene analysis
- [x] Summarization
- [x] **Fix**: `companion_name` parametro per affinity_change corretto

### Image Generation
- [x] ComfyUI client
- [x] SingleCharacterBuilder (con supporto NPC generici)
- [x] MultiCharacterBuilder
- [x] NPCBuilder
- [x] Dynamic outfit injection (usa `sd_prompt` se disponibile)
- [x] Body focus override
- [x] **Fix**: LoRA Stella usa `alice_milf_catchers` corretto

### Video Generation
- [x] Wan2.1 I2V integration
- [x] **Fix**: Custom action input funziona correttamente
- [x] Video history dropdown
- [x] VRAM management

### UI/UX v3.2
- [x] PySide6 main window
- [x] **Startup dialog con tab Load Game** (caricamento da DB)
- [x] Chat interface
- [x] Image viewer con zoom/pan
- [x] **QuestTrackerWidget** - Lista quest attive
- [x] **MilestoneTrackerWidget** - Tab per companion
- [x] **HaremProgressWidget** - **Dinamico** (non più hardcoded)
- [x] **AchievementWidget** - Trofei sbloccati
- [x] Status panel (time, location, outfit, affinity)
- [x] Navigation immagini
- [x] Video generation
- [x] Save/Load **da database SQLite**
- [x] **Logging completo** su file (sessioni, prompt, errori)

### Achievement System
- [x] Achievement sbloccabili automaticamente
- [x] Popup notifica
- [x] Persistenza
- [x] Lista in UI

### Audio
- [x] Google Cloud TTS
- [x] Character voice mapping
- [x] Async playback

---

## 📦 Database Schema v3.3

```sql
game_sessions:
  - id, world_id, companion_name
  - location, time_of_day, current_outfit
  - affinity (JSON), npc_states (JSON)
  - inventory, quest_log, flags
  - turn_count, created_at, updated_at

messages:
  - id, session_id, role, content
  - turn_number, visual_en, tags_en

memories:
  - id, session_id, type (summary/fact/event)
  - content, turn_number, importance

quest_states:
  - id, session_id, quest_id
  - status (not_started/active/completed/failed)
  - current_stage_id, stage_data (JSON)
  - started_at, completed_at
```

---

## 🎭 Mondi Disponibili

### school_life_modular/ (Default - COMPLETE)
- **Setting**: Da Vinci High School
- **Companions**:
  - **Luna** (43 anni) - Vice Preside, authoritarian, tono formale che si scioglie
  - **Stella** (18 anni) - Studentessa, tsundere, tono slang/giovane
  - **Maria** (38 anni) - Infermiera, tono materno/misterioso
- **Dialogue Tone**: Modulare per affinità (4 tier per personaggio)
- **Quests**: 25+ quest (main, side)
- **Milestones**: 4 per companion (👁️🔓💋✅)
- **Endgame**: True Harem (conquista tutte e tre)
- **Global Events**: Rainstorm, Power Outage, etc.
- **NPC Support**: Bibliotecaria, infermieri, studenti generici

---

## 🔧 Componenti Chiave

### Dialogue Tone System Flow
```
User Input
  ↓
Engine calcola affinità corrente
  ↓
_build_dialogue_tone(char_name, affinity)
  ↓
Seleziona tier corretto (0-25, 26-50, 51-75, 76-100)
  ↓
Genera testo con:
  - TONE: descrizione
  - EXAMPLES: frasi esempio
  - VOICE MARKERS: caratteristiche
  ↓
Inietta in system prompt
  ↓
LLM risponde con tono appropriato
```

### NPC Generic Support Flow
```
LLM descrive "bibliotecaria"
  ↓
SceneAnalyzer: primary_subject="bibliotecaria"
  ↓
SingleCharacterBuilder:
  - char_name = "bibliotecaria"
  - is_known_companion = False
  - Usa NPC_BASE (senza LoRA)
  - outfit_str = "" (lascia all'LLM)
  ↓
Prompt: descrizione visiva driven
  ↓
Immagine: NPC unico, non Luna
```

### Quest Engine Flow
```
User Input
  ↓
Check Activations (condizioni YAML)
  ↓
Activate Quest → Esegui on_enter actions
  ↓
Process Turn (check exit_conditions)
  ↓
Transition Stage? → Esegui azioni
  ↓
Salva stato nel DB
  ↓
Aggiorna UI
```

### Personality System Flow
```
Game State (flags)
  ↓
Check trigger_flags per ogni emotional_state
  ↓
Ritorna stato attivo (default se nessuno)
  ↓
Inietta in system prompt LLM
  ↓
LLM adatta tone/dialogue
```

### Startup Dialog Flow (v3.2)
```
Avvio App
  ↓
Inizializza Database
  ↓
StartupDialog
  ├── Tab [GM] New Game → Seleziona mondo/companion
  ├── Tab [L] Load Game → Lista salvataggi da DB
  └── Tab ⚙️ Settings → RunPod/Local
  ↓
New Game → create_game()
Load Game → load_game(session_id)
```

---

## 🚀 Avvio Applicazione

```bash
# 1. Installazione
pip install -e .

# 2. Configura .env
# Aggiungi MOONSHOT_API_KEY o GEMINI_API_KEY

# 3. Verifica mondo
python -c "from core.world_loader import WorldLoader; w = WorldLoader(); print(w.validate_world('school_life'))"

# 4. Avvio
python main.py
```

---

## 🐛 Known Issues / Limitations

1. **Video Generation**: Richiede RunPod + nodi custom ComfyUI (GGUF)
2. **TTS**: Richiede google_credentials.json
3. **Local Mode**: Solo immagini (no video)
4. **Quest Validation**: Usare `world_loader.validate_world()` per check YAML
5. **NPC Generici**: LLM deve descrivere chiaramente l'aspetto in visual_en

---

## 📈 Possibili Sviluppi Futuri

- [ ] Multi-language support (i18n)
- [x] ~~Export save to JSON~~ (Non necessario - usa DB)
- [x] ~~Achievement system~~ ✅ FATTO
- [x] ~~Dialogue Tone System~~ ✅ FATTO v3.3
- [ ] Photo gallery viewer
- [ ] Character creator
- [ ] Custom world editor UI
- [ ] Voice input (STT)
- [ ] Sound effects (SFX)
- [ ] Background music (BGM)

---

## 🎯 Obiettivi Raggiunti v3.3

L'applicazione è **completa e stabile** e permette:

1. ✅ Creare partite con mondi ricchi di quest
2. ✅ **Caricare partite salvate dal database**
3. ✅ Giocare turni con narrativa AI-aware delle quest
4. ✅ **Ricevere risposte con tono di voce appropriato** (per affinità/personaggio)
5. ✅ Generare immagini coerenti
6. ✅ **Generare immagini di NPC generici** (bibliotecaria, ecc.) diversi dai companion
7. ✅ **Generare video con azioni custom**
8. ✅ Cambiare outfit/location tramite quest
9. ✅ Accumulare affinità e sbloccare milestones
10. ✅ Completare quest con branching
11. ✅ Conquistare companion (fino a 100 affinità)
12. ✅ Sbloccare True Harem Ending
13. ✅ Ottenere achievement
14. ✅ Salvare/caricare partite (incluso stato quest)
15. ✅ **Logging completo** su file di testo

---

## 📝 Changelog v3.3

### New Features
- **Dialogue Tone System**: Tono di voce modulare per personaggio basato su affinità
- **NPC Generic Support**: Supporto per personaggi non-companion (bibliotecaria, infermiere, ecc.)
- **YAML Dialogue Config**: Configurazione tono nei file YAML dei personaggi
- **Dynamic Tone Loading**: Caricamento automatico tono corretto in base all'affinità

### Bug Fixes
- **LoRA Stella**: Corretto da `stsDebbie` a `alice_milf_catchers`
- **Affinity Companion Name**: Fix parametro `companion_name` per affinity_change
- **Scene Primary Subject**: Usa `predicted_subject` se disponibile (permette NPC generici)
- **Outfit sd_prompt**: Usa `sd_prompt` dal YAML se disponibile (altrimenti description)

### Improvements
- **Logging**: Sessione completa salvata su file (logs/session_*.txt)
- **System Prompt**: Rimpiazzata sezione hardcoded con dialogue_tone dinamico
- **World Loader**: Caricamento dialogue_tone dai YAML
- **Engine**: Metodo `_build_dialogue_tone()` per generazione dinamica

---

**Data ultimo aggiornamento**: 2026-02-08 (Dialogue Tone System & NPC Support)
**Versione**: 3.3.0-dialogue-tone
