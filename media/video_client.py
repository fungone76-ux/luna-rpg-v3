"""Async ComfyUI client - DO NOT DISTURB mode (safe & reliable).

Versione semplificata:
- Risoluzione 512x768 (meno VRAM)
- Do Not Disturb: 7 minuti attesa fissa
- Niente split workflow
"""
import json
import os
import platform
import subprocess
import time
import uuid
import asyncio
import gc
from pathlib import Path
from typing import Optional, Dict
import random
seed_casuale = random.randint(1, 999999999999999)
print(f"  [Patch] Seed applicato: {seed_casuale}")
import aiohttp
import aiofiles

from config.settings import Settings


class VideoClient:
    """Async client per video generation - modalita DND semplice."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.client_id = str(uuid.uuid4())
        self.workflow_path = Path("api.json")
        if not self.workflow_path.exists():
            self.workflow_path = Path(__file__).parent.parent / "api.json"
        self._progress_callback = None
    
    def set_progress_callback(self, callback):
        self._progress_callback = callback
    
    def _update_progress(self, msg: str):
        print(f"  [Video] {msg}")
        if self._progress_callback:
            self._progress_callback(msg)
    
    # ========================================================================
    # VRAM MANAGEMENT
    # ========================================================================
    
    def _manage_vram(self, action="unload"):
        """Scarica/carica modelli - usa ComfyUI (non SD WebUI)."""
        import requests
        comfy_url = self.settings.comfy_url  # Usa ComfyUI, non SD!
        
        if not comfy_url:
            print("  [!] ComfyURL non disponibile, skip VRAM management")
            return True
        
        if action == "unload":
            print("  [Comfy] Unload models...")
            try:
                # ComfyUI /free scarica tutto
                resp = requests.post(
                    f"{comfy_url}/free", 
                    json={"unload_models": True, "free_memory": True},
                    timeout=15
                )
                resp.close()
                time.sleep(3)
                print("  [VRAM] ComfyUI models unloaded")
            except Exception as e:
                print(f"  [!] Comfy unload error: {e}")
            
            gc.collect()
            return True
                
        else:
            print("  [Comfy] Reload non necessario (ComfyUI carica auto)")
            # ComfyUI carica automaticamente i modelli quando serve
            # Non c'è bisogno di reload esplicito
            return True
    
    async def _cleanup_comfy_vram(self, comfy_url: str):
        """Pulizia VRAM su ComfyUI dopo video - VERSIONE VELOCE."""
        print("  [Cleanup] Scarico modelli ComfyUI...")
        session = None
        try:
            session = aiohttp.ClientSession()
            
            # 1. Interrompi esecuzione
            try:
                await session.post(f"{comfy_url}/interrupt", timeout=5)
            except:
                pass
            await asyncio.sleep(1)  # Ridotto da 2s a 1s
            
            # 2. PULIZIA: 5 chiamate /free con attese brevi
            for attempt in range(5):
                try:
                    resp = await session.post(
                        f"{comfy_url}/free", 
                        json={"unload_models": True, "free_memory": True},
                        timeout=30
                    )
                    if resp.status == 200:
                        print(f"  [Cleanup] /free OK ({attempt+1}/5)")
                    await resp.release()
                except Exception as e:
                    print(f"  [Cleanup] /free error: {e}")
                
                # Attese brevi tra le chiamate: 1s, 2s, 2s, 3s, 3s
                wait_times = [1, 2, 2, 3, 3]
                await asyncio.sleep(wait_times[attempt])
            
            # 3. Attesa finale per scarico VRAM
            print("  [Cleanup] Attesa finale scarico VRAM...")
            await asyncio.sleep(5)  # Ridotto da 20s a 5s
                
        except Exception as e:
            print(f"  [Cleanup] Error: {e}")
        finally:
            if session:
                await session.close()
        
        print("  [Cleanup] VRAM liberata")
    
    # ========================================================================
    # TEMPORAL PROMPT
    # ========================================================================
    
    async def _build_temporal_prompt(self, llm_client, context, character, location, action, user_action=None):
        """Genera prompt temporale cinematografico con LLM.
        
        Args:
            user_action: Optional custom action description in Italian from user
        """
        
        if user_action:
            # User provided custom action - translate to simple flowing description
            system = """You are an expert video prompt engineer. 

Take the user's Italian description and rewrite it as a professional English video prompt for Wan2.1 I2V. 

Focus on:
- Camera angle and shot type (close-up, medium shot, from below, etc.)
- Physical motion description
- Lighting and environment details
- NO emotions, NO facial expressions

Keep it as one flowing sentence or paragraph.

