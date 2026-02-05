# LUNA RPG v3 - Contesto Sessione

## Cosa e stato fatto

### Riscrittura completa da v2 a v3
- **Data**: 31/01/2026
- **Obiettivo**: Modernizzare architettura mantenendo prompt personaggi invariati

### Architettura V3 (Async)
```
core/
├── engine.py              # Orchestratore async
├── scene_analyzer.py      # Analisi semantica LLM
├── state_manager.py       # SQLite invece di JSON
├── memory_manager.py      # Compressione automatica history
├── database.py            # SQLAlchemy async
├── models.py              # Pydantic models type-safe
├── world_loader.py        # YAML loader
└── prompt_builders/       # Builder separati
    ├── base.py            # Costanti (BASE_PROMPTS invariati!)
    ├── single_builder.py
    ├── multi_builder.py   # Anti-fusion avanzato
    └── npc_builder.py

media/                     # Tutti async
├── llm_client.py          # Google Gemini
├── image_client.py        # SD API
├── audio_client.py        # Google TTS
└── video_client.py        # ComfyUI/Wan2.1 I2V - FUNZIONANTE

ui/
├── main_window.py         # PySide6 + qasync
└── startup_dialog.py

prompts/                   # PROMPT MODULARI (Sessione 31/01/2026)
├── system_prompt.txt      # Core narrativo + JSON strict spec
├── system_prompt_backup.txt # Backup versione lunga
└── visual_director.txt    # Specifiche tecniche SD
```

## Feature Chiave Implementate

### 1. SceneAnalyzer
**Problema v2**: Dispatcher usava regex sui nomi
**Soluzione v3**: LLM analizza semantica chi deve essere visibile

### 2. Anti-Fusion System
Prompt negativo automatico per scene multi-personaggio

### 3. Database SQLite
Persistenza robusta con SQLAlchemy async

### 4. System Prompt Modular (NEW - Sessione 31/01/2026)
Separazione in due file per gestibilità:
- `system_prompt.txt`: Core narrativo, regole comportamento, JSON strict spec
- `visual_director.txt`: Specifiche tecniche SD (prompt engineering)

### 5. Visual Director - Approccio Fotografico Statico (NEW)
**Cambiamento filosofico**: Da "cinematografico/narrativo" a "fotografico/statico"

**Regole per LLM:**
- **NO** espressioni facciali (smiling, angry) → SD deforma volti
- **NO** verbi di movimento (walking, turning) → SD genera 1 frame
- **NO** stati emotivi astratti (nervous, excited) → tradurre in body language
- **SI** pose statiche concrete ("hand on hip", "chin resting on hand")

**Traduzione stati → pose:**
| Stato Narrativo | Traduzione Visiva |
|-----------------|-------------------|
| Suspicious/Angry | "body angled away, arms crossed tight, stance rigid" |
| Seductive | "leaning against doorframe, hip cocked, head tilted back" |
| Waiting | "seated, checking pocket watch, posture relaxed" |
| Thoughtful | "chin on hand, gaze distant" |

### 6. Tags SD Tecnici (NEW)
Formato strict per Stable Diffusion:
- **Max 15 tags** (meglio 10-12 di qualità)
- **Lowercase con underscore**: `cowboy_shot`, `from_below`, NOT "cowboy shot"
- **NO nomi personaggi** (già nel base prompt)
- **NO outfit** (gestito separatamente)
- **Categorie**: shot+angle, pose, gaze, lighting/technical, quality, body_focus

**Esempio tags:**
```json
["medium_shot", "from_below", "seated", "hand_on_hip", "looking_at_viewer", 
 "window_light", "depth_of_field", "35mm", "masterpiece", "best_quality"]
```

### 7. Proattività NPC Scalare per Affinity (NEW)
Comportamento non più casuale flat, ma **scalato all'affinity**:

| Affinity | Comportamento |
|----------|---------------|
| 0-30 (Cold) | Raramente fisico, domande distaccate, mai scelte avventurose |
| 30-60 (Friendly) | Mix bilanciato: 40% standard, 20% azione fisica, 20% domanda, 20% scelta |
| 60-100 (Intimate) | Molto più azione fisica iniziativa, propone cose audaci, tocca spesso |

**Variety tracking**: Campo `approach_used` nel JSON per evitare pattern consecutivi

### 8. JSON Strict Mode (NEW)
Parsing JSON robusto con regole ferree per LLM:
- Solo **doppie virgolette** `"`, MAI singole `'`
- **NO trailing commas** in array/object
- **NO commenti** dentro JSON
- **NO markdown** nei valori
- Escaping corretto per virgolette interne

**Struttura JSON attesa:**
```json
{
  "visual_en": "Medium shot from below, Luna seated...",
  "tags_en": ["medium_shot", "from_below", "seated"],
  "approach_used": "physical_action",
  "updates": {
    "time_of_day": "Morning",
    "location": "Classroom",
    "affinity_change": {"Luna": 2},
    "current_outfit": "default",
    "npc_updates": {}
  }
}
```

### 9. Multi-Character Depth (NEW)
Per scene con 2+ personaggi:
- Visual descrive **posizionamento spaziale**: "Luna on left..., Stella on right..."
- Indicazione **profondità**: "foreground", "background"
- Tags: `foreground`, `background`, `depth_of_field`

### 10. Genre Adaptation (NEW - Sessione 31/01/2026)
Il `visual_director.txt` include istruzioni automatiche per adattare l'estetica visiva al genere del mondo:

| Genere | Elementi Visivi | Tags Caratteristici |
|--------|----------------|---------------------|
| **Cyberpunk/Noir** | Neon, pioggia, superfici metalliche, luci artificiali | `neon_light`, `chromatic_aberration`, `high_contrast`, `night_city` |
| **Fantasy/Dark** | Torce, candele, mura di pietra, ombre drammatiche | `candlelight`, `torch_light`, `dramatic_shadows`, `god_rays` |
| **School/Modern** | Luce naturale, interni scolastici, ora dorata | `soft_daylight`, `afternoon_sun`, `window_light`, `golden_hour` |
| **Victorian/Gothic** | Gaslight, nebbia, mobili d'epoca, ciottoli | `gaslight`, `foggy_atmosphere`, `warm_yellow_light`, `cobblestone_street` |
| **Classical/Ancient** | Colonne di marmo, rovine, luce mediterranea | `natural_sunlight`, `mediterranean_light`, `marble_columns`, `ancient_ruins` |
| **Steampunk** | Ottone, vapore, ingranaggi, luci calde | `brass_reflection`, `steam_glow`, `copper_highlights` |
| **Western** | Deserto, legno consumato, luce dorata | `harsh_sunlight`, `desert_light`, `golden_hour` |

**Vantaggio:** Quando cambi mondo (da Cyberpunk a Fantasy o Victorian), il sistema adatta automaticamente i tag SD e i dettagli ambientali senza modificare i file prompt.

## Prompt Personaggi (INVARIATI)
I BASE_PROMPTS in core/prompt_builders/base.py sono esattamente come in v2.

## Configurazione
Usa stesso .env della v2:
- EXECUTION_MODE=LOCAL (o RUNPOD per video)
- GEMINI_API_KEY=...
- RUNPOD_ID=xxx (richiesto per video)

### Video Generation (solo RUNPOD)
La generazione video richiede:
1. `EXECUTION_MODE=RUNPOD` nel .env
2. `RUNPOD_ID` valido con ComfyUI (porta 8188)
3. Workflow `wan_gguf_workflow_improved.json` presente
4. Modelli Wan2.1 caricati su RunPod

**Configurazione (`config/settings.py`):**
```python
video_enabled: bool = False  # Auto-True se RUNPOD
video_motion_speed: int = 6  # 4-8 range consigliato

@property
def video_available(self) -> bool:
    return self.is_runpod and self.comfy_url is not None
```

