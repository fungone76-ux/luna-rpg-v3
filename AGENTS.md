# Luna RPG v3 - Agent Guidelines (Feb 2026)

## 🎯 Panoramica Progetto

Luna RPG v3 è un **Visual Novel/RPG AI-driven** per adulti con generazione immagini in tempo reale e **Quest System modulare**.

### Architettura Core
- **Async**: asyncio + qasync per integrazione Qt
- **Database**: SQLite con SQLAlchemy 2.0 (async)
- **LLM**: Moonshot (primary) + Gemini (fallback)
- **Immagini**: ComfyUI (locale/RunPod) - NON più SD WebUI
- **Video**: Wan2.1 I2V su RunPod (512x768)
- **UI**: PySide6 con tema dark + **Quest Tracker UI**
- **Quest System**: State machine modulare da YAML

---

## 📁 Struttura Progetto

```
luna-rpg-v3/
├── main.py                    # Entry point (async Qt setup)
├── pyproject.toml             # Dependencies
├── .env                       # Configurazione runtime
│
├── core/                      # Engine principale
│   ├── models.py              # Pydantic models (GameSession, SceneAnalysis, etc)
│   ├── database.py            # SQLAlchemy async + DatabaseManager
│   ├── engine.py              # GameEngine - orchestrazione turni + quest
│   ├── quest_engine.py        # Quest System v3 (state machine)
│   ├── quest_models.py        # Modelli Pydantic per quest
│   ├── state_manager.py       # Persistenza stato gioco
│   ├── memory_manager.py      # Gestione memoria + compressione
│   ├── scene_analyzer.py      # Analisi scena con LLM
│   ├── world_loader.py        # Loader YAML mondi v3 (con quest)
│   └── prompt_builders/       # Costruttori prompt SD
│       ├── base.py            # Costanti + BASE_PROMPTS (SACRI!)
│       ├── single_builder.py  # Scene single-character
│       ├── multi_builder.py   # Scene multi-char (anti-fusion)
│       └── npc_builder.py     # NPC generici
│
├── media/                     # Client API esterni
│   ├── llm_client.py          # Multi-provider (Gemini + Moonshot)
│   ├── comfy_image_client.py  # ComfyUI per immagini
│   ├── image_client.py        # SD WebUI (legacy)
│   ├── audio_client.py        # Google TTS
│   └── video_client.py        # Wan2.1 I2V per video
│
├── ui/                        # Interfaccia PySide6
│   ├── startup_dialog.py      # Selezione mondo/companion
│   ├── main_window.py         # Finestra principale + Quest Tracker
│   ├── quest_widgets.py       # Widget UI per quest/milestone/achievement
│   └── video_action_dialog.py # Dialog input azione video
│
├── config/
│   └── settings.py            # Pydantic Settings
│
├── prompts/                   # System prompts LLM
│   ├── system_prompt_compact.txt
│   ├── system_prompt_backup.txt
│   └── visual_director.txt
│
├── worlds/                    # Mondi di gioco (YAML v3)
│   ├── school_life_v3.yaml    # High School Harem + Quest System
│   ├── fantasy_dark.yaml
│   └── cyberpunk_noir.yaml
│
├── storage/                   # Persistenza locale
│   ├── saves/                 # Database SQLite
│   ├── images/                # Immagini generate
│   └── videos/                # Video generati
│
└── tests/
    └── test_basic.py
```

---

## 🧠 Meccaniche di Gioco

### 1. Quest System v3 (NUOVO - Feb 2026)

**Architettura modulare** definita interamente nel YAML:

```yaml
quests:
  medical_checkup:
    meta:
      title: "The Medical Checkup"
      type: "side"  # main | side
      character: "Luna"
      hidden: true
    
    activation:
      type: "auto"
      conditions:
        - type: "affinity"
          target: "Luna"
          operator: "gte"
          value: 25
    
    stages:
      start:
        title: "The Invitation"
        narrative_prompt: "Luna asks you to stay after class..."
        on_enter:
          - action: "set_emotional_state"
            character: "Luna"
            state: "flustered"
        exit_conditions:
          - type: "location"
            operator: "eq"
            value: "Nurse Office"
        transitions:
          - condition: "condition_0"
            target_stage: "examination"
      
      examination:
        ...
    
    rewards:
      affinity:
        Luna: 15
      flags:
        medical_quest_done: true
      unlock_quests:
        - "boiler_room_secret"
```

**Azioni Supportate** (`on_enter`, `rewards`):
- `set_location`, `set_outfit`, `set_flag`
- `change_affinity`, `increment_stat`
- `set_emotional_state`, `set_time`
- `unlock_achievement`

**Condizioni** (`exit_conditions`, `activation`):
- `affinity`: Confronto affinità companion
- `location`, `time`: Check stato mondo
- `flag`: Check flag arbitrari
- `action`: Pattern regex su input utente
- `turn_count`: Numero turni trascorsi

### 2. Personality System v3 (NUOVO)

