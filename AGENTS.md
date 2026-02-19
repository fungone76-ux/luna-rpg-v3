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
│   ├── startup_dialog.py      # Selezione mondo/companion + Load Game da DB
│   ├── main_window.py         # Finestra principale + Quest Tracker (dynamic)
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
│   ├── school_life_modular/   # NEW: Modular folder structure
│   │   ├── _meta.yaml         # World metadata, player
│   │   ├── luna.yaml          # Luna + quests + milestones
│   │   ├── stella.yaml        # Stella + quests + milestones
│   │   ├── maria.yaml         # Maria + quests + milestones
│   │   ├── locations.yaml     # 16 game locations
│   │   ├── time.yaml          # Time system
│   │   └── global_events.yaml # Weather & events
│   ├── school_life_v3.yaml    # Legacy monolithic (backward compat)
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
│  WardrobeEngine.get_outfit() → Lista sicura vs Creativa     │
│     ↓                                                       │
│  llm.generate_response() → JSON                             │
│     ↓                                                       │
│  memory.add_message()                                       │
│     ↓                                                       │
│  state.update() (affinity, outfit, location)                │
│     ↓                                                       │
│  Salva quest states nel DB                                  │
│     ↓                                                       │
│  _generate_image() (con prompt ibrido)                      │
│     ↓                                                       │
│  _update_quest_ui() → aggiorna UI                           │
│     ↓                                                       │
│  _check_achievements() → sblocca achievement?               │
│     ↓                                                       │
│  RETURN {text, image_path, quest_updates, ...}              │
└─────────────────────────────────────────────────────────────┘
```

---

## 👔 Wardrobe System "Hybrid Creative" (NUOVO - Feb 2026)

**Problema:** Volevamo sia la qualità curata dei prompt predefiniti (v3) sia la libertà creativa dell'LLM di inventare outfit al volo (v2).

**Soluzione:** Un sistema ibrido che supporta entrambi.

### 1. YAML Configuration (Modalità Sicura)
Gli outfit definiti nel YAML sono la "base solida". L'LLM li usa per la coerenza quotidiana.

```yaml
wardrobe:
  executive_suit:
    sd_prompt: "wearing black pencil skirt, white blouse..."
    description: "Tailleur formale."
  gym_wear:
    sd_prompt: "wearing tight yoga pants..."
```

### 2. LLM Creative Mode (Modalità Libera)
Se l'LLM inventa un outfit che NON è nel YAML, il sistema lo accetta come **descrizione visiva diretta**.

**Esempio LLM JSON:**
```json
{
  "current_outfit": "wearing red latex catsuit, shiny, zipper",
  "text": "Luna sorride maliziosa..."
}
```

**Logica Engine (`core/prompt_builders/base.py`):**
1. Cerca "wearing red latex..." nel YAML -> Non trovato.
2. Assume sia una descrizione creativa -> Passa la stringa direttamente a ComfyUI.
3. Risultato: Luna indossa la tutina rossa inventata dall'LLM!

**System Prompt Instruction:**
> "If the user asks for a specific outfit NOT in the list, YOU CAN INVENT IT. Output a full visual description string in `current_outfit` instead of an ID."

---

## 🎮 Feature Complete List v3.3

- ✅ **Wardrobe Hybrid System** (Safe List + Creative Freedom)
- ✅ Predictive Scene Analysis
- ✅ Multi-provider LLM (Moonshot + Gemini)
- ✅ JSON mode
- ✅ Memory compression
- ✅ Outfit switching
- ✅ Anti-fusion multi-char
- ✅ Video generation (Wan2.1) with custom actions
- ✅ TTS
- ✅ **Save/Load database** (SQLite + SQLAlchemy async)
- ✅ **Quest System v3** (state machine YAML)
- ✅ **Personality System** (emotional states)
- ✅ **Milestones & Endgame**
- ✅ **Achievement System**
- ✅ **Quest Tracker UI**
- ✅ **Harem Progress UI** (dynamic, N companion support)
- ✅ RunPod cloud support
- ✅ **Modular World System** (folder-based, selective loading)
- ✅ **PersonalityEngine** (behavioral tracking, impressions, NPC links)
- ✅ **LLM Output Validation** (Python as source of truth)
- ✅ **Startup Dialog** (New Game / Load Game / Settings tabs)

---

## 📦 Modular World System (NUOVO - Feb 2026)

**Split monolithic YAML into maintainable components:**

### File Structure
```
worlds/
├── school_life_v3.yaml          # Legacy monolithic (backward compat)
└── school_life_modular/         # NEW: Modular folder structure
    ├── _meta.yaml               # World metadata, player character, endgame
    ├── luna.yaml                # Luna character + quests + milestones
    ├── stella.yaml              # Stella character + quests + milestones  
    ├── maria.yaml               # Maria character + quests + milestones
    ├── locations.yaml           # 16+ game locations
    ├── time.yaml                # Time system configuration
    └── global_events.yaml       # Weather, school events, social dynamics
