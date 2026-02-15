"""Controlla quota e stato API key Moonshot."""
import os
import httpx
from config.settings import get_settings

def check_moonshot_quota():
    settings = get_settings()
    api_key = settings.moonshot_api_key
    
    if not api_key:
        print("[!] MOONSHOT_API_KEY non trovata nel .env")
        return
    
    print(f"[INFO] API Key: {api_key[:15]}... (lunghezza: {len(api_key)})")
    print()
    
    # Prova a fare una semplice chiamata per vedere gli header
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Endpoint user/billing di Moonshot (OpenAI-compatibile)
    # Prova a chiamare /models per vedere se la key è valida
    try:
        print("[1] Verifica validità API key...")
        response = httpx.get(
            "https://api.moonshot.cn/v1/models",
            headers=headers,
            timeout=30
        )
        
        print(f"    Status: {response.status_code}")
        
        if response.status_code == 200:
            print("    [OK] API Key VALIDA!")
            data = response.json()
            models = [m.get('id', 'unknown') for m in data.get('data', [])]
            print(f"    Modelli disponibili: {len(models)}")
            for m in models[:5]:
                print(f"      - {m}")
        elif response.status_code == 401:
            print("    [ERR] API Key INVALIDA o SCADUTA!")
        elif response.status_code == 429:
            print("    [ERR] Rate limit già attivo!")
        else:
            print(f"    [WARN] Risposta: {response.text[:200]}")
        
        # Header utili
        print()
        print("[2] Header di risposta:")
        important_headers = ['x-ratelimit-limit', 'x-ratelimit-remaining', 
                            'x-ratelimit-reset', 'x-request-id']
        for h in important_headers:
            if h in response.headers:
                print(f"    {h}: {response.headers[h]}")
        
        # Prova una chiamata di test per vedere i limiti
        print()
        print("[3] Test chiamata completion (budget basso)...")
        test_payload = {
            "model": "moonshot-v1-8k",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
        
        test_resp = httpx.post(
            "https://api.moonshot.cn/v1/chat/completions",
            headers=headers,
            json=test_payload,
            timeout=30
        )
        
        print(f"    Status: {test_resp.status_code}")
        
        if test_resp.status_code == 200:
            result = test_resp.json()
            usage = result.get('usage', {})
            print(f"    [OK] Chiamata riuscita!")
            print(f"    Tokens usati: {usage.get('total_tokens', 'N/A')}")
        elif test_resp.status_code == 429:
            print("    [ERR] Rate limit attivo!")
            print("    Aspetta qualche minuto prima di riprovare...")
        
        # Mostra header rate limit se presenti
        print()
        print("[4] Header Rate Limit:")
        for h in important_headers:
            if h in test_resp.headers:
                print(f"    {h}: {test_resp.headers[h]}")
                
    except Exception as e:
        print(f"[ERR] Errore: {e}")
    
    print()
    print("="*60)
    print("Per controllare la quota dettagliata:")
    print("1. Vai su https://platform.moonshot.cn/")
    print("2. Login con il tuo account")
    print("3. Vai su 'Billing' o 'Usage'")
    print("="*60)

if __name__ == "__main__":
    check_moonshot_quota()