Sostituisce i vecchi `personality_tiers` statici:

```yaml
personality_system:
  core_traits:
    role: "Vice Principal"
    age: "43"
    base_personality: "Authoritative but lonely"
  
  emotional_states:
    default:
      description: "Professional and commanding"
      dialogue_tone: "Formal, uses titles"
    
    flustered:
      trigger_flags: ["luna_embarrassed"]
      description: "Nervous but pleased"
      dialogue_tone: "Hesitant, stuttering"
    
    seductive:
      trigger_flags: ["luna_affinity_high"]
      description: "Openly provocative"
      dialogue_tone: "Whispering, double meanings"
  
  affinity_tiers:
    0:
      tier_name: "The Authority"
      available_actions: ["ask_question"]
      locked_actions: ["flirt", "touch"]
    50:
      tier_name: "The Woman"
      unlock_outfits: ["lingerie"]
```

**Stati Emotivi Dinamici**:
- Si attivano tramite `trigger_flags` nel database
- Cambiano il tone dell'LLM in tempo reale
- Persistono finché il flag è attivo

### 3. Milestones & Endgame (NUOVO)

```yaml
milestones:
  Luna:
    - id: "luna_trust"
      name: "La sua Fiducia"
      condition: 
        affinity: 50
        flag: "luna_shared_personal"
      icon: "🔓"

endgame:
  victory_conditions:
    - type: "companion_conquered"
      target: "Luna"
      requires:
        - affinity: 100
        - flag: "luna_confessed_love"
```

**True Harem Ending**: Conquista tutte e tre le companion (affinity 100 + flag specifici).

### 4. Predictive Scene Analysis

**Flusso di un turno**:

```python
# STEP 1: QUEST SYSTEM CHECK
quest_updates = self.quest_engine.check_activations(game_state)
for quest_id in new_quests:
    self.quest_engine.activate_quest(quest_id, game_state)

# STEP 2: Analisi predittiva
predictive_analysis = await self._analyze_user_intent(user_input)

# STEP 3: Build system prompt CON quest context
system_prompt += self.quest_engine.get_active_quests_context()
system_prompt += f"Emotional state: {get_companion_emotional_state()}"

# STEP 4: LLM genera risposta
response = await self.llm.generate_response(...)

# STEP 5: Update quest progress
self.quest_engine.process_turn(quest_id, game_state, user_input)

# STEP 6: Salva stati nel DB
await db_manager.save_quest_state(...)
```

### 5. Affinity System

- **0-25**: Stranger/Distante
- **25-50**: Friendly/Curiosa (sblocca azioni base)
- **50-75**: Intimate/Interessata (sblocca outfit)
- **75-100**: Obsessed/Innamorata (azioni intime)
- **100**: Conquistata (per True Harem)

---

## 🎨 Image Generation Pipeline

Invariata dalla v3.0. Vedi sezioni precedenti per `SingleCharacterBuilder`, `MultiCharacterBuilder`, `BASE_PROMPTS`.

---

## 🤖 LLM Integration

Invariata. Supporto JSON mode con campi aggiuntivi:

```json
{
  "text": "Narrativa italiana...",
  "visual_en": "Descrizione scena...",
  "tags_en": ["tag1", "tag2"],
  "body_focus": "legs",
  "approach_used": "physical_action",
  "time_of_day": "Afternoon",
  "location": "Nurse Office",
  "affinity_change": {"Luna": 5},
  "current_outfit": "medical_gown"
}
```

---

## 🖥️ UI Components (NUOVO)

### QuestTrackerWidget
Lista quest attive con stato (🟢 attiva, ✅ completata, 🔴 fallita).

### MilestoneTrackerWidget
Tab per companion con:
- Progress bar affinità (cambia colore)
- Stato emotivo attuale
- Lista milestones con icone (✅/⬜)

### HaremProgressWidget
- Barra progresso 0/3 companion conquistate
- Stato individuale Luna/Stella/Maria
- Notifica quando sbloccato True Harem

### AchievementWidget
- Lista achievement sbloccati
- Popup notifica al unlock
- Contatore progresso

---

## 📝 World YAML Format v3

### Schema Completo

```yaml
meta:
  id: "school_life_v3"
  name: "High School Harem - Complete"
  version: "3.0"
  timeline:
    time_cycle: ["Morning", "Afternoon", "Evening", "Night"]

npc_logic:
  female_hints: [...]
  male_hints: [...]

companions:
  Luna:
    default_outfit: "executive_suit"
    base_prompt: "..."
    wardrobe:
      executive_suit: "..."
      nude: "..."
    personality_system:
      core_traits: {...}
      emotional_states: {...}
      affinity_tiers: {...}
    relationship:
      flags: [...]
      stats: {...}

quests:
  # Vedi sezione Quest System

milestones:
  Luna:
    - id: "..."
      name: "..."
      condition: {affinity: 50, flag: "..."}
      icon: "🔓"

endgame:
  description: "..."
  victory_conditions: [...]
  ui_indicators:
    heart_icon: "❤️"
    conquered_icon: "✅"

global_events:
  rainstorm:
    meta: {...}
    trigger: {type: "random", chance: 0.15}
    effect:
      actions:
        - action: "set_emotional_state"
          character: "{current_companion}"
          state: "flustered"
```