```

### Loader Auto-Detection
```python
def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
    folder_path = self.worlds_path / world_id
    if folder_path.exists() and folder_path.is_dir():
        return self._load_modular_world(folder_path, world_id)
    else:
        return self._load_legacy_world(self.worlds_path / f"{world_id}.yaml", world_id)
```

### Benefits
- **Reduced LLM tokens**: Load only active companion's full psychology
- **Parallel editing**: Multiple authors can work on different characters
- **Version control**: Track changes per character/location
- **Selective loading**: Load summaries of inactive companions

---

## 🧠 PersonalityEngine (NUOVO - Feb 2026)

**Dynamic psychological tracking of player behavior:**

### BehavioralMemory
```python
@dataclass
class BehavioralMemory:
    aggressive: Dict[str, int]   # "subtle" -> count
    shy: Dict[str, int]
    romantic: Dict[str, int]
    dominant: Dict[str, int]
    kind: Dict[str, int]
    
    def get_dominant_traits(self) -> List[Tuple[str, str]]:
        # Returns [("romantic", "strong"), ("aggressive", "subtle")]
```

### Impressions System
5-dimensional emotional state per companion (-100 to +100):
- **Trust**: Credibility of player
- **Attraction**: Romantic/sexual interest
- **Fear**: Intimidation level
- **Curiosity**: Interest in discovering more
- **Dominance**: Who holds power in relationship

### NPC Relationship Matrix
```python
class NPCLinks:
    def __init__(self):
        self.links: Dict[str, Dict[str, LinkData]] = {
            "Luna": {
                "Stella": LinkData(jealousy=0.7, awareness=0.3),
                "Maria": LinkData(gossip_target=0.9)
            }
        }
```

### Usage in Engine
```python
# Step 0: Analyze behavior
if self.personality_engine:
    analysis = self.personality_engine.analyze_player_action(
        self.state.current.companion_name, 
        user_input, 
        self.state.current.turn_count
    )
    # Returns: detected traits, impression changes, archetype hints

# Step 3: Build English personality context for LLM
personality_context = self.personality_engine.get_psychological_context(
    companion_name,
    include_behavioral=True,
    include_impressions=True,
    include_links=True
)
```

---

## ✅ LLM Output Validation (NUOVO - Feb 2026)

**Python is source of truth. LLM suggests, Python validates.**

### Validation Rules
```python
def _validate_llm_updates(self, updates: Dict[str, Any]) -> Dict[str, Any]:
    validated = {}
    
    # 1. Affinity clamped (-5 to +5 per turn)
    if "affinity" in updates:
        for char, delta in updates["affinity"].items():
            validated["affinity"][char] = max(-5, min(5, delta))
    
    # 2. Outfits must exist in character wardrobe
    if "current_outfit" in updates:
        wardrobe = self.world_data["companions"][companion]["wardrobe"].keys()
        if updates["current_outfit"] not in wardrobe:
            validated["current_outfit"] = self.state.current.outfit  # Keep current
    
    # 3. Locations must be defined
    if "location" in updates:
        valid_locations = [loc["id"] for loc in self.world_data.get("locations", [])]
        if updates["location"] not in valid_locations:
            validated["location"] = self.state.current.location
    
    # 4. Flags must be whitelisted or start with allowed prefixes
    if "flags" in updates:
        for flag in updates["flags"]:
            if not self._is_valid_flag(flag):
                continue  # Skip invalid flags
            validated["flags"][flag] = updates["flags"][flag]
    
    return validated
