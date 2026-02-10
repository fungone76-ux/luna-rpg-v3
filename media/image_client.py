"""Async Stable Diffusion client (local or RunPod)."""
import asyncio
import base64
import gc
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp

from core.prompt_builders.base import PromptResult
from config.settings import Settings


class ImageClient:
    """Client async per Stable Diffusion."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 min per generazione
        self._last_checkpoint: Optional[str] = None
        self._is_loaded = True
    
    async def generate(
        self, 
        prompt_result: PromptResult,
        character_name: str = "Luna",
        save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Genera immagine e restituisce il path salvato.
        
        Args:
            prompt_result: Risultato dal prompt builder
            character_name: Nome del personaggio per il filename
            save_dir: Directory dove salvare (default: storage/images)
        
        Returns:
            Path dell'immagine generata o None se errore
        """
        base_url = self.settings.sd_url
        api_url = f"{base_url}/sdapi/v1/txt2img"
        
        payload = {
            "prompt": prompt_result.positive,
            "negative_prompt": prompt_result.negative,
            "steps": self.settings.image_steps,
            "width": prompt_result.width,
            "height": prompt_result.height,
            "sampler_name": self.settings.image_sampler,
            "cfg_scale": 7.0,
            "enable_hr": False,
        }
        
        print(f"[IMG] Generating image via {base_url}...")
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(api_url, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"[ERR] SD Error {resp.status}: {error_text[:200]}")
                        return None
                    
                    data = await resp.json()
                    img_data = base64.b64decode(data["images"][0])
                    
                    # Salva
                    if save_dir is None:
                        save_dir = Path("storage/images")
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{character_name}_{timestamp}.png"
                    filepath = save_dir / filename
                    
                    with open(filepath, "wb") as f:
                        f.write(img_data)
                    
                    print(f"[OK] Image saved: {filepath}")
                    return filepath
                    
        except aiohttp.ClientError as e:
            print(f"[ERR] Connection error: {e}")
            return None
        except Exception as e:
            print(f"[ERR] Image generation error: {e}")
            return None
    
    async def check_connection(self) -> bool:
        """Verifica connessione a SD."""
        try:
            base_url = self.settings.sd_url
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{base_url}/sdapi/v1/samplers") as resp:
                    return resp.status == 200
        except:
            return False
    
    async def unload_model(self) -> bool:
        """Scarica il modello SD per liberare VRAM (staffetta per ComfyUI).
        
        Returns:
            True se l'unload è riuscito
        """
        if not self._is_loaded:
            return True
        
        try:
            base_url = self.settings.sd_url
            print("[->] SD: Unloading checkpoint to free VRAM...")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                # 1. Unload checkpoint
                try:
                    async with session.post(f"{base_url}/sdapi/v1/unload-checkpoint") as resp:
                        if resp.status == 200:
                            print("  [OK] SD checkpoint unloaded")
                except Exception as e:
                    print(f"  [!] Unload failed: {e}")
                
                # 2. Free memory (come in v2)
                try:
                    async with session.post(f"{base_url}/sdapi/v1/free-memory") as resp:
                        if resp.status == 200:
                            print("  [OK] SD memory freed")
                except Exception as e:
                    print(f"  [!] Free memory failed: {e}")
                
                # 3. Garbage collection Python (come in v2)
                gc.collect()
                
                # 4. Attesa per liberare memoria (aumentata per CUDA)
                print("  [WAIT] Waiting for VRAM cleanup...")
                await asyncio.sleep(5)  # Aumentato da 2 a 5 secondi
                
            self._is_loaded = False
            return True
            
        except Exception as e:
            print(f"  [ERR] SD unload error: {e}")
            return False
    
    async def reload_model(self) -> bool:
        """Ricarica il modello SD dopo che ComfyUI ha finito.
        
        Returns:
            True se il reload è riuscito
        """
        if self._is_loaded:
            return True
        
        try:
            base_url = self.settings.sd_url
            print("[->] SD: Reloading checkpoint...")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                # Usa reload-checkpoint come in v2
                try:
                    async with session.post(f"{base_url}/sdapi/v1/reload-checkpoint") as resp:
                        if resp.status == 200:
                            print("  [OK] SD checkpoint reloaded")
                        else:
                            print(f"  [!] Reload returned {resp.status}")
                except Exception as e:
                    print(f"  [!] Reload failed: {e}")
                
                await asyncio.sleep(1)  # Aspetta caricamento
                
            self._is_loaded = True
            return True
            
        except Exception as e:
            print(f"  [ERR] SD reload error: {e}")
            return False
