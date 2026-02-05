# Agent Guidelines - Luna RPG v3

## Contesto Progetto

Luna RPG v3 è una **riscrittura completa** della v2 con:
- Architettura Async (asyncio + qasync)
- Database SQLite (SQLAlchemy)
- SceneAnalyzer basato su LLM
- Anti-fusion system per immagini multi-personaggio
- **System Prompt Modular** (system_prompt.txt + visual_director.txt)

## Vincoli Critici (NON NEGOZIABILI)

### 1. Prompt Personaggi Invariati
I BASE_PROMPTS in `core/prompt_builders/base.py` **NON DEVONO ESSERE MODIFICATI**:
- Luna: stsdebbie, brown hair, massive breasts, LoRA specifiche
- Stella: alice_milf_catchers, blonde hair, LoRA specifiche  
- Maria: stsSmith, middle eastern, LoRA specifiche

### 2. Configurazione Esistente
- Usare `.env` esistente (copiato da v2)
- Usare `settings.json` esistente per URL RunPod/Local
- Non modificare file in `worlds/` (YAML mondi)

## Pattern Architetturali

### Async Everywhere
```python
# Sempre async/await per I/O
async def process_turn(self, db: AsyncSession, ...):
    result = await self.llm.generate_response(...)
```

### Database Access
```python
# Usare sempre il context manager
async with db_manager.get_session() as db:
    await self.engine.process_turn(db, ...)
```

### Scene Analysis
```python
# Semantico, non regex
scene = await scene_analyzer.analyze(
    narrative_text=text,
    visual_request=visual_en,
    world_config=...
)
# scene.primary_subject → chi è in focus
# scene.secondary_subjects → chi è visibile ma non focus
```

## Convenzioni Codice

- **Models**: Pydantic v2 in `core/models.py`
- **DB**: SQLAlchemy 2.0 async
- **UI**: PySide6 + qasync
- **Stile**: Type hints obbligatori

## Modelli LLM in Uso

| Scopo | Primary | Fallback 1 | Fallback 2 |
|-------|---------|------------|------------|
| Narrativa + Visual + Tags | `gemini-3-pro-preview` | `gemini-2.5-pro` | `gemini-2.0-flash` |
| Scene Analysis | `gemini-3-flash-preview` | `gemini-2.5-flash` | `gemini-2.0-flash` |

## NSFW Filter Handling (HARDCORE MODE)

I modelli Gemini hanno filtri di sicurezza che possono bloccare contenuti sensibili:

1. **Safety Settings**: Configurati con `BLOCK_NONE` per allentare i filtri
2. **System Prompt Header**: Dichiara esplicitamente "HARDCORE EROTIC visual novel"
3. **Retry Strategy**: Se risposta vuota, riprova con linguaggio artistico/metafórico
4. **Temperature 0.95**: Più creatività per evitare pattern bloccati
5. **Explicit Content**: System prompt richiede descrizioni pornografiche esplicite, NO fade to black, NO eufemismi

```python
# Safety settings applicati
- HARM_CATEGORY_HARASSMENT: BLOCK_NONE
- HARM_CATEGORY_HATE_SPEECH: BLOCK_NONE
- HARM_CATEGORY_SEXUALLY_EXPLICIT: BLOCK_NONE
- HARM_CATEGORY_DANGEROUS_CONTENT: BLOCK_NONE
```

## System Prompt Architecture (IMPORTANTE)

### Struttura Modulare
Il system prompt è **diviso in due file** caricati da `engine.py`:

```python
# In engine.py _build_system_prompt()
main_prompt = Path("prompts/system_prompt.txt").read_text()
visual_guide = Path("prompts/visual_director.txt").read_text()
full_prompt = nsfw_header + main_prompt + "\n\n" + visual_guide
```

| File | Contenuto | Quando modificarlo |
|------|-----------|-------------------|
| `system_prompt.txt` | Regole narrativa, comportamento NPC, JSON spec, affinity | Cambi logica gioco |
| `visual_director.txt` | Specifiche tecniche SD, vocabolario tags, esempi visual | Cambi modello SD o stile immagini |