---

## 🏆 Achievement System

**Achievement sbloccabili**:
- 🎯 **First Steps** - Prima quest attivata
- 💕 **{Companion} Interessata** - Affinità 50
- ❤️ **{Companion} Conquistata** - Affinità 100
- 👑 **Harem Master** - Tutte e tre a 100
- 🔐 **Secret Keeper** - Scopri segreti
- 👗 **Fashionista** - Tutti outfit sbloccati

**Implementazione UI**:
```python
# In main_window.py
def _unlock_achievement(self, title, description, icon):
    self.achievement_widget.add_achievement(title, description, icon)
    self._append_story(f"<div class='achievement-popup'>...</div>")
```

---

## ⚙️ Environment Variables

Invariati. Vedi sezione precedente.

---

## 🔧 Pattern di Codice

### Quest Engine Usage
```python
# Inizializzazione
self.quest_engine = QuestEngine(world_data)

# Caricamento stati salvati
saved_states = await db_manager.get_quest_states(db, session_id)
self.quest_engine.load_saved_states(saved_states)

# Process turn
new_quests = self.quest_engine.check_activations(game_state)
for qid in new_quests:
    result = self.quest_engine.activate_quest(qid, game_state)
    await self._execute_quest_actions(db, result["actions"])

# Update active quests
for qid in self.quest_engine.active_states:
    result = self.quest_engine.process_turn(qid, game_state, user_input)
    if result:
        await self._execute_quest_actions(db, result.actions_to_execute)
```

### Emotional State Detection
```python
state = self.quest_engine.get_companion_emotional_state("Luna", game_state)
# Controlla trigger_flags nel game_state.flags
# Ritorna "default" se nessun trigger attivo
```

### Milestone Check
```python
milestones = self.quest_engine.check_milestones("Luna", game_state)
for m in milestones:
    if m.id not in already_notified:
        self._show_milestone_reached(m)
```

---

## 🐛 Debug Tips

1. **Check quest attive**: `print(f"[Q] Active: {quest_engine.active_states}")`
2. **Check emotional state**: `print(f"[E] Luna state: {emo_state}")`
3. **Check milestones**: Lista in UI o `quest_engine.check_milestones()`
4. **Check flags**: `print(f"[F] flags={game_state.flags}")`

---

## 🚫 Vincoli Critici

1. **BASE_PROMPTS**: Mai modificare
2. **Async/await**: SEMPRE per I/O
3. **Database**: Usare sempre context manager
4. **UI**: Non bloccare main thread (usa asyncSlot)
5. **ComfyUI**: Usare workflow JSON
6. **YAML v3**: Validare con `world_loader.validate_world()`

---

## 🔄 Flusso Completo Turno (v3.1)

```
┌─────────────────────────────────────────────────────────────┐
│  USER INPUT                                                 │
│     ↓                                                       │
│  QuestEngine.check_activations() → nuove quest?             │
│     ↓                                                       │
│  QuestEngine.process_turn() → cambio stage?                 │
│     ↓                                                       │
│  Esegui on_enter actions (outfit, flag, affinity...)        │
│     ↓                                                       │
│  _analyze_user_intent() → predictive analysis               │
│     ↓                                                       │
│  _build_system_prompt_with_quest_context()                  │
│     ↓                                                       │
│  llm.generate_response() → JSON                             │
│     ↓                                                       │
│  memory.add_message()                                       │
│     ↓                                                       │
│  state.update() (affinity, outfit, location)                │
│     ↓                                                       │
│  Salva quest states nel DB                                  │
│     ↓                                                       │
│  _generate_image()                                          │
│     ↓                                                       │
│  _update_quest_ui() → aggiorna UI                           │
│     ↓                                                       │
│  _check_achievements() → sblocca achievement?               │
│     ↓                                                       │
│  RETURN {text, image_path, quest_updates, ...}              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎮 Feature Complete List v3.1

- ✅ Predictive Scene Analysis
- ✅ Multi-provider LLM (Moonshot + Gemini)
- ✅ JSON mode
- ✅ Memory compression
- ✅ Outfit switching
- ✅ Anti-fusion multi-char
- ✅ Video generation (Wan2.1)
- ✅ TTS
- ✅ Save/Load database
- ✅ **Quest System v3** (state machine YAML)
- ✅ **Personality System** (emotional states)
- ✅ **Milestones & Endgame**
- ✅ **Achievement System**
- ✅ **Quest Tracker UI**
- ✅ **Harem Progress UI**
- ✅ RunPod cloud support

---

**Ultimo aggiornamento**: Feb 2026 (Sessione: Quest System v3 + Personality System + Achievement System)
**Versione**: 3.1.0