Example:
Italian: "Si sistema i capelli e mi guarda"
English: "Medium shot from eye level, woman's hand slowly tucking hair behind ear, looking toward camera, soft classroom lighting, gentle fluid motion, realistic skin texture"

Write like a pro video prompt engineer would."""

            user = f"""Translate this Italian action into a simple video description:

Italian: {user_action}
Character: {character}
Location: {location}

Write in English as one flowing description (no timestamps):"""
        else:
            # Default action-based generation
            system = """You are an expert Wan2.1 I2V Video Prompt Engineer.

Create a RICH, CINEMATIC 5-second video description with EXACT temporal markers.
Each timestamp must describe:
- SHOT TYPE (wide shot, medium shot, close-up, extreme close-up)
- CAMERA ANGLE (eye level, low angle, high angle, dutch angle)
- CAMERA MOVEMENT (static, pan, tilt, dolly in/out, tracking)
- CHARACTER ACTION (specific motion, not just "posing")
- ENVIRONMENT REACTION (dust, light, particles, physics)

STRICT RULES:
1. NO facial expressions (smiling, angry, etc.)
2. NO emotional states (nervous, excited, etc.)
3. Describe PHYSICAL MOTION and CAMERA WORK only
4. Each timestamp should be 1-2 detailed sentences
5. Include environmental details (lighting, atmosphere)

FORMAT EXACTLY:
(At 0 seconds: [shot type], [character] in [location], [initial pose/action], [camera angle], [lighting/atmosphere])
(At 1 second: [camera movement begins], [action starts], [environment reaction])
(At 2 seconds: [peak motion/action], [dynamic element], [physics/feedback])
(At 3 seconds: [continuation], [secondary motion], [spatial change])
(At 4 seconds: [stabilization], [ending pose], [final camera position])"""

            user = f"""Create a cinematic 5-second video prompt based on:

CHARACTER: {character}
LOCATION: {location}
ACTION: {action}
CONTEXT: {context}