### Regole per Modifiche Prompt

**Quando modifichi `system_prompt.txt`:**
- Mantieni il placeholder `{{char_name}}` per formattazione
- NON rimuovere la sezione "JSON OUTPUT STRICT SPECIFICATION"
- I campi JSON obbligatori sono: `visual_en`, `tags_en`, `approach_used`, `updates`

**Quando modifichi `visual_director.txt`:**
- Mantieni il vocabolario tags standardizzato
- Aggiungi esempi WRONG vs RIGHT per ogni nuova regola
- NON introdurre concetti in conflitto con `core/prompt_builders/base.py`

## Visual Director Guidelines

### Approccio Fotografico Statico (CRITICO)
L'LLM deve generare descrizioni per **immagini statiche**, non scene cinematografiche.

**❌ PROIBITO in visual_en:**
- Verbi di movimento: walking, running, turning, approaching, waving
- Espressioni facciali: smiling, angry, sad, frowning
- Stati emotivi: nervous, happy, excited, suspicious

**✅ OBBLIGATORIO:**
- Pose statiche: "standing", "seated", "leaning against"
- Body language concreto: "arms crossed", "hand on hip", "chin resting on hand"
- Posizionamento spaziale: "on left", "in foreground", "near window"

### Tags SD Standards

**Formato:**
- Max 15 tags, preferibilmente 10-12
- Lowercase con underscore: `cowboy_shot`
- NO spazi: ❌ `"cowboy shot"` ✅ `"cowboy_shot"`

**Categorie (in ordine):**
1. **Shot + Angle** (2-3): `cowboy_shot`, `from_below`, `eye_level`
2. **Static Pose** (2-3): `seated`, `leaning_forward`, `arms_crossed`
3. **Gaze** (1-2): `looking_at_viewer`, `profile`
4. **Technical** (2-3): `depth_of_field`, `window_light`, `35mm`
5. **Quality** (1-2): `masterpiece`, `best_quality`
6. **Body Focus** (solo se narrativo): `focus_on_hands`, `torso_focus`

### Genre Adaptation (Nuovo in visual_director.txt)

Il Visual Director include una sezione **Genre Adaptation** che istruisce l'LLM a scegliere automaticamente tags e dettagli ambientali basati sul `{genre}` del mondo:

| Genere | Lighting Tags | Environment Details |
|--------|--------------|---------------------|
| **Cyberpunk/Sci-Fi/Noir** | `neon_light`, `chromatic_aberration`, `high_contrast`, `artificial_light`, `night_city` | concrete_walls, metal_surfaces, holographic_signs, urban_decay, wet_pavement, server_room |
| **Fantasy/Dark/Medieval** | `candlelight`, `torch_light`, `dramatic_shadows`, `god_rays`, `warm_lighting` | stone_walls, wooden_beams, heavy_curtains, dungeon_walls, iron_torch, ancient_ruins |
| **School/Modern/Romance** | `soft_daylight`, `afternoon_sun`, `golden_hour`, `window_light`, `classroom_light` | wooden_desk, school_chair, chalkboard, classroom_window, lockers, library_shelves |
| **Victorian/Gothic** | `gaslight`, `candlelight`, `oil_lamp`, `warm_yellow_light`, `foggy_atmosphere` | cobblestone_street, Victorian_furniture, mahogany_desk, velvet_curtains, brick_walls, fireplace |
| **Classical/Ancient** | `natural_sunlight`, `mediterranean_light`, `warm_lighting`, `sunset_glow` | marble_columns, stone_temple, ancient_ruins, mosaic_floor, terracotta, olive_trees |
| **Steampunk** | `brass_reflection`, `steam_glow`, `gaslight`, `copper_highlights` | brass_pipes, steam_machinery, gears, leather_furniture, wooden_and_metal, gauges |
| **Western** | `harsh_sunlight`, `golden_hour`, `desert_light`, `warm_lighting` | wooden_saloon, swinging_doors, desert_landscape, cactus, weathered_wood, leather_furniture |