```

### Anti-Hallucination Strategy
1. **Read-only context**: LLM receives psychological state as text, cannot modify directly
2. **Suggestion-only**: LLM outputs `updates` dict, Python validates & applies
3. **Wardrobe enforcement**: Outfit changes must reference valid wardrobe keys
4. **Flag prefix whitelist**: Only `luna_*`, `stella_*`, `maria_*`, `player_*`, `quest_*` allowed

---

## 🖥️ UI Components & Patterns (v3.2)

### StartupDialog Flow
```python
# Inizializzazione in _async_init()
await self.engine.initialize_database()
dialog = StartupDialog(self)
dialog.load_saves_sync()  # Carica salvataggi dal DB

# Struttura tabs:
# - [GM] New Game: selezione mondo/companion
# - [L] Load Game: lista salvataggi da database
# - ⚙️ Settings: RunPod/Local mode
```

### UI Widgets Dinamici

#### HaremProgressWidget (Dinamico v3.2)
```python
# Inizializzazione con lista companion del mondo
companion_names = list(companions.keys())
self.harem_progress.set_companions(companion_names)

# Aggiornamento progresso
self.harem_progress.update_progress(conquered_list)  # ["Luna", "Stella"]
```

#### QuestEngine.get_ui_milestone_status()
```python
# Metodo per ottenere milestone formattati per UI
milestones = self.quest_engine.get_ui_milestone_status(
    "Luna", game_state
)
# Returns: [{"id": "luna_trust", "name": "Her Trust", "icon": "🔓", "reached": True}, ...]
```

### Pattern Fix v3.2

#### Fix: PersonalityEngine Pydantic Access
```python
# ❌ ERRATO (tratta Pydantic model come dict)
config = companions_dict.get(c1)  # CompanionV3Config
psych = config.get("psychology", {})  # AttributeError!

# ✅ CORRETTO (dot notation per Pydantic)
if config and config.personality_system:
    rel_config = config.personality_system.relationship.get(c2, {})
```

#### Fix: Video Action Parameter
```python
# ❌ ERRATO (hardcoded)
video_path = await self.engine.generate_video(
    image, action="posing", ...  # Ignora input utente
)

# ✅ CORRETTO (usa input utente)
user_action = dialog.get_action() or "posing"
video_path = await self.engine.generate_video(
    image, action=user_action, user_action=user_action, ...
)
```

---

## 🎭 Dialogue Tone System (NUOVO - Feb 2026)

**Tono di voce modulare per personaggio, basato su affinità.**

### YAML Structure (per personaggio)
```yaml
dialogue_tone:
  base: "Descrizione base del tono"
  
  affinity_tiers:
    0-25:
      name: "Tier Name"
      tone: "Descrizione specifica del tono"
      examples:
        - "Frase esempio 1"
        - "Frase esempio 2"
      voice_markers:
        - "Usa 'Lei' formale"
        - "Cognomi solo"
    
    26-50:
      name: "Tier Name"
      tone: "..."
      examples: [...]
      voice_markers: [...]
