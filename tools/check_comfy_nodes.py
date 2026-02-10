"""Verifica quali nodi sono disponibili su ComfyUI RunPod."""
import asyncio
import aiohttp
from config.settings import Settings

async def check_nodes():
    settings = Settings()
    
    if not settings.comfy_url:
        print("[ERR] ComfyUI non configurato. Imposta RUNPOD_ID nell'env.")
        return
    
    comfy_url = settings.comfy_url
    print(f"Checking ComfyUI nodes at: {comfy_url}")
    print("="*60)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Ottieni lista nodi disponibili
            async with session.get(
                f"{comfy_url}/object_info",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    print(f"[ERR] Errore: HTTP {resp.status}")
                    return
                
                data = await resp.json()
                
                # Cerca nodi specifici
                nodes_to_check = [
                    "SaveLatent",
                    "LoadLatent", 
                    "CheckpointLoaderSimple",
                    "KSampler",
                    "KSamplerAdvanced",
                    "VAEDecode",
                    "VHS_VideoCombine",
                    "SaveAnimatedWEBP",
                    "UnloadModel",
                    "FreeMemory"
                ]
                
                print("\n[LIST] NODI NECESSARI PER SPLIT WORKFLOW:")
                print("-"*60)
                
                found_split = True
                for node in ["SaveLatent", "LoadLatent"]:
                    if node in data:
                        print(f"[OK] {node}: DISPONIBILE")
                    else:
                        print(f"[ERR] {node}: MANCANTE")
                        found_split = False
                
                print("\n[LIST] ALTRI NODI UTILI:")
                print("-"*60)
                for node in ["UnloadModel", "FreeMemory"]:
                    if node in data:
                        print(f"[OK] {node}: DISPONIBILE (ottimo per VRAM)")
                    else:
                        print(f"[!]  {node}: non disponibile")
                
                print("\n[LIST] NODI STANDARD:")
                print("-"*60)
                for node in ["KSamplerAdvanced", "VAEDecode", "VHS_VideoCombine"]:
                    if node in data:
                        print(f"[OK] {node}: OK")
                    else:
                        print(f"[ERR] {node}: MANCANTE")
                
                print("\n" + "="*60)
                if found_split:
                    print("🎉 PERFETTO! Puoi usare il WORKFLOW SPLIT!")
                    print("   I nodi SaveLatent e LoadLatent sono disponibili.")
                else:
                    print("[!]  ATTENZIONE: Nodi mancanti per split workflow.")
                    print("   Devi usare il metodo 'Do Not Disturb' (8 min attesa).")
                    print("\n[I] Per installare i nodi mancanti:")
                    print("   1. Vai su ComfyUI Manager → Install Missing Custom Nodes")
                    print("   2. Cerca: 'SaveLatent' o 'latent' nodes")
                    print("   3. Oppure installa: ComfyUI-Manager e aggiorna tutto")
                
                print("\n" + "="*60)
                print(f"\nTotale nodi disponibili: {len(data)}")
                
    except Exception as e:
        print(f"[ERR] Errore connessione: {e}")
        print("\nVerifica che:")
        print("1. RunPod sia acceso e ComfyUI in esecuzione")
        print("2. RUNPOD_ID sia corretto nel file .env")
        print("3. La porta 8188 sia accessibile")

if __name__ == "__main__":
    asyncio.run(check_nodes())