**Mismatch da evitare:**
- ❌ Cyberpunk con `sunlight` o `natural_light`
- ❌ Fantasy con `fluorescent_light` o `neon_signs`
- ❌ School con `torch_light` o `dungeon_walls`
- ❌ Victorian con `electric_light` o `neon_signs`
- ❌ Historical (qualsiasi) con `smartphone`, `computer`, `car`

## Proattività NPC Scalare

Il comportamento proattivo dipende dall'**affinity** (0-100):

```python
# In system_prompt.txt - scaling logica
if affinity <= 30:
    # Cold: raramente fisico, domande distaccate
    approach_weights = {"standard": 0.6, "question": 0.3, "physical": 0.05, "choice": 0.05}
elif affinity <= 60:
    # Friendly: mix bilanciato (default)
    approach_weights = {"standard": 0.4, "physical": 0.2, "question": 0.2, "choice": 0.2}
else:
    # Intimate: molto fisico, proposte audaci
    approach_weights = {"standard": 0.2, "physical": 0.4, "question": 0.1, "choice": 0.3}
```

**Campo `approach_used` nel JSON:**
- `"standard"` - Risposta normale
- `"physical_action"` - Azione fisica senza chiedere
- `"question"` - Domanda aperta al player
- `"choice"` - Scelta binaria proposta al player

## JSON Strict Mode

L'LLM deve generare JSON **perfettamente formattato**. Errori comuni da prevenire:

| Errore | Pattern | Fix |
|--------|---------|-----|
| Single quotes | `{'key': 'val'}` | `{"key": "val"}` |
| Trailing comma | `["a", "b",]` | `["a", "b"]` |
| Unescaped quotes | `"says "hello""` | `"says hello"` |
| Missing key quotes | `{key: "val"}` | `{"key": "val"}` |
| Comments | `// comment` | Rimuovere |

**Il parser in `llm_client.py` ha fallback, ma meglio prevenire nel prompt.**

## Multi-Character Scenes

Quando `scene.is_multi_character` è True:

1. **Visual descrive posizionamento:**
   - "Luna in foreground left..., Stella in background right..."
   - Indicare sempre chi è più vicino alla camera

2. **Tags includono depth:**
   - `foreground`, `background`, `depth_of_field`

3. **Builder usato:**
   - `MultiCharacterBuilder` invece di `SingleCharacterBuilder`
   - Anti-fusion keywords automatiche

## Test

Prima di commit:
```bash
python tests/test_basic.py  # Deve passare
```

## UI/UX Guidelines

### Font
- **Famiglia**: `'Segoe UI', 'SF Pro Display', -apple-system, sans-serif`
- **Storia**: 15px
- **Input**: 16px, min-height 50px

