# Architettura Tecnica Luna RPG v3

## Overview Architetturale

Luna RPG v3 segue un'architettura **async-first** con separazione netta tra:
- **Core**: Logica di gioco e orchestrazione
- **Media**: Client per API esterne
- **UI**: Interfaccia utente PySide6
- **Storage**: Persistenza SQLite

```
┌─────────────────────────────────────────────────────────────────┐
│                          UI Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ startup_dialog│  │ main_window  │  │ async event handlers │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ async calls
┌──────────────────────────▼──────────────────────────────────────┐
│                        Core Engine                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ GameEngine   │  │ StateManager │  │ MemoryManager        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ SceneAnalyzer│  │WorldLoader   │  │ Prompt Builders      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   Database   │  │   LLM Client    │  │   Media    │
│   SQLite     │  │  Gemini/Moonshot│  │ Image/Video│
└──────────────┘  └─────────────────┘  └────────────┘
```

## Game Loop Dettagliato

### 1. Input Processing

```python
# main_window.py
async def _on_send(self):
    text = self.input_field.text()
    await self._process_turn(text)
```

### 2. Turn Processing

```python
# engine.py
async def process_turn(self, db, user_input, ...):
    # 2.1 Predictive Analysis (euristica)
    analysis = self._analyze_user_intent(user_input)
    
    # 2.2 Companion Switch
    if analysis.primary_subject != current:
        await self.state.switch_companion(db, new_companion)
    
    # 2.3 Build System Prompt
    system_prompt = self._build_system_prompt_with_analysis(analysis)
    
    # 2.4 LLM Generation
    response = await self.llm.generate_response(...)
    
    # 2.5 Update State
    await self.state.update(db, response.updates)
    
    # 2.6 Generate Image
    image_path = await self._generate_image(scene_analysis)
    
    return {"text": response.text, "image_path": image_path, ...}
```

### 3. State Persistence

```python
# state_manager.py
async def update(self, db, updates):
    # Update in-memory
    self._session.location = updates.location
    
    # Update database
    self._db_session.location = updates.location
    await db.commit()
```

## Database Architecture

### Schema Completo

```sql
-- Sessioni di gioco (stato principale)
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY,
    world_id TEXT NOT NULL,
    companion_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    turn_count INTEGER DEFAULT 0,
    location TEXT DEFAULT 'Unknown',
    time_of_day TEXT DEFAULT 'Morning',
    current_outfit TEXT DEFAULT 'default',
    gold INTEGER DEFAULT 0,
    hp INTEGER DEFAULT 20,
    stats JSON DEFAULT '{}',
    affinity JSON DEFAULT '{}',
    npc_states JSON DEFAULT '{}',
    inventory JSON DEFAULT '[]',
    quest_log JSON DEFAULT '[]',
    flags JSON DEFAULT '{}'
);

-- Messaggi (history conversazione)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES game_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' o 'model'
    content TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    visual_en TEXT DEFAULT '',
    tags_en JSON DEFAULT '[]'
);

-- Memorie a lungo termine
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES game_sessions(id) ON DELETE CASCADE,
    type TEXT NOT NULL,  -- 'summary', 'fact', 'event'
    content TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    importance INTEGER DEFAULT 5
);
```

## Prompt Builder Architecture

### Class Hierarchy

```
PromptResult (dataclass)
├─ positive: str
├─ negative: str
├─ width: int
└─ height: int

Base Prompts (constants)
├─ BASE_PROMPTS: Dict[str, str]  # Luna, Stella, Maria
├─ NPC_BASE: str
├─ NEGATIVE_BASE: str
└─ ANTI_FUSION_NEGATIVE: str

Builders
├─ SingleCharacterBuilder
│  └─ build(scene, visual_en, tags_en, game_session, world_data)
├─ MultiCharacterBuilder
│  └─ build(scene, visual_en, tags_en, game_session, world_data)
└─ NPCBuilder
   └─ build(npc_type, visual_en, tags_en, game_session, world_data)
```

### SingleCharacterBuilder Flow

```python
def build(scene, visual_en, tags_en, game_session, world_data):
    # 1. Get character base prompt
    base = BASE_PROMPTS.get(char_name, NPC_BASE)
    
    # 2. Get outfit from wardrobe
    outfit = get_outfit_for_character(char_name, outfit_key, ...)
    
    # 3. Clean tags (remove duplicates)
    clean_tags = [t for t in tags_en if t not in base.lower()]
    
    # 4. Assemble
    parts = [
        base,
        outfit,
        ", ".join(clean_tags),
        visual_en,
        body_focus_boost
    ]
    
    return PromptResult(
        positive=", ".join(parts),
        negative=NEGATIVE_BASE,
        width=896,
        height=1152
    )
```

## LLM Client Architecture

### Multi-Provider Strategy

```
User Request
    ↓
Primary Provider (Moonshot)
    ↓
[Success?] ──Yes──→ Return
    ↓ No
Retry with backoff
    ↓
[Success?] ──Yes──→ Return
    ↓ No
Fallback Provider (Gemini)
    ↓
[Success?] ──Yes──→ Return
    ↓ No
Return error message
```

### JSON Mode Parsing

```python
# llm_client.py _generate_moonshot_json()
payload = {
    "model": "kimi-k2-turbo-preview",
    "messages": messages,
    "response_format": {"type": "json_object"}  # Forza JSON
}

# Parsing
json_data = json.loads(raw_text)
result = LLMResponse(
    text=json_data["text"],
    visual_en=json_data["visual_en"],
    tags_en=json_data["tags_en"],
    ...
)
```

## Memory Management

### Compression Strategy

```
Message Buffer (50 messages)
    ↓
[Overflow?] ──No──→ Continue
    ↓ Yes
Select oldest 20 messages
    ↓
LLM Summarize
    ↓
Save to memories table (type='summary')
    ↓
Delete old messages from buffer
```

### Context Injection

```python
# memory_manager.py
async def get_context_block(db):
    parts = []
    
    # 1. Facts (permanent knowledge)
    facts = await db.get_memories(type="fact")
    parts.append("🧠 KNOWLEDGE BASE:")
    for f in facts:
        parts.append(f"- {f.content}")
    
    # 2. Summaries (compressed history)
    summaries = await db.get_memories(type="summary")
    parts.append("📜 STORY SO FAR:")
    for s in summaries:
        parts.append(f"- {s.content}")
    
    return "\n".join(parts)
```

## Video Generation Pipeline

### Workflow Wan2.1

```
Image Input
    ↓
LoadImage (nodo 1)
    ↓
CLIP + VAE + UNet (High/Low noise)
    ↓
CLIPTextEncode (prompt positivo/negativo)
    ↓
WanFirstLastFrameToVideo
    ↓
KSamplerAdvanced (2 passaggi)
    ↓
VAEDecode
    ↓
VHS_VideoCombine
    ↓
MP4 Output
```

### VRAM Management

```python
# Pre-video
await image_gen.unload_model()  # Libera VRAM SD

# Post-video
for i in range(5):
    await session.post(f"{comfy_url}/free", ...)
    await asyncio.sleep(3 + i * 2)
await asyncio.sleep(20)  # Attesa finale
```

## Error Handling Strategy

### Layer 1: API Level
- Timeout handling
- Retry with exponential backoff
- Provider fallback

### Layer 2: Business Logic
- Validation input utente
- State consistency checks
- Database transaction rollback

### Layer 3: UI
- Error display in story log
- Status bar updates
- Graceful degradation

---

**Document Version**: 1.0
**Last Updated**: 2026-02-03
