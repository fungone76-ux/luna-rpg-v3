# Developer Guide - Luna RPG v3

## Setup Ambiente di Sviluppo

### 1. Requisiti
- Python 3.11+
- Git
- (Opzionale) CUDA per generazione locale

### 2. Installazione

```bash
# Clone repository
git clone <repo-url>
cd luna-rpg-v3

# Crea virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Installa in modalità development
pip install -e ".[dev]"

# Verifica installazione
python tests/test_basic.py
```

### 3. Configurazione

Crea file `.env`:
```bash
EXECUTION_MODE=LOCAL
LLM_PROVIDER=moonshot
MOONSHOT_API_KEY=sk-tua-chiave
GEMINI_API_KEY=AIzaSy-tua-chiave
```

## Workflow di Sviluppo

### Test Prima di Commit

```bash
# Test base
python tests/test_basic.py

# Type checking
mypy core/ media/ ui/

# Linting
ruff check .
```

### Struttura di un Modulo

```python
"""Breve descrizione modulo."""
from __future__ import annotations

# Imports stdlib
import asyncio
from typing import Optional

# Imports third-party
import aiohttp

# Imports locali
from core.models import GameSession
from config.settings import Settings


class NewClient:
    """Docstring classe."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Inizializza client."""
        self.settings = settings or Settings()
    
    async def do_something(self) -> bool:
        """Fa qualcosa.
        
        Returns:
            True se successo
        """
        try:
            # Implementazione
            return True
        except Exception as e:
            print(f"[!] Error: {e}")
            return False
```

## Aggiungere un Nuovo Mondo

### 1. Crea file YAML

```yaml
# worlds/mio_mondo.yaml
meta:
  id: "mio_mondo"
  name: "Nome del Mondo"
  genre: "Genere"
  world_lore: |
    Descrizione del setting...
  story_structure:
    key_events:
      - "Evento 1"
      - "Evento 2"

npc_logic:
  female_hints: ["nurse", "maid"]
  male_hints: ["guard", "merchant"]

companions:
  NomePersonaggio:
    default_outfit: "default"
    wardrobe:
      default: "descrizione outfit"
      nude: "nude, naked"
    personality_tiers:
      0: "Descrizione tier 0"
      50: "Descrizione tier 50"
```

### 2. Aggiungi BASE_PROMPT (se nuovo personaggio)

```python
# core/prompt_builders/base.py
BASE_PROMPTS = {
    # ... esistenti ...
    "NuovoPersonaggio": (
        "score_9, score_8_up, masterpiece, "
        "trigger_words, description, "
        "<lora:name:0.7>"
    )
}
```

### 3. Test

```python
# Test manuale
from core.world_loader import WorldLoader

loader = WorldLoader()
world = loader.load_world("mio_mondo")
print(world["companions"].keys())
```

## Aggiungere una Feature

### Esempio: Nuovo Tipo di Memoria

```python
# core/memory_manager.py

async def add_quest_memory(self, db, quest_name: str, turn_number: int):
    """Aggiunge memoria quest specifica."""
    await self.db.add_memory(
        db, self.session_id, "quest", 
        f"Quest attiva: {quest_name}", 
        turn_number, 
        importance=9
    )
```

## Debug e Logging

### Logging Pattern Consigliato

```python
# Per info
print(f"[OK] Operazione completata: {result}")

# Per debug
print(f"[?] Debug var: {value}")

# Per warning
print(f"[!] Warning: {message}")

# Per errori
print(f"[ERR] Errore: {e}")
import traceback
traceback.print_exc()
```

### Debug Database

```python
# Leggi sessione direttamente
import asyncio
from core.database import db_manager

async def debug():
    async with db_manager.get_session() as db:
        from core.database import SessionModel
        from sqlalchemy import select
        
        result = await db.execute(select(SessionModel))
        sessions = result.scalars().all()
        for s in sessions:
            print(f"ID {s.id}: {s.companion_name} turn {s.turn_count}")

asyncio.run(debug())
```

## Best Practices

### 1. Async/Await
- **SEMPRE** usa `async` per I/O
- **MAI** bloccare il main thread
- Usa `asyncio.create_task()` per operazioni in background

### 2. Database
- Usa sempre `async with db_manager.get_session()`
- Non fare commit manuali (gestito dal context manager)
- Gestisci rollback implicito tramite exception

### 3. Error Handling
```python
try:
    result = await risky_operation()
except SpecificException as e:
    # Handle specific
    print(f"[!] Specific error: {e}")
except Exception as e:
    # Catch all
    print(f"[ERR] Unexpected: {e}")
    import traceback
    traceback.print_exc()
```

### 4. Type Hints
- Usa type hints ovunque
- Usa `Optional[X]` per valori nullable
- Usa `Dict[str, Any]` per JSON/dati flessibili

### 5. Testing
```python
# tests/test_feature.py
def test_new_feature():
    from core.module import NewFeature
    
    feature = NewFeature()
    result = feature.do_something()
    
    assert result is True
    print("[OK] Test passed")
```

## Troubleshooting

### Problema: ImportError
```bash
# Verifica installazione
pip list | grep luna-rpg

# Reinstalla
pip install -e . --force-reinstall
```

### Problema: Database locked
```bash
# Elimina database (perde i dati!)
rm storage/saves/luna_v3.db

# O riavvia l'app
```

### Problema: ComfyUI non risponde
```bash
# Verifica URL
python -c "from config.settings import get_settings; print(get_settings().comfy_url)"

# Test connessione
curl http://localhost:8188/system_stats
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-03