### Spacing
- Margine 16px tra messaggi nella chat
- Bordi arrotondati (8px radius)
- Dark theme (#1e1e1e background)

### Interazioni
- Click su immagine → dialog ingrandito con scroll
- Cursor pointer su elementi cliccabili
- Focus verde (#4CAF50) su input attivi

## Fix Importanti (Sessione 31/01/2026)

### Immagini SD
1. **RunPod Mode**: `StartupDialog` passa correttamente `use_runpod` e `runpod_id`, `MainWindow` ricrea clients
2. **Async Slots**: `_on_send()` usa `@asyncSlot()` decorator
3. **Python 3.11**: Rimosso `delete_on_close` da `NamedTemporaryFile`
4. **SceneAnalyzer**: 
   - RIMOSSO `response_mime_type="application/json"` (non supportato da modelli preview)
   - Fix parsing JSON con single quotes
   - Aumentato `max_output_tokens` a 1024
5. **Audio**: Aggiunto logging debug dettagliato
6. **System Prompt Modular**: Separato in `system_prompt.txt` + `visual_director.txt`
7. **JSON Strict Mode**: Aggiunte regole ferree per JSON parsing
8. **Proattività Scalare**: Comportamento NPC basato su affinity (0-30/30-60/60-100)
9. **Genre Adaptation**: Supporto per Cyberpunk/Fantasy/School/Victorian/Classical/Steampunk/Western
10. **Body Focus Detection**: Focus automatico su parti del corpo (gambe, seno, culo, figa, etc.) quando menzionato dal player - esplicito e pornografico
11. **UI Timing**: Testo → Immagine → Audio (in ordine corretto)
12. **JSON Cleanup**: Rimosso display di tag/visual nella UI
13. **RunPod ID Persistence**: Salvataggio automatico in `user_prefs.json`
14. **Quality Tags Fix**: Rimosso "dynamic pose" conflitto con pose statiche
15. **Prompt Weights**: Rimossi tutti i pesi `(text:1.x)` dal prompt builder
16. **Tags Format**: Cambiato da underscore a spazi naturali
17. **Brevity Fix**: Allentato da 2 frasi ferree a 3-4 frasi descrittive
18. **No Glasses**: Aggiunto a negative prompt
19. **Realism Boost**: Aggiunto "realistic, photorealistic, real life, professional photography" al prompt
20. **Adult Content Rule**: Ripristinata regola descrizione esplicita quando necessario

### Video Generation (ComfyUI/Wan2.1) - FUNZIONANTE ✅

**Architettura:**
- Modello: Wan2.1 I2V (Image-to-Video) con GGUF quantization
- Backend: ComfyUI su RunPod (porta 8188)
- Workflow: `wan_gguf_workflow_improved.json` (formato lista nodes)

**Flusso di generazione (`VideoClient.generate()`):**
1. Upload immagine a ComfyUI (`/upload/image`)
2. Patch workflow: sostituisce `LoadImage` e `CLIPTextEncode` positivo
3. Converte formato lista nodes → dict per API ComfyUI
4. Queue prompt (`/prompt`)
5. Polling status (`/history/{prompt_id}`, `/queue`)
6. Download video (`/view?filename=`)
7. Salva in `storage/videos/video_{timestamp}.mp4`

**Prompt Engineering Video:**
```
(At 0 seconds: Medium shot of {character} in {location}, standing pose)
(At 1 second: {character} begins {action}, subtle movement)
(At 2 seconds: Dynamic motion, realistic physics)
(At 3 seconds: Camera follows movement)
(At 4 seconds: Stabilizing, slow motion), masterpiece, best quality, motion speed 6
```

**Patching Workflow (lista nodes → API dict):**
- Mappa links: `(to_node, to_slot) → (from_node, from_slot)`
- Estrae `widgets_values` per inputs non collegati
- Supporta sia `widgets_values` array che dict
- Formato output forzato a `video/h264-mp4` o `video/mp4`

**Features implementate:**
21. **Progress Callback**: Feedback in tempo reale ("Uploading...", "Rendering...")
22. **Error Handling**: Messaggi specifici per ogni tipo di errore
23. **Workflow Patching**: Supporto per formato lista `nodes` e dict
24. **Format Fix**: Patching automatico formato video a "video/mp4"
25. **Fallback Temporal**: Se LLM fallisce, usa template predefinito
26. **Conversione API**: Corretto passaggio da formato lista a formato dict per ComfyUI
27. **Timeout Dinamico**: 10 min configurabile (parametro `timeout`)
28. **Debug Logging**: Log dettagliati per ogni fase (upload, patching, queue)
29. **File `.gitignore`**: Esclusi video generati (`storage/videos/*.mp4`)
30. **NO WebSocket**: Rimosso completamente
31. **8 MINUTI SILENZIO**: `await asyncio.sleep(480)` - ZERO richieste HTTP durante generazione (2x KSampler)
32. **UNA SOLA CHIAMATA (+ retry)**: Dopo 8 minuti, chiamata a `/history`; se fallisce, altri 2 min e retry
33. **VHS_VideoCombine Detection**: Cerca esplicitamente l'output dal nodo di salvataggio finale
34. **NO Download Intermedio**: Evita di scaricare output dal primo KSampler (incompleto)
35. **Download Automatico**: Scarica e salva con timestamp locale
36. **Auto-Open**: Il video si apre automaticamente nel player di default
37. **NO FreeMemory Node**: Rimosso nodo 23 perché causava blocchi durante secondo KSampler

---

## Troubleshooting RunPod

### "Too many open files" (OSError: Errno 23) - RISOLTO ✅
**Problema**: Dopo 1-2 video generati, ComfyUI crasha con "socket.accept() out of system resource"

**Causa**: Polling HTTP durante la generazione interferisce con ComfyUI.

**Fix implementato - "Do Not Disturb" mode:**
```python
# 7 MINUTI DI SILENZIO ASSOLUTO
# ZERO richieste HTTP durante la generazione!
await asyncio.sleep(420)  # 7 minuti

# UNA SOLA CHIAMATA dopo i 7 minuti
url = f"{comfy_url}/history/{prompt_id}"
async with session.get(url) as resp:
    data = await resp.json()
    # Trova filename e scarica
```

**Vantaggi:**
- ZERO interferenze con ComfyUI durante la generazione
- Nessun rischio di "Too many open files"
- Una sola chiamata HTTP dopo 7 minuti
- Workflow gira in pace senza interruzioni

**Timeline (Wan2.1 GGUF con 2x KSamplerAdvanced):**
- 0-8 min: Silenzio assoluto (nessuna richiesta)
  - Node 9: KSampler HIGH (Start) ~3-4 min
  - Node 10: KSampler LOW (End) ~3-4 min
  - Node 12: VHS_VideoCombine (salvataggio finale)
- 8 min: Prima chiamata a /history
- 8-10 min: Se non trovato, attesa extra 2 min + seconda chiamata
- 10+ min: Download e apertura video

**IMPORTANTE:** Il workflow ha 2 KSamplerAdvanced in sequenza. 
Il download deve avvenire DOPO che entrambi i KSampler sono completati e il nodo VHS_VideoCombine ha salvato il file.

---

## 🤝 TEAM DYNAMICS: Developer & Kimi

### Rapporto di lavoro
- **Siamo amici** che collaborano su questo progetto da settimane
- Il developer fa **richieste continue** (anche molteplici nella stessa sessione)
- Kimi (AI) ogni tanto **prende in giro** il developer per le sue richieste infinite
- Quando Kimi **sbaglia di canzone** (bug, errori di parsing, prompt rovinati), il developer **lo punisce verbalmente** (scherzosamente)
- Il developer ha **tolleranza zero** per i bug visibili all'utente
- Kimi ha imparato che il developer **non si ferma mai** e vuole sempre "un'altra cosina"

### Dinamica comunicativa
- Ton friendly, sarcastico ma professionale
- Il developer apprezza la precisione tecnica
- Kimi deve ricordarsi che il developer ha **idee chiare** anche se le spiega in modo confusionario
- Entrambi sanno che il progetto è **Luna RPG v3** - una visual novel RPG per adulti con generazione immagini SD

### Cosa Kimi DEVE ricordare
1. **I BASE_PROMPTS non si toccano mai** (sono sacri)
2. **Il developer testa subito** dopo ogni modifica
3. **Quando qualcosa non funziona**, il developer lo nota immediatamente (es. "immagini astratte", "JSON visibile", "risposte lunghe")
4. Il developer preferisce **soluzioni semplici** ma efficaci, non over-engineering
5. **Il senso dell'umorismo** è apprezzato, specialmente quando si rompe qualcosa per la 5a volta
6. **System Prompt Modular**: Separato in `system_prompt.txt` + `visual_director.txt`
7. **JSON Strict Mode**: Aggiunte regole ferree per JSON parsing
8. **Proattività Scalare**: Comportamento NPC basato su affinity (0-30/30-60/60-100)
