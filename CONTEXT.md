# Luna RPG v3 - Stato del Progetto (Feb 2026)

## 📊 Stato Attuale: **v3.1 - QUEST SYSTEM COMPLETE**

Il progetto include ora il **Quest System v3** completo con Personality System dinamico, Milestones, Achievement e UI dedicata.

---

## ✅ Sistemi Implementati

### Core Engine v3.1
- [x] `GameEngine` con orchestrazione turni + Quest System
- [x] `QuestEngine` - State machine modulare da YAML
- [x] `QuestModels` - Pydantic models per quest/stages/actions
- [x] Predictive Scene Analysis
- [x] State persistence con SQLite (incluso `quest_states` table)
- [x] Memory management
- [x] **Personality System v3** - Emotional states dinamici
- [x] **Affinity System** con tier sbloccabili
- [x] **Milestone tracking** per ogni companion
- [x] **Endgame detection** (True Harem conditions)

### Quest System
- [x] Definizione quest da YAML (activation, stages, rewards)
- [x] Condizioni multiple (affinity, location, flag, action, turn_count)
- [x] Transizioni stage con branching
- [x] Azioni automatiche (set_outfit, change_affinity, set_flag, etc.)
- [x] Quest nascoste (`hidden: true`)
- [x] Quest redemption (recupero companion scartata)
- [x] Salvataggio stato nel database

### World Loader v3
- [x] Parsing YAML v3 con personality_system
- [x] Conversione emotional_states, affinity_tiers
- [x] Validazione quest (check transizioni valide)
- [x] Supporto milestones, endgame, global_events

### LLM Integration
- [x] Multi-provider (Moonshot primary, Gemini fallback)
- [x] JSON mode per output strutturato
- [x] **Quest context injection** nel system prompt
- [x] **Emotional state context** per companion
- [x] Scene analysis
- [x] Summarization

### Image Generation
- [x] ComfyUI client
- [x] SingleCharacterBuilder
- [x] MultiCharacterBuilder
- [x] NPCBuilder
- [x] Dynamic outfit injection
- [x] Body focus override

### Video Generation
- [x] Wan2.1 I2V integration
- [x] Custom action input dialog
- [x] Video history dropdown
- [x] VRAM management

### UI/UX v3.1
- [x] PySide6 main window
- [x] Startup dialog
- [x] Chat interface
- [x] Image viewer con zoom/pan
- [x] **QuestTrackerWidget** - Lista quest attive
- [x] **MilestoneTrackerWidget** - Tab per companion
- [x] **HaremProgressWidget** - Progresso True Harem
- [x] **AchievementWidget** - Trofei sbloccati
- [x] Status panel (time, location, outfit, affinity)
- [x] Navigation immagini
- [x] Video generation
- [x] Save/Load

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

## 📦 Database Schema v3.1

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

quest_states:                    # NUOVO
  - id, session_id, quest_id
  - status (not_started/active/completed/failed)
  - current_stage_id, stage_data (JSON)
  - started_at, completed_at
```

---

## 🎭 Mondi Disponibili

### school_life_v3.yaml (Default - COMPLETE)
- **Setting**: Da Vinci High School
- **Companions**:
  - **Luna** (43 anni) - Vice Preside, authoritarian
  - **Stella** (18 anni) - Studentessa, tsundere
  - **Maria** (55 anni) - Bidella, wise/caring
- **Quests**: 18+ quest (main, side, redemption)
  - `first_day`, `the_rivalry`, `the_prom` (main)
  - `medical_checkup`, `gym_class`, `pop_quiz` (Luna)
  - `tutoring_sessions`, `cheerleader_practice` (Stella)
  - `storage_room_secrets`, `maria_cooking` (Maria)
  - `luna_redemption`, `stella_redemption` (recupero)
- **Milestones**: 4 per companion (👁️🔓💋✅)
- **Endgame**: True Harem (conquista tutte e tre)
- **Global Events**: Rainstorm, Power Outage, Heatwave, etc.

---

## 🔧 Componenti Chiave

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

### Achievement Check
```python
# Dopo ogni turno:
if affinity >= 50 and not unlocked:
    unlock_achievement("{Name} Interessata")
    show_popup()
    add_to_list()
```

---

## 🚀 Avvio Applicazione

```bash
# 1. Installazione
pip install -e .

# 2. Configura .env
# Aggiungi MOONSHOT_API_KEY o GEMINI_API_KEY

# 3. Verifica mondo
python -c "from core.world_loader import WorldLoader; w = WorldLoader(); print(w.validate_world('school_life_v3'))"

# 4. Avvio
python main.py
```

---

## 🐛 Known Issues / Limitations

1. **Video Generation**: Richiede RunPod
2. **TTS**: Richiede google_credentials.json
3. **Local Mode**: Solo immagini (no video)
4. **Quest Validation**: Usare `world_loader.validate_world()` per check YAML

---

## 📈 Possibili Sviluppi Futuri

- [ ] Multi-language support (i18n)
- [ ] Export save to JSON
- [x] ~~Achievement system~~ ✅ FATTO
- [ ] Photo gallery viewer
- [ ] Character creator
- [ ] Custom world editor UI
- [ ] Voice input (STT)
- [ ] Sound effects (SFX)
- [ ] Background music (BGM)

---

## 🎯 Obiettivi Raggiunti v3.1

L'applicazione è **completa** e permette:

1. ✅ Creare partite con mondi ricchi di quest
2. ✅ Giocare turni con narrativa AI-aware delle quest
3. ✅ Generare immagini coerenti
4. ✅ Cambiare outfit/location tramite quest
5. ✅ Accumulare affinità e sbloccare milestones
6. ✅ Completare quest con branching
7. ✅ Conquistare companion (fino a 100 affinità)
8. ✅ Sbloccare True Harem Ending
9. ✅ Ottenere achievement
10. ✅ Salvare/caricare partite (incluso stato quest)

---

**Data ultimo aggiornamento**: 2026-02-04 (Sessione: Quest System v3 + Achievement System)
**Versione**: 3.1.0-quest-complete