```

### Esempio: Luna (Teacher)
| Affinità | Tier | Tono | Frasi Esempio |
|----------|------|------|---------------|
| 0-25 | The Strict Teacher | Ghiaccio, formale | "Signor..., lei è in ritardo" |
| 26-50 | The Caring Teacher | Professionale ma osservante | "Ha studiato, signor...?" |
| 51-75 | The Private Tutor | Calda, usa nome | "Enrico... mi sorprende" |
| 76-100 | The Forbidden Affair | Intima, sussurrata | "Chiamami Luna..." |

### Esempio: Stella (Student)
| Affinità | Tier | Tono | Frasi Esempio |
|----------|------|------|---------------|
| 0-20 | The Snob | Sfacciata, "loser" | "Ehi tu, spostati. Sfigato" |
| 21-50 | The Tsundere | Balbuzie, nega | "N-non è che mi importi!" |
| 51-80 | The Girlfriend | Gelosa, appiccicosa | "Chi è quella che ti guardava?" |
| 81-100 | The Lover | Dichiarazioni | "Ti amo, idiota. Voglio che tu sia il mio primo" |

### Esempio: Maria (Nurse)
| Affinità | Tier | Tono | Frasi Esempio |
|----------|------|------|---------------|
| 0-25 | The Professional | Distaccata medica | "Si accomodi, signor..." |
| 26-50 | The Caring | Materna, tocco lungo | "Povero... vieni qui, lascia che ti coccoli" |
| 51-75 | The Temptress | Doppi sensi medici | "Questo è un trattamento speciale..." |
| 76-100 | The Obsessive | Possessiva, yandere | "Non ti curo più... ti TERRO qui" |

### Dynamic Loading
```python
# In engine.py
self._build_dialogue_tone(char_name, current_aff)

# Seleziona automaticamente il tier corretto in base all'affinità
# Genera testo con esempi e voice markers per l'LLM
```

---

## 👤 NPC Generici Support (Feb 2026)

**Supporto per personaggi non-companion (bibliotecaria, infermiere, ecc.)**

### Problema Risolto
Prima: NPC generici venivano renderizzati con LoRA di Luna (sbagliato!)
Dopo: NPC generici usano `NPC_BASE` senza LoRA personaggio-specifici

### Meccanismo
```python
# single_builder.py
known_companions = {"Luna", "Stella", "Maria"}
is_known_companion = char_name in known_companions

if is_known_companion:
    base_raw = BASE_PROMPTS[char_name]  # Con LoRA specifico
else:
    base_raw = NPC_BASE  # Generico, senza LoRA
```

### Scene Analyzer Fix
```python
# scene_analyzer.py - NON forzare primary_subject a None
if primary and primary not in available:
    # Prima: primary = None  ❌
    # Dopo: mantieni primary  ✅ (permette "bibliotecaria")
```

### Engine Fix
```python
# _build_scene_analysis_from_response
predicted_subject = predictive_analysis.get("primary_subject")
if predicted_subject:
    primary = predicted_subject  # Usa il soggetto predetto
else:
    primary = self.state.current.companion_name  # Fallback
```

---

## 🐛 Bug Fixes (Feb 2026)

| Fix | File | Descrizione |
|-----|------|-------------|
| **Dialogue Tone System** | `luna.yaml`, `stella.yaml`, `maria.yaml` | Tono modulare per affinità |
| **Dialogue Tone Loader** | `world_loader.py` | Caricamento dialogue_tone dinamico |
| **Dialogue Tone Engine** | `engine.py` | `_build_dialogue_tone()` method |
| **NPC Generic Support** | `single_builder.py`, `scene_analyzer.py` | Supporto personaggi non-companion |
| **LoRA Stella Fix** | `comfy_image_client.py` | Stella usa `alice_milf_catchers` non `stsDebbie` |
| **Affinity Companion Name** | `llm_client.py` | Fix `companion_name` param per affinity_change |
| **Scene Primary Subject** | `engine.py` | Usa `predicted_subject` se disponibile |
| **Outfit sd_prompt** | `base.py` | Usa `sd_prompt` dal YAML se disponibile |

---

**Ultimo aggiornamento**: Feb 2026 (Dialogue Tone System, NPC Generic Support, Bug Fixes)
**Versione**: 3.3.0-dialogue-tone
