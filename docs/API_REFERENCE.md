# API Reference - Luna RPG v3

## Core Models

### GameSession
```python
class GameSession(BaseModel):
    id: Optional[int]
    world_id: str
    companion_name: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    turn_count: int = 0
    location: str = "Unknown"
    time_of_day: str = "Morning"
    current_outfit: str = "default"
    gold: int = 0
    hp: int = 20
    stats: Dict[str, int] = {"strength": 10, "mind": 10, "charisma": 10}
    affinity: Dict[str, int] = {}
    npc_states: Dict[str, Dict[str, Any]] = {}
    inventory: List[str] = []
    quest_log: List[str] = []
    flags: Dict[str, Any] = {}
```

### SceneAnalysis
```python
class SceneAnalysis(BaseModel):
    primary_subject: Optional[str]      # Focus principale
    secondary_subjects: List[str]       # Altri personaggi visibili
    background_mentions: List[str]      # Personaggi nominati ma non visibili
    composition_type: CompositionType   # close_up/medium_shot/wide_shot/group
    action_focus: str                   # Azione principale
    frame_type: str                     # Tipo inquadratura
    reasoning: str                      # Spiegazione scelta
```

### LLMResponse
```python
class LLMResponse(BaseModel):
    text: str                           # Narrativa italiana
    visual_en: Optional[str]            # Descrizione scena per SD
    tags_en: List[str]                  # Tag tecnici SD
    body_focus: Optional[str]           # Parte corpo in focus
    approach_used: Optional[str]        # standard/physical_action/question/choice
    updates: GameStateUpdate            # Aggiornamenti stato
```

### GameStateUpdate
```python
class GameStateUpdate(BaseModel):
    location: Optional[str]
    current_outfit: Optional[str]
    time_of_day: Optional[str]
    gold: Optional[int]
    hp: Optional[int]
    add_item: Optional[str]
    remove_item: Optional[str]
    flags: Dict[str, Any] = {}
    affinity_change: Dict[str, int] = {}
    npc_updates: Dict[str, Dict[str, Any]] = {}
    new_fact: Optional[str]
    stat_changes: Dict[str, int] = {}
```

## Core Classes

### GameEngine

#### `__init__()`
Inizializza engine con tutti i client.

#### `async initialize_database()`
Crea tabelle database.

#### `async create_game(db, world_id, companion_name) -> GameSession`
Crea nuova partita.

**Args:**
- `db`: AsyncSession
- `world_id`: str - ID mondo (es. "school_life")
- `companion_name`: str - Nome companion iniziale

**Returns:** GameSession

#### `async load_game(db, session_id) -> Optional[GameSession]`
Carica partita esistente.

#### `async process_turn(db, user_input, generate_image=True, generate_audio=False) -> Dict`
Processa un turno completo.

**Returns:**
```python
{
    "text": str,                    # Narrativa
    "scene_analysis": SceneAnalysis,
    "visual_en": str,
    "tags_en": List[str],
    "updates": GameStateUpdate,
    "image_path": Optional[Path],
    "audio_played": bool
}
```

#### `async generate_video(image_path, action, narrative_context, visual_description) -> Optional[Path]`
Genera video da immagine.

### StateManager

#### `async create_new(db, world_id, companion_name, world_data) -> GameSession`
Crea nuova sessione.

#### `async load(db, session_id) -> Optional[GameSession]`
Carica sessione.

#### `async update(db, updates: GameStateUpdate)`
Applica aggiornamenti.

#### `async switch_companion(db, new_companion, world_data)`
Cambia companion attivo.

#### `def get_personality_for_affinity(char_name, world_data) -> str`
Ottiene descrizione personalità basata su affinità.

### MemoryManager

#### `async get_context_block(db) -> str`
Costruisce blocco contesto per LLM.

#### `async get_recent_history(db, limit=50) -> List[dict]`
Recupera history recente.

#### `async add_message(db, role, content, turn_number, visual_en, tags_en)`
Aggiunge messaggio.

#### `async add_fact(db, fact, turn_number)`
Aggiunge fatto permanente.

### DatabaseManager

#### `async create_game_session(db, world_id, companion_name, affinity) -> SessionModel`

#### `async get_session_by_id(db, session_id) -> Optional[SessionModel]`

#### `async get_recent_messages(db, session_id, limit=50) -> List[MessageModel]`

#### `async add_message(db, session_id, role, content, turn_number, visual_en, tags_en) -> MessageModel`

#### `async add_memory(db, session_id, mem_type, content, turn_number, importance) -> MemoryModel`

#### `@asynccontextmanager async get_session() -> AsyncIterator[AsyncSession]`

**Usage:**
```python
async with db_manager.get_session() as db:
    result = await db.execute(query)
    # Commit automatico se no exception
```

## Media Clients

### LLMClient

#### `async generate_response(user_input, system_instruction, history, memory_context) -> LLMResponse`

**Args:**
- `user_input`: str - Input utente
- `system_instruction`: str - System prompt completo
- `history`: List[Dict[str, str]] - Messaggi recenti
- `memory_context`: str - Blocco memoria

#### `async summarize(messages) -> str`
Riassume lista messaggi.

### ComfyImageClient

#### `async generate(prompt_result, character_name, save_dir) -> Optional[Path]`

**Args:**
- `prompt_result`: PromptResult
- `character_name`: str - Per naming file
- `save_dir`: Optional[Path]

### VideoClient

#### `async generate(llm_client, image_path, context, character, location, action, save_dir, motion_speed) -> Optional[Path]`

**Args:**
- `llm_client`: LLMClient - Per generare temporal prompt
- `image_path`: Path - Immagine sorgente
- `context`: str - Contesto narrativo
- `character`: str - Nome personaggio
- `location`: str - Location corrente
- `action`: str - Azione da animare
- `motion_speed`: int - Velocità movimento (default 6)

### AudioClient

#### `async speak(text, character_name) -> bool`

**Args:**
- `text`: str - Testo da pronunciare (max 400 char)
- `character_name`: str - Luna/Stella/Maria/Narrator

## Prompt Builders

### SingleCharacterBuilder

#### `build(scene, visual_en, tags_en, game_session, world_data, body_focus) -> PromptResult`

### MultiCharacterBuilder

#### `build(scene, visual_en, tags_en, game_session, world_data, body_focus) -> PromptResult`

### NPCBuilder

#### `build(npc_type, visual_en, tags_en, game_session, world_data) -> PromptResult`

## Config

### Settings

```python
class Settings(BaseSettings):
    execution_mode: Literal["LOCAL", "RUNPOD"]
    llm_provider: Literal["gemini", "moonshot"]
    gemini_api_key: str
    moonshot_api_key: str
    runpod_id: Optional[str]
    runpod_api_key: Optional[str]
    local_sd_url: str = "http://127.0.0.1:7860"
    local_comfy_url: str = "http://127.0.0.1:8188"
    database_url: str = "sqlite+aiosqlite:///storage/saves/luna_v3.db"
```

#### Properties
- `is_runpod: bool`
- `sd_url: str`
- `comfy_url: Optional[str]`
- `video_available: bool`

---

**Document Version**: 1.0
**Last Updated**: 2026-02-03
