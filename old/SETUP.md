# Setup Luna RPG v3

## Prerequisiti
- Python 3.11+
- Windows (per PySide6)

## Installazione

```powershell
# 1. Entra nella cartella
cd D:\luna-rpg-v3

# 2. Crea virtual environment
python -m venv .venv

# 3. Attiva
.venv\Scripts\activate

# 4. Installa dipendenze
pip install -e .
```

## Configurazione

Il progetto usa **il tuo file `.env` esistente** dalla v2. Copialo:

```powershell
copy D:\luna-rpg-v2\.env D:\luna-rpg-v3\.env
```

Oppure crea uno nuovo:

```env
# --- MODALITÀ ---
EXECUTION_MODE=LOCAL

# --- API KEYS ---
GEMINI_API_KEY=la_tua_chiave_qui

# --- RUNPOD (opzionale) ---
RUNPOD_ID=
RUNPOD_API_KEY=
```

## Test

### Test automatici (senza UI)
```powershell
# Dalla cartella luna-rpg-v3
python tests\test_basic.py
```

Questo verifica:
- ✅ Tutti i moduli si importano
- ✅ Database funziona
- ✅ Settings caricati
- ✅ Mondi caricabili
- ✅ Prompt builders funzionanti

### Avvio applicazione
```powershell
python main.py
```

## Troubleshooting

### Errore: "No module named 'qasync'"
```powershell
pip install qasync>=0.27
```

### Errore: "No module named 'google'"
```powershell
pip install google-genai google-cloud-texttospeech
```

### Errore: "DLL load failed" (PySide6)
Aggiorna pip e reinstalla:
```powershell
pip install --upgrade pip
pip install --force-reinstall pyside6
```

## Struttura Database

La v3 usa SQLite invece di JSON. Il file è:
```
storage/saves/luna_v3.db
```

I vecchi save JSON non sono compatibili (nuova struttura).

## Differenze dalla v2

| Feature | v2 | v3 |
|---------|----|----|
| Persistenza | JSON files | SQLite database |
| UI | Sincrona (bloccante) | Asincrona (reattiva) |
| Scene Multi | Regex su nomi | LLM semantico |
| Type Safety | No | Pydantic models |
| Memory | Buffer fisso | Compressione automatica |
