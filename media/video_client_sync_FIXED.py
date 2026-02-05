# media/video_client.py - VERSIONE SINCRONA FUNZIONANTE
import json
import os
import time
import uuid
import requests
from pathlib import Path
from config.settings import Settings
from media.llm_client import LLMClient
import subprocess
import platform


class VideoClient:
    def __init__(self):
        self.settings = Settings.get_instance()
        self.llm = LLMClient()
        self.client_id = str(uuid.uuid4())
        
        # URLs
        sd_url = self.settings.get_sd_url().rstrip("/")
        self.sd_url = sd_url
        
        if "runpod.net" in sd_url:
            self.comfy_url = sd_url.replace("-7860.proxy.runpod.net", "-8188.proxy.runpod.net")
        else:
            self.comfy_url = "http://127.0.0.1:8188"
        
        self.workflow_path = "wan_gguf_workflow_improved.json"
        if not os.path.exists(self.workflow_path):
            root = Path(__file__).resolve().parent.parent
            self.workflow_path = str(root / "wan_gguf_workflow_improved.json")
        
        print(f"[V] ComfyUI URL: {self.comfy_url}")

    def _unload_sd(self):
        """Libera VRAM da SD"""
        try:
            requests.post(f"{self.sd_url}/sdapi/v1/unload-checkpoint", timeout=10)
            requests.post(f"{self.sd_url}/sdapi/v1/free-memory", timeout=10)
            time.sleep(5)
            print("[OK] SD scaricato dalla VRAM")
        except Exception as e:
            print(f"[!] Errore unload SD: {e}")

    def _reload_sd(self):
        """Ricarica SD"""
        try:
            requests.post(f"{self.sd_url}/sdapi/v1/reload-checkpoint", timeout=30)
            time.sleep(2)
            print("[OK] SD ricaricato")
        except Exception as e:
            print(f"[!] Errore reload SD: {e}")

    def generate_video(self, image_path, context_text, character_name="Luna", 
                      location="room", action="posing", motion_speed=6):
        """
        Genera video con workflow lista nodi (formato wf2.json).
        APPROCCIO: Do Not Disturb - 8 minuti attesa dopo queue.
        """
        if not os.path.exists(image_path):
            print(f"[ERR] Immagine non trovata: {image_path}")
            return ""

        self._unload_sd()
        
        try:
            # 1. Genera prompt temporale
            print(f"[V] Generazione prompt per {character_name}...")
            temporal = self._build_temporal_prompt(context_text, character_name, location, action)
            final_prompt = f"{temporal}, motion speed {motion_speed}, masterpiece, best quality"
            print(f"[W] Prompt: {final_prompt[:150]}...")
            
            # 2. Carica workflow dal file
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                workflow_raw = json.load(f)
            
            # 3. Upload immagine
            print("📤 Upload immagine...")
            with open(image_path, "rb") as f:
                res = requests.post(f"{self.comfy_url}/upload/image", 
                                  files={"image": f}, timeout=30)
            if res.status_code != 200:
                print(f"[ERR] Upload fallito: {res.status_code}")
                return ""
            
            image_name = res.json().get("name", os.path.basename(image_path))
            print(f"[OK] Upload OK: {image_name}")
            
            # 4. PREPARA WORKFLOW (formato lista nodi -> dict API)
            prompt_api = {}
            nodes = workflow_raw.get("nodes", [])
            links = workflow_raw.get("links", [])
            
            # Mappa links: (to_node, to_slot) -> (from_node, from_slot)
            links_map = {}
            for link in links:
                if len(link) >= 5:
                    _, from_node, from_slot, to_node, to_slot = link
                    links_map[(str(to_node), to_slot)] = (str(from_node), from_slot)
            
            # Processa ogni nodo
            for node in nodes:
                node_id = str(node.get("id"))
                node_type = node.get("type", "")
                title = node.get("title", "")
                widgets = node.get("widgets_values", [])
                inputs_list = node.get("inputs", [])
                
                # Costruisci inputs
                inputs = {}
                widget_idx = 0  # Contatore separato per i widget_values
                
                for i, inp in enumerate(inputs_list):
                    name = inp.get("name")
                    has_widget = inp.get("widget") is not None
                    link_key = (node_id, i)
                    
                    if link_key in links_map:
                        # Input collegato da un altro nodo
                        from_n, from_s = links_map[link_key]
                        inputs[name] = [from_n, from_s]
                    elif has_widget and isinstance(widgets, list):
                        # Input con widget - usa widget_idx, non i!
                        if widget_idx < len(widgets):
                            inputs[name] = widgets[widget_idx]
                        widget_idx += 1
                
                # PATCH SPECIFICI
                
                # LoadImage: imposta immagine caricata
                if node_type == "LoadImage":
                    inputs["image"] = image_name
                
                # CLIPTextEncode positivo: imposta prompt
                if node_type == "CLIPTextEncode":
                    is_negative = "NEGATIVO" in title.upper() or "NEGATIVE" in title.upper() or node_id == "7"
                    if not is_negative:
                        inputs["text"] = final_prompt
                
                # WanFirstLastFrameToVideo: batch_size=1 e rimuovi end_image
                if node_type == "WanFirstLastFrameToVideo":
                    inputs["batch_size"] = 1
                    if "end_image" in inputs:
                        del inputs["end_image"]
                
                # KSamplerAdvanced: CORREGGI parametri shiftati (skip index 2 fantasma)
                if node_type == "KSamplerAdvanced":
                    if len(widgets) >= 10:
                        # Salta index 2 ('randomize'/'fixed' è un valore fantasma)
                        inputs["add_noise"] = widgets[0] if isinstance(widgets[0], str) else "enable"
                        inputs["noise_seed"] = widgets[1] if isinstance(widgets[1], int) else 99680016694451
                        inputs["steps"] = widgets[3] if isinstance(widgets[3], int) else 4
                        inputs["cfg"] = widgets[4] if isinstance(widgets[4], (int, float)) else 0.9
                        inputs["sampler_name"] = widgets[5] if isinstance(widgets[5], str) else "euler"
                        inputs["scheduler"] = widgets[6] if isinstance(widgets[6], str) else "beta"
                        inputs["start_at_step"] = widgets[7] if isinstance(widgets[7], int) else 0
                        inputs["end_at_step"] = widgets[8] if isinstance(widgets[8], int) else 1
                        inputs["return_with_leftover_noise"] = widgets[9] if isinstance(widgets[9], str) else "enable"
                        print(f"    [F] KSampler {node_id}: steps={inputs['steps']}, cfg={inputs['cfg']}, range={inputs['start_at_step']}-{inputs['end_at_step']}")
                
                # Video Combine: assicurati salvi MP4
                if node_type in ["VHS_VideoCombine", "SaveAnimatedWEBP", "SaveVideo"]:
                    inputs["format"] = "video/h264-mp4"
                
                # Aggiungi al dict API
                prompt_api[node_id] = {
                    "inputs": inputs,
                    "class_type": node_type,
                    "_meta": {"title": title}
                }
            
            # 5. INVIA A COMFYUI
            print("🚀 Invio a ComfyUI...")
            res = requests.post(f"{self.comfy_url}/prompt", json={
                "prompt": prompt_api,
                "client_id": self.client_id
            }, timeout=30)
            
            if res.status_code != 200:
                print(f"[ERR] Queue fallita: {res.status_code} - {res.text[:200]}")
                return ""
            
            prompt_id = res.json().get("prompt_id")
            if not prompt_id:
                print("[ERR] Queue fallita: nessun prompt_id")
                return ""
            
            print(f"[OK] Queue OK (ID: {prompt_id})")
            
            # 6. DO NOT DISTURB MODE: Attendi 8 minuti
            print("[WAIT] Do Not Disturb: Attendo 8 minuti per la generazione...")
            print("   (2 KSamplerAdvanced + VHS_VideoCombine)")
            time.sleep(480)  # 8 minuti
            
            # 7. Scarica risultato
            print("📥 Controllo risultato...")
            history_res = requests.get(f"{self.comfy_url}/history/{prompt_id}", timeout=30)
            history = history_res.json()
            
            outputs = history.get(prompt_id, {}).get("outputs", {})
            
            # Cerca il video
            video_filename = None
            for nid, data in outputs.items():
                files = data.get("gifs", []) or data.get("videos", [])
                for f in files:
                    fname = f.get("filename", "")
                    if fname.endswith((".mp4", ".mov", ".webm")):
                        video_filename = fname
                        print(f"[OK] Trovato video: {fname}")
                        break
                if video_filename:
                    break
            
            if not video_filename:
                print("[WAIT] Primo check fallito, attendo altri 2 min...")
                time.sleep(120)
                history_res = requests.get(f"{self.comfy_url}/history/{prompt_id}", timeout=30)
                outputs = history_res.json().get(prompt_id, {}).get("outputs", {})
                for nid, data in outputs.items():
                    files = data.get("gifs", []) or data.get("videos", [])
                    for f in files:
                        fname = f.get("filename", "")
                        if fname.endswith((".mp4", ".mov", ".webm")):
                            video_filename = fname
                            break
                    if video_filename:
                        break
            
            if not video_filename:
                print("[ERR] Video non trovato")
                return ""
            
            # Scarica file
            print(f"📥 Download {video_filename}...")
            video_data = requests.get(f"{self.comfy_url}/view?filename={video_filename}", timeout=120).content
            
            # Salva
            save_dir = Path("storage/videos")
            save_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            filepath = str(save_dir / f"{character_name}_Video_{timestamp}.mp4")
            
            with open(filepath, "wb") as f:
                f.write(video_data)
            
            print(f"[OK] Video salvato: {filepath}")
            
            # Apri automaticamente
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", filepath])
            else:
                subprocess.Popen(["xdg-open", filepath])
            
            return filepath
            
        except Exception as e:
            print(f"[ERR] Errore video: {e}")
            import traceback
            traceback.print_exc()
            return ""
        finally:
            self._reload_sd()

    def _build_temporal_prompt(self, context, character, location, action):
        """Genera prompt temporale semplice."""
        return (f"(At 0 seconds: {character} in {location}, {action}, standing pose) "
                f"(At 1 second: Camera moves closer, movement begins) "
                f"(At 2 seconds: Dynamic motion, realistic body physics) "
                f"(At 3 seconds: Close up action, detailed movement) "
                f"(At 4 seconds: Stabilizing, slow final pose)")