Generate detailed temporal descriptions focusing on motion, camera work, and physics."""

        try:
            print(f"  [LLM] Building temporal prompt...")
            if user_action:
                print(f"    User action: {user_action[:60]}...")
            
            response = await llm_client.generate_response(
                user_input=user, system_instruction=system, history=[],
                companion_name=character
            )
            text = response.text.strip().replace("```", "")
            
            # Simple validation: must be non-empty and reasonable length
            if not text or len(text) < 10:
                print(f"  [!] Empty response, using fallback")
                return self._fallback_temporal(character, location, action)
            
            print(f"  [OK] Prompt generated: {text[:80]}...")
            return text
            
        except Exception as e:
            print(f"  [LLM] Error: {e}")
            return self._fallback_temporal(character, location, action)

    def _fallback_temporal(self, character, location, action):
        """Fallback temporale cinematico quando LLM fallisce."""
        return (f"(At 0 seconds: Wide establishing shot, {character} in {location}, standing still, eye level camera, soft natural lighting) "
                f"(At 1 second: Camera slowly dollies forward, {character} begins {action}, subtle movement starting) "
                f"(At 2 seconds: Medium shot, {character} in full {action}, dynamic motion, fabric and hair reacting to movement) "
                f"(At 3 seconds: Camera follows the motion, {character} continues movement, spatial depth changing) "
                f"(At 4 seconds: Shot stabilizes, {character} returning to static pose, camera settles, motion fading)")

    def _add_boosters(self, prompt, intensity=6):
        return prompt.strip() + f", masterpiece, best quality, motion speed {intensity}"
    
    # ========================================================================
    # MAIN GENERATION - DO NOT DISTURB
    # ========================================================================
    
    async def generate(
        self, llm_client, image_path: Path, context: str,
        character: str, location: str, action: str = "posing",
        save_dir: Optional[Path] = None, motion_speed: int = 6,
        user_action: Optional[str] = None,
        dialog_logger = None
    ) -> Optional[Path]:
        """Genera video con Do Not Disturb mode.
        
        Args:
            user_action: Optional custom action description in Italian from user
            dialog_logger: Optional logger per dialogo e prompt
        """
        
        if not self.settings.video_available:
            print("[Video] Video generation disabilitata in modalità LOCAL")
            print("[Video] Richiede RunPod con ComfyUI configurato")
            return None
        
        comfy_url = self.settings.comfy_url
        if not comfy_url:
            print("[Video] ComfyUI URL non disponibile")
            return None
        
        if not image_path.exists():
            print(f"[Video] Immagine non trovata: {image_path}")
            return None
        
        # VRAM unload
        self._manage_vram("unload")
        
        video_path = None
        try:
            # 1. Genera prompt
            print(f"[Video] Generating prompt per {character}...")
            if user_action:
                print(f"  [Input] User action: {user_action}")
            temporal = await self._build_temporal_prompt(
                llm_client, context, character, location, action, user_action
            )
            final_prompt = self._add_boosters(temporal, motion_speed)
            print(f"[Video] Prompt: {final_prompt[:100]}...")
            
            # Log prompt video nel dialog_logger
            if dialog_logger:
                dialog_logger.log_video_prompt(character, final_prompt)
            
            # 2. Carica e patch workflow
            print("[Video] Loading workflow...")
            async with aiofiles.open(self.workflow_path, "r", encoding="utf-8") as f:
                workflow = json.loads(await f.read())
            
            # Trova e patch positive prompt (nodo 5) PRIMA di rimuovere _meta
            for nid, node in workflow.items():
                if node.get("class_type") == "CLIPTextEncode":
                    title = node.get("_meta", {}).get("title", "")
                    if "POSITIVO" in title.upper() or nid == "5":
                        node["inputs"]["text"] = final_prompt
                        print(f"  [Patch] Prompt positivo ({nid}): {final_prompt[:80]}...")
                        break
            
            # Rimuovi _meta da tutti i nodi (causa errori 400)
            for node_id in list(workflow.keys()):
                if "_meta" in workflow[node_id]:
                    del workflow[node_id]["_meta"]
            
            # Patch workflow - Nodo 6 è LoadImage per Wan2.1
            if "6" in workflow:
                workflow["6"]["inputs"]["image"] = image_path.name
                print(f"  [Patch] Immagine input: {image_path.name}")
            
            # Patch risoluzione e batch (nodo 7 = WanImageToVideo)
            if "7" in workflow:
                workflow["7"]["inputs"]["width"] = 512
                workflow["7"]["inputs"]["height"] = 768
                workflow["7"]["inputs"]["length"] = 81
                workflow["7"]["inputs"]["batch_size"] = 1
                print("  [Patch] Risoluzione video: 512x768x81frames")

            # Patch seed per KSampler (nodo 8)
            if "8" in workflow:
                workflow["8"]["inputs"]["seed"] = seed_casuale
                print(f"  [Patch] Seed: {seed_casuale}")
            
            # Patch filename_prefix per tracciamento su RunPod (nodo 10 = VHS_VideoCombine)
            if "10" in workflow:
                workflow["10"]["inputs"]["filename_prefix"] = f"{character}_Video"
                print(f"  [Patch] Filename prefix: {character}_Video")
            
            # NOTA: FreeMemory node non e' standard, lo gestiamo via API dopo
            
            # 3. Upload immagine
            print("[Video] Uploading image...")
            try:
                async with aiohttp.ClientSession() as s:
                    data = aiohttp.FormData()
                    async with aiofiles.open(image_path, "rb") as f:
                        data.add_field("image", await f.read(), filename=image_path.name)
                    async with s.post(f"{comfy_url}/upload/image", data=data, timeout=30) as r:
                        if r.status == 200:
                            result = await r.json()
                            uploaded_name = result.get("name", image_path.name)
                            if "6" in workflow:
                                workflow["6"]["inputs"]["image"] = uploaded_name
                            print(f"  [Upload] OK: {uploaded_name}")
            except Exception as e:
                print(f"  [Upload] Warning: {e}")
            
            # 4. Invia a ComfyUI
            print("[Video] Queueing to ComfyUI...")
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{comfy_url}/prompt",
                    json={"prompt": workflow, "client_id": self.client_id},
                    timeout=30
                ) as r:
                    if r.status != 200:
                        error_text = await r.text()
                        print(f"[Video] Queue failed: {r.status}")
                        print(f"[Video] Error: {error_text[:500]}")
                        return None
                    data = await r.json()
                    prompt_id = data.get("prompt_id")
                    if not prompt_id:
                        print("[Video] No prompt_id")
                        return None
                    print(f"  [Queue] ID: {prompt_id}")
            
            # 5. DO NOT DISTURB - ~2m 45s (basato su test: video pronto in ~155s)
            print("[Video] Generating... (~2m 45s)")
            total_seconds = 165  # 2 minuti 45 secondi (margine sui 155s reali)
            update_interval = 7  # ~165s / 24 updates
            for i in range(24):
                await asyncio.sleep(update_interval)
                elapsed = int((i + 1) * update_interval)
                mins = elapsed // 60
                secs = elapsed % 60
                self._update_progress(f"Generazione... {mins}m {secs}s / 2m 45s")
            
            print("[Video] Checking result...")
            
            # 6. Download
            video_path = await self._download(comfy_url, prompt_id, character, save_dir)
            
            if video_path:
                print(f"[Video] Salvato: {video_path}")
                self._open_video(video_path)
            
            # PULIZIA MEMORIA (variabili grandi)
            print("[Video] Pulizia memoria temporanea...")
            import gc
            del workflow, final_prompt, temporal
            for _ in range(3):
                gc.collect()
            print("  [RAM] Buffer temporanei liberati")
            
            # PULIZIA VRAM ComfyUI
            print("[Video] Pulizia VRAM ComfyUI...")
            await self._cleanup_comfy_vram(comfy_url)
            
            # Pausa per scarico VRAM + RAM
            print("  [VRAM] Attesa scarico finale (10s)...")
            await asyncio.sleep(10)  # Ridotto da 30s a 10s
            
            # Cleanup aggiuntivo della RAM di sistema
            gc.collect()
            print("  [RAM] Garbage collection eseguito")
            
            await asyncio.sleep(5)  # Altra pausa - ridotta da 15s a 5s
            print("  [VRAM/RAM] Pronto")
            
            return video_path
            
        except Exception as e:
            print(f"[Video] Errore: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Cleanup finale VRAM
            print("  [VRAM] Cleanup finale...")
            await asyncio.sleep(5)
            
            # ComfyUI non ha bisogno di reload (carica auto)
            print("  [Comfy] Ready for next generation")
    
    async def _download(self, comfy_url: str, prompt_id: str, character: str, save_dir: Optional[Path]) -> Optional[Path]:
        """Scarica video da history con polling attivo."""
        session = None
        try:
            session = aiohttp.ClientSession()
            
            # Polling per max 120 secondi (il video potrebbe richiedere tempo)
            max_attempts = 24
            attempt_delay = 5  # 5 secondi tra tentativi
            
            for attempt in range(max_attempts):
                print(f"  [Download] Check {attempt + 1}/{max_attempts}...")
                
                async with session.get(f"{comfy_url}/history/{prompt_id}", timeout=30) as r:
                    if r.status == 200:
                        data = await r.json()
                        outputs = data.get(prompt_id, {}).get("outputs", {})
                        
                        if not outputs:
                            print(f"    No outputs yet, retrying...")
                        else:
                            print(f"    Found {len(outputs)} output nodes")
                            
                            for nid, node in outputs.items():
                                print(f"    Checking node {nid}: {list(node.keys())}")
                                files = node.get("gifs", []) or node.get("videos", [])
                                
                                if not files:
                                    # Cerca anche in 'images' (alcuni formati video sono lì)
                                    files = node.get("images", [])
                                
                                for f in files:
                                    fname = f.get("filename", "")
                                    print(f"    File found: {fname}")
                                    
                                    if fname.endswith(('.mp4', '.mov', '.webm', '.gif')):
                                        print(f"    [OK] Downloading {fname}...")
                                        async with session.get(f"{comfy_url}/view?filename={fname}", timeout=120) as vr:
                                            if vr.status == 200:
                                                vdata = await vr.read()
                                                if save_dir is None:
                                                    save_dir = Path("storage/videos")
                                                save_dir.mkdir(parents=True, exist_ok=True)
                                                
                                                # Determina estensione corretta
                                                ext = Path(fname).suffix
                                                if ext == '.gif':
                                                    ext = '.mp4'  # Converti nome
                                                
                                                path = save_dir / f"{character}_Video_{int(time.time())}{ext}"
                                                async with aiofiles.open(path, "wb") as f:
                                                    await f.write(vdata)
                                                
                                                print(f"    [OK] Saved: {path} ({len(vdata)} bytes)")
                                                del vdata
                                                gc.collect()
                                                await session.close()
                                                return path
                                            else:
                                                print(f"    [!] Download failed: {vr.status}")
                    else:
                        print(f"    [!] History check failed: {r.status}")
                
                # Attesa prima del prossimo tentativo
                if attempt < max_attempts - 1:
                    await asyncio.sleep(attempt_delay)
            
            await session.close()
            print("[Video] Video non trovato dopo tutti i tentativi")
            return None
                
        except Exception as e:
            if session:
                await session.close()
            print(f"[Video] Download error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _open_video(self, filepath: Path):
        """Apri video."""
        try:
            if platform.system() == "Windows":
                os.startfile(str(filepath))
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(filepath)])
            else:
                subprocess.Popen(["xdg-open", str(filepath)])
            print("[Video] Apertura player...")
        except:
            pass