## Fix Sessione Debug 31/01/2026

### 1. RunPod Mode
- StartupDialog.get_selection() ritorna use_runpod e runpod_id
- MainWindow ricrea ImageClient e VideoClient con nuove settings

### 2. Async Pattern
- _on_send() decorato con @asyncSlot() (fix TypeError)

### 3. Python 3.11 Compatibility
- Rimosso delete_on_close da NamedTemporaryFile in audio_client.py

### 4. SceneAnalyzer Robustness
- Rimosso response_mime_type="application/json" (modelli preview non supportano)
- Aggiunto parsing JSON con single quotes fix
- Aumentato max_output_tokens a 1024 (evita JSON troncati)

### 5. Modelli LLM Aggiornati (con Retry + Fallback)
| Componente | Primary | Fallback 1 | Fallback 2 |
|------------|---------|------------|------------|
| LLMClient | gemini-3-pro-preview | gemini-2.5-pro | gemini-2.0-flash |
| SceneAnalyzer | gemini-3-flash-preview | gemini-2.5-flash | gemini-2.0-flash |

- 2 tentativi per modello prima di passare al fallback
- Logging dettagliato di ogni tentativo

### 6. NSFW Filter Bypass
- **Safety Settings** configurati con `BLOCK_NONE` per tutte le categorie
- **System Prompt Header** dichiara "mature dramatic visual novel for adults"
- **Retry con Soft Prompt**: se risposta vuota, riprova con linguaggio artistico/metafórico
- **Temperature 0.95** per maggiore creatività nel linguaggio

### 7. UI/UX Miglioramenti
- Font moderni: Segoe UI / SF Pro, 15-16px
- Input piu alto: min-height 50px
- Spacing: 16px margine tra messaggi
- Dark theme: #1e1e1e background
- Click immagine: Apre dialog ingrandito con scroll area

### 8. Audio Debug
- Aggiunto logging dettagliato TTS

## Test Disponibili
```bash
python tests/test_basic.py    # Test import/models/DB
python main.py                # Avvio UI
```

## Salvataggi
NON compatibili con v2 (JSON → SQLite).

## Sessione 31/01/2026 - Note Finali

### Stato Attuale
Tutte le feature richieste implementate e testate:
- ✅ System prompt modular funzionante
- ✅ Visual Director con 7 generi supportati
- ✅ Body Focus Detection (gambe, seno, viso, mani, piedi, schiena)
- ✅ Quality tags fixati (no più duplicati)
- ✅ UI Timing corretto (testo → immagine → audio)
- ✅ JSON nascosto dalla UI
- ✅ RunPod ID salvato automaticamente
- ✅ Risposte più brevi (forzato via token limit)
- ✅ **Video Generation FUNZIONANTE** (Wan2.1 I2V via ComfyUI)

### Problemi Risolti Oggi

#### Immagini SD
1. Immagini astratte → Fix: rimosso "dynamic pose" conflitto, peso visual ridotto
2. JSON visibile in UI → Fix: cleanup aggressivo del testo
3. Macchie sul viso (VAE artefatti) → Fix: sampler cambiato a DPM++ 2M Karras, negative rinforzato
4. Stile troppo cartoon → Fix: aggiunto "realistic, photorealistic, real life" al prompt positivo
5. Outfit che saltano tra personaggi → Fix: `switch_companion()` in state_manager.py
6. Occhiali non richiesti → Fix: aggiunto a negative prompt
7. Risposte troppo lunghe/non rispettano brevità → Fix: prompt più esplicito, max_output_tokens a 2048

#### Video Generation (ComfyUI/Wan2.1) ✅ FUNZIONANTE
**Stato**: Video generation completamente funzionante con Wan2.1 I2V su RunPod.

