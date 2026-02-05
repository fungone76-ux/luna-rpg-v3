"""Async ComfyUI client for images (replaces SD WebUI)."""
import asyncio
import base64
import gc
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import aiofiles

from core.prompt_builders.base import PromptResult
from config.settings import Settings


class ComfyImageClient:
    """Client async per immagini usando ComfyUI (invece di SD WebUI)."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.timeout = aiohttp.ClientTimeout(total=300)
        self.client_id = str(uuid.uuid4())
        self.workflow_path = Path("workflow_image.json")
        self._is_loaded = True
    
    async def generate(
        self, 
        prompt_result: PromptResult,
        character_name: str = "Luna",
        save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Genera immagine usando ComfyUI workflow."""
        
        comfy_url = self.settings.comfy_url
        print(f"[ComfyImage] URL: {comfy_url}")
        if not comfy_url:
            print("[ComfyImage] URL non disponibile")
            return None
        
        try:
            # 1. Carica e patch workflow
            async with aiofiles.open(self.workflow_path, "r") as f:
                workflow = json.loads(await f.read())
            
            # Rimuovi _meta da tutti i nodi (causa errori 400)
            for node_id in list(workflow.keys()):
                if "_meta" in workflow[node_id]:
                    del workflow[node_id]["_meta"]
            
            # 2. Patch parametri
            # Node 2 = positive prompt
            workflow["2"]["inputs"]["text"] = prompt_result.positive
            # Node 3 = negative prompt  
            workflow["3"]["inputs"]["text"] = prompt_result.negative
            # Node 7 = size
            workflow["7"]["inputs"]["width"] = prompt_result.width
            workflow["7"]["inputs"]["height"] = prompt_result.height
            # Node 4 = seed
            workflow["4"]["inputs"]["noise_seed"] = int(time.time()) % 1000000000
            # Node 9 = filename prefix
            workflow["9"]["inputs"]["filename_prefix"] = f"{character_name}_ComfyUI"
            
            # 3. Seleziona LoRA corretto (nomi esatti dal server) + pesi originali
            lora_config = {
                "Luna": ("stsDebbie-10e.safetensors", 0.7),
                "Stella": ("stsDebbie-10e.safetensors", 0.7),
                "Maria": ("stsSmith-10e.safetensors", 0.65)
            }
            lora_name, lora_strength = lora_config.get(character_name, ("stsDebbie-10e.safetensors", 0.7))
            workflow["20"]["inputs"]["lora_name"] = lora_name
            workflow["20"]["inputs"]["strength_model"] = lora_strength
            
            # Aggiungi nodi 23 e 24 per Expressive_H e FantasyWorldPonyV2
            # Nodo 23: Expressive_H (peso originale: 0.2)
            workflow["23"] = {
                "inputs": {
                    "lora_name": "Expressive_H-000001.safetensors",
                    "strength_model": 0.2,
                    "strength_clip": 1.0,
                    "model": ["20", 0],
                    "clip": ["20", 1]
                },
                "class_type": "LoraLoader"
            }
            # Nodo 24: FantasyWorldPonyV2 (peso originale: 0.4)
            workflow["24"] = {
                "inputs": {
                    "lora_name": "FantasyWorldPonyV2.safetensors",
                    "strength_model": 0.4,
                    "strength_clip": 1.0,
                    "model": ["23", 0],
                    "clip": ["23", 1]
                },
                "class_type": "LoraLoader"
            }
            
            # Cambia scheduler a karras
            workflow["6"]["inputs"]["scheduler"] = "karras"
            
            # Riconnetti tutto al nodo 24 (ultimo LoRA)
            workflow["4"]["inputs"]["model"] = ["24", 0]
            workflow["6"]["inputs"]["model"] = ["24", 0]
            workflow["2"]["inputs"]["clip"] = ["24", 1]
            workflow["3"]["inputs"]["clip"] = ["24", 1]
            
            # 4. Invia a ComfyUI
            print(f"[ComfyImage] Generating {character_name}...")
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{comfy_url}/prompt",
                    json={"prompt": workflow, "client_id": self.client_id}
                ) as resp:
                    if resp.status != 200:
                        error_body = await resp.text()
                        print(f"[ComfyImage] Queue failed: {resp.status}")
                        print(f"[ComfyImage] Error body: {error_body[:500]}")
                        return None
                    data = await resp.json()
                    prompt_id = data.get("prompt_id")
                    if not prompt_id:
                        print("[ComfyImage] No prompt_id")
                        return None
                    print(f"[ComfyImage] Queue ID: {prompt_id}")
            
            # 5. Attendi completamento con polling (più veloce)
            print("[ComfyImage] Waiting for generation...")
            img_path = await self._wait_and_download(comfy_url, prompt_id, character_name, save_dir)
            return img_path

        except Exception as e:
            print(f"[ComfyImage] Error: {e}")
            return None
    
    async def _wait_and_download(self, comfy_url: str, prompt_id: str, character: str, save_dir: Optional[Path]) -> Optional[Path]:
        """Attende il completamento con polling e scarica subito."""
        max_wait = 120  # 2 minuti max
        poll_interval = 2  # check ogni 2 secondi
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for attempt in range(0, max_wait, poll_interval):
                await asyncio.sleep(poll_interval)
                
                # Controlla se completato
                try:
                    async with session.get(f"{comfy_url}/history/{prompt_id}") as r:
                        if r.status == 200:
                            data = await r.json()
                            outputs = data.get(prompt_id, {}).get("outputs", {})
                            
                            if outputs:  # Completato!
                                print(f"[ComfyImage] Done in {attempt + poll_interval}s, downloading...")
                                # Scarica immediatamente
                                for nid, node in outputs.items():
                                    images = node.get("images", [])
                                    for img in images:
                                        fname = img.get("filename", "")
                                        if fname.endswith('.png'):
                                            async with session.get(f"{comfy_url}/view?filename={fname}") as ir:
                                                if ir.status == 200:
                                                    img_data = await ir.read()
                                                    if save_dir is None:
                                                        save_dir = Path("storage/images")
                                                    save_dir.mkdir(parents=True, exist_ok=True)
                                                    path = save_dir / f"{character}_{int(time.time())}.png"
                                                    async with aiofiles.open(path, "wb") as f:
                                                        await f.write(img_data)
                                                    print(f"[ComfyImage] Saved: {path}")
                                                    return path
                                return None
                except Exception as e:
                    print(f"[!] Poll error: {e}")
                    continue
            
            print("[ComfyImage] Timeout waiting for generation")
            return None
    
    async def _download_image(self, comfy_url: str, prompt_id: str, character: str, save_dir: Optional[Path]) -> Optional[Path]:
        """Scarica immagine da history."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{comfy_url}/history/{prompt_id}") as r:
                    if r.status != 200:
                        return None
                    data = await r.json()
                    outputs = data.get(prompt_id, {}).get("outputs", {})
                    
                    for nid, node in outputs.items():
                        images = node.get("images", [])
                        for img in images:
                            fname = img.get("filename", "")
                            if fname.endswith('.png'):
                                # Download
                                async with session.get(f"{comfy_url}/view?filename={fname}") as ir:
                                    if ir.status == 200:
                                        img_data = await ir.read()
                                        if save_dir is None:
                                            save_dir = Path("storage/images")
                                        save_dir.mkdir(parents=True, exist_ok=True)
                                        path = save_dir / f"{character}_{int(time.time())}.png"
                                        async with aiofiles.open(path, "wb") as f:
                                            await f.write(img_data)
                                        print(f"[ComfyImage] Saved: {path}")
                                        return path
            return None
        except Exception as e:
            print(f"[ComfyImage] Download error: {e}")
            return None
    
    async def unload_model(self) -> bool:
        """Scarica modelli da VRAM."""
        try:
            comfy_url = self.settings.comfy_url
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{comfy_url}/free",
                    json={"unload_models": True, "free_memory": True}
                )
            gc.collect()
            return True
        except:
            return False
    
    async def reload_model(self) -> bool:
        """ComfyUI non ha reload esplicito come SD."""
        # ComfyUI carica automaticamente quando serve
        return True