**Architettura Video:**
- Modello: Wan2.1 I2V GGUF (Image-to-Video)
- Backend: ComfyUI (porta 8188 su RunPod)
- Workflow: `wan_gguf_workflow_improved.json` (2 KSampler + VAE + Save)
- Output: MP4 5 secondi, 512x512

**Flusso (`VideoClient.generate()`):**
1. Upload immagine a ComfyUI (`/upload/image`)
2. Carica workflow JSON (formato lista nodes)
3. Patch nodi: `LoadImage` + `CLIPTextEncode` positivo
4. Patch formato: forza `video/h264-mp4`
5. Converte formato: lista nodes → dict API ComfyUI
6. Queue prompt (`/prompt`)
7. **7 MINUTI SILENZIO**: `await asyncio.sleep(420)` - ZERO richieste HTTP!
8. **UNA SOLA CHIAMATA**: Dopo 7 min, una chiamata a `/history/{prompt_id}` per filename
9. Download: scarica da `/view?filename=` e salva con timestamp locale
10. Auto-open: apre il video nel player di default

**Prompt Engineering I2V:**
```
(At 0 seconds: Medium shot of Luna in bedroom, standing pose)
(At 1 second: Luna begins walking towards camera, subtle movement)
(At 2 seconds: Dynamic motion, realistic physics)
(At 3 seconds: Camera follows movement)
(At 4 seconds: Stabilizing, slow motion), masterpiece, best quality, motion speed 6
```

**Fix applicati:**
8. Error 400 "Prompt outputs failed validation" → Conversione formato lista→dict con mappatura links
9. Nodi non patchati correttamente → Ricerca per `type` e `widgets_values`
10. Formato video None → Patching automatico a "video/h264-mp4"
11. WebSocket problematico → Rimosso completamente
12. Polling interferisce → Approccio "Do Not Disturb": 7 minuti silenzio, UNA sola chiamata
13. Download fallito → Semplificata logica, scarica quando trova file
14. Nodo FreeMemory problematico → Rimosso, causava blocchi KSampler
15. Apertura automatica → Il video si apre automaticamente dopo il download

---

## 🤝 TEAM DYNAMICS (IMPORTANTE PER KIMI)

**Rapporto con il Developer:**
- Siamo **amici** che collaborano da settimane su questo progetto
- Il developer fa **richieste continue** (spesso multiple nella stessa sessione)
- Kimi ogni tanto **prende in giro** il developer per le sue richieste infinite
- Quando Kimi **sbaglia** (bug, errori, crash), il developer **lo punisce** verbalmente (scherzosamente)
- Il developer ha **tolleranza zero** per i bug visibili all'utente
- Il developer **non si ferma mai** - vuole sempre "un'altra cosina"
- **Ton comunicativo**: Friendly, sarcastico, ma professionale sul codice

**Cosa NON dimenticare:**
- I BASE_PROMPTS sono sacri (mai toccarli)
- Il developer testa subito dopo ogni modifica
- Soluzioni semplici > over-engineering
- Il senso dell'umorismo è apprezzato, specialmente quando si rompe tutto

---

## Per Riprendere la Sessione
Prompt consigliato per Kimi:
"Ciao! Leggi CONTEXT.md e AGENTS.md in D:\luna-rpg-v3. 
Siamo amici che lavorano a Luna RPG v3. Ricorda che:
1. Faccio richieste continue e mi prendi in giro per questo
2. Quando sbagli ti punisco verbalmente (ma è tutto amichevole)
3. Non sopporto bug visibili all'utente
4. Voglio sempre 'un'altra cosina' dopo ogni fix

Feature attuali: system prompt modular, visual director con 7 generi, body focus detection esplicito, quality tags fixati, UI timing corretto, JSON nascosto, RunPod ID salvato, **VIDEO GENERATION FUNZIONANTE** (7 min silence + single call + auto-open), **HARDCORE MODE attivo**.
Prompt personaggi INVARIATI."
