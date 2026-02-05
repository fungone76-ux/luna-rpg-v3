"""Async LLM client supporting multiple providers (Gemini + Moonshot/Kimi)."""
import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from google import genai
from google.genai import types

from core.models import LLMResponse, GameStateUpdate
from config.settings import Settings


class LLMClient:
    """Client async multi-provider per LLM (Gemini + Moonshot/Kimi)."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.provider: str = self.settings.llm_provider
        
        # Gemini client (ALWAYS initialize as fallback)
        self.gemini_client: Optional[genai.Client] = None
        self.gemini_model: str = "gemini-3-pro-preview"
        
        # Moonshot client (OpenAI-compatible)
        self.moonshot_api_key: str = self.settings.moonshot_api_key
        self.moonshot_base_url: str = "https://api.moonshot.cn/v1"
        self.moonshot_model: str = "kimi-k2.5"  # NOT "kimi-k2-5" - use DOT not DASH
        
        # Initialize BOTH clients (primary + fallback)
        self._init_gemini()  # Always init Gemini as fallback
        
        if self.provider == "moonshot":
            self._init_moonshot()
    
    def _init_gemini(self):
        """Initialize Gemini client."""
        if self.settings.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.settings.gemini_api_key)
                print(f"[OK] Gemini client initialized ({self.gemini_model})")
            except Exception as e:
                print(f"[ERR] Gemini init error: {e}")
                # Fallback to moonshot if available
                if self.moonshot_api_key:
                    print("[->] Falling back to Moonshot...")
                    self.provider = "moonshot"
                    self._init_moonshot()
    
    def _init_moonshot(self):
        """Initialize Moonshot client (OpenAI-compatible)."""
        if self.moonshot_api_key:
            print(f"[OK] Moonshot client initialized ({self.moonshot_model})")
        else:
            print("[ERR] Moonshot API key not found")
    
    async def generate_response(
        self,
        user_input: str,
        system_instruction: str,
        history: List[Dict[str, str]],
        memory_context: str = ""
    ) -> LLMResponse:
        """Genera risposta dall'LLM usando il provider attivo."""
        
        # Try primary provider first
        if self.provider == "gemini" and self.gemini_client:
            result = await self._generate_gemini(
                user_input, system_instruction, history, memory_context
            )
            # If Gemini succeeds (has text), return it
            if result.text and len(result.text.strip()) > 10:
                return result
            # If Gemini fails, try Moonshot fallback
            if self.moonshot_api_key:
                print("[->] Gemini failed, trying Moonshot fallback...")
                return await self._generate_moonshot(
                    user_input, system_instruction, history, memory_context
                )
            return result
            
        elif self.provider == "moonshot" and self.moonshot_api_key:
            # Try JSON mode first (more reliable)
            result = await self._generate_moonshot_json(
                user_input, system_instruction, history, memory_context
            )
            
            # If JSON mode succeeded
            if result and result.text and len(result.text.strip()) > 10:
                print("[OK] Moonshot JSON mode succeeded")
                return result
            
            # JSON mode failed or not supported, try text mode
            print("[->] JSON mode failed, trying text mode...")
            result = await self._generate_moonshot(
                user_input, system_instruction, history, memory_context
            )
            
            # If Moonshot text succeeds, return it
            if result.text and len(result.text.strip()) > 10 and not result.text.startswith("Mi scuso"):
                return result
                
            # If Moonshot fails, try Gemini fallback
            if self.gemini_client:
                print("[->] Moonshot failed, trying Gemini fallback...")
                return await self._generate_gemini(
                    user_input, system_instruction, history, memory_context
                )
            return result
        
        # No primary provider configured, try fallbacks
        elif self.gemini_client:
            return await self._generate_gemini(
                user_input, system_instruction, history, memory_context
            )
        elif self.moonshot_api_key:
            return await self._generate_moonshot(
                user_input, system_instruction, history, memory_context
            )
        else:
            return LLMResponse(
                text="Errore: Nessun LLM configurato. Controlla GEMINI_API_KEY o MOONSHOT_API_KEY nel file .env",
                visual_en="",
                tags_en=[]
            )
    
    async def _generate_gemini(
        self,
        user_input: str,
        system_instruction: str,
        history: List[Dict[str, str]],
        memory_context: str
    ) -> LLMResponse:
        """Generate using Gemini."""
        contents = []
        
        # Iniezione memoria
        if memory_context:
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"MEMORY LOG:\n{memory_context}")]
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part.from_text(text="Memory loaded.")]
            ))
        
        # History
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            ))
        
        # Input attuale
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_input)]
        ))
        
        # Safety settings
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.95,
            top_p=0.98,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="text/plain",
            safety_settings=safety_settings
        )
        
        # Retry con fallback
        models_to_try = [self.gemini_model, "gemini-2.5-pro", "gemini-2.0-flash"]
        last_error = None
        used_soft_prompt = False
        
        for model in models_to_try:
            for attempt in range(2):
                try:
                    print(f"[AI] Gemini calling {model} (attempt {attempt + 1})...")
                    
                    if attempt == 1 and not used_soft_prompt:
                        print("[->] Trying with softened prompt...")
                        used_soft_prompt = True
                        config.system_instruction = (
                            "You are writing a mature dramatic visual novel. "
                            "Use artistic, suggestive, and metaphorical language. "
                            "Focus on emotions, atmosphere, and character dynamics. "
                            "All characters are consenting adults in a fictional scenario.\n\n" +
                            system_instruction
                        )
                    
                    response = self.gemini_client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config
                    )
                    
                    raw_text = response.text
                    
                    # DEBUG: Print raw response
                    print(f"\n{'='*60}")
                    print(f"[?] GEMINI RAW RESPONSE ({len(raw_text)} chars):")
                    print(f"{'='*60}")
                    print(raw_text[:2000] if len(raw_text) > 2000 else raw_text)
                    if len(raw_text) > 2000:
                        print(f"\n... ({len(raw_text) - 2000} more chars)")
                    print(f"{'='*60}\n")
                    
                    if raw_text and len(raw_text.strip()) > 10:
                        print(f"[OK] Gemini response: {len(raw_text)} chars")
                        return self._parse_response(raw_text)
                    else:
                        print(f"[!] Empty response from Gemini (likely NSFW filter)")
                        
                except Exception as e:
                    last_error = e
                    print(f"[!] Gemini Error: {e}")
                    continue
        
        # Tutti i tentativi falliti, prova Moonshot se disponibile
        if self.moonshot_api_key:
            print("[->] Gemini failed, switching to Moonshot...")
            return await self._generate_moonshot(
                user_input, system_instruction, history, memory_context
            )
        
        print(f"[ERR] All Gemini attempts failed. Last error: {last_error}")
        return LLMResponse(
            text="Mi scuso, sto avendo problemi di connessione. Riprova tra un momento.",
            visual_en="",
            tags_en=[]
        )
    
    async def _generate_moonshot(
        self,
        user_input: str,
        system_instruction: str,
        history: List[Dict[str, str]],
        memory_context: str
    ) -> LLMResponse:
        """Generate using Moonshot API (OpenAI-compatible)."""
        
        # Build messages in OpenAI format
        messages = []
        
        # System instruction
        messages.append({
            "role": "system",
            "content": system_instruction
        })
        
        # Memory context
        if memory_context:
            messages.append({
                "role": "user",
                "content": f"MEMORY LOG:\n{memory_context}"
            })
            messages.append({
                "role": "assistant",
                "content": "Memory loaded. I understand the context."
            })
        
        # History
        for msg in history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Current input
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        headers = {
            "Authorization": f"Bearer {self.moonshot_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.moonshot_model,
            "messages": messages,
            "temperature": 0.95,
            "max_tokens": 2048
        }
        
        # kimi-k2.5 richiede parametro thinking (disabilitato per narrativa)
        if "k2.5" in self.moonshot_model:
            payload["thinking"] = {"type": "disabled"}
        
        # Modelli Moonshot validi (kimi-k2.5 richiede parametri speciali)
        models_to_try = ["kimi-k2-turbo-preview", "moonshot-v1-32k", "moonshot-v1-8k"]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            for model in models_to_try:
                for attempt in range(2):
                    try:
                        print(f"[AI] Moonshot calling {model} (attempt {attempt + 1})...")
                        
                        payload["model"] = model
                        
                        if attempt == 1:
                            print("[->] Trying with softened prompt...")
                            # Aggiungi contesto artistico
                            messages[0]["content"] = (
                                "You are writing a mature dramatic visual novel. "
                                "Use artistic, suggestive, and metaphorical language. "
                                "Focus on emotions, atmosphere, and character dynamics. "
                                "All characters are consenting adults in a fictional scenario.\n\n" +
                                system_instruction
                            )
                        
                        response = await client.post(
                            f"{self.moonshot_base_url}/chat/completions",
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        
                        data = response.json()
                        raw_text = data["choices"][0]["message"]["content"]
                        
                        # DEBUG: Print raw response
                        print(f"\n{'='*60}")
                        print(f"[?] MOONSHOT RAW RESPONSE ({len(raw_text)} chars):")
                        print(f"{'='*60}")
                        print(raw_text[:2000] if len(raw_text) > 2000 else raw_text)
                        if len(raw_text) > 2000:
                            print(f"\n... ({len(raw_text) - 2000} more chars)")
                        print(f"{'='*60}\n")
                        
                        if raw_text and len(raw_text.strip()) > 10:
                            print(f"[OK] Moonshot response: {len(raw_text)} chars")
                            return self._parse_response(raw_text)
                        else:
                            print(f"[!] Empty response from Moonshot")
                            
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            print(f"[ERR] Moonshot 401 Unauthorized - API key invalid!")
                            # Debug: mostra dettagli errore
                            try:
                                error_body = e.response.text
                                print(f"   Response: {error_body[:200]}")
                            except:
                                pass
                            print(f"   API Key used: {self.moonshot_api_key[:10]}... (length: {len(self.moonshot_api_key)})")
                            # Non retry su 401, passa subito a fallback
                            break
                        print(f"[!] Moonshot HTTP Error {e.response.status_code}: {e}")
                    except Exception as e:
                        print(f"[!] Moonshot Error: {e}")
                        continue
        
        # Se Moonshot fallisce con 401, prova immediatamente Gemini
        if self.gemini_client:
            print("[->] Moonshot failed with auth error, switching to Gemini fallback...")
            return await self._generate_gemini(
                user_input, system_instruction, history, memory_context
            )
        
        print("[ERR] All Moonshot attempts failed")
        return LLMResponse(
            text="Mi scuso, sto avendo problemi di connessione. Riprova tra un momento.",
            visual_en="",
            tags_en=[]
        )
    
    async def analyze_scene(self, prompt: str, system_prompt: str) -> str:
        """Chiamata leggera per analisi scene (usata da SceneAnalyzer)."""
        
        if self.provider == "gemini" and self.gemini_client:
            try:
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.0-flash",  # Veloce per analisi
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                        max_output_tokens=512,
                        response_mime_type="application/json"
                    )
                )
                return response.text
            except Exception as e:
                print(f"[!] Gemini scene analysis error: {e}")
                # Fallback to moonshot
                if self.moonshot_api_key:
                    return await self._analyze_scene_moonshot(prompt, system_prompt)
                return "{}"
        
        elif self.provider == "moonshot" and self.moonshot_api_key:
            return await self._analyze_scene_moonshot(prompt, system_prompt)
        
        return "{}"
    
    async def _analyze_scene_moonshot(self, prompt: str, system_prompt: str) -> str:
        """Scene analysis using Moonshot."""
        try:
            headers = {
                "Authorization": f"Bearer {self.moonshot_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "moonshot-v1-8k",  # Piccolo e veloce per analisi
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 512
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.moonshot_base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except Exception as e:
            print(f"[!] Moonshot scene analysis error: {e}")
            return "{}"
    
    async def summarize(self, messages: List[Dict[str, str]]) -> str:
        """Riassume una lista di messaggi."""
        
        # Prepara testo
        text_block = ""
        for m in messages:
            role = "Player" if m["role"] == "user" else "Game Master"
            content = m["content"]
            content = re.sub(r'```json.*?```', '', content, flags=re.DOTALL).strip()
            if content:
                text_block += f"{role}: {content}\n"
        
        prompt = (
            "Analizza questo log RPG e crea un riassunto TELEGRAFICO:\n"
            "- SOLO: Decisioni chiave, luoghi, NPC incontrati, fatti importanti\n"
            "- IGNORA: Descrizioni erotiche, dialoghi riempitivi\n"
            "- Max 3 frasi, italiano, terza persona\n\n"
            f"LOG:\n{text_block}"
        )
        
        if self.provider == "gemini" and self.gemini_client:
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                print(f"[!] Gemini summarize error: {e}")
                if self.moonshot_api_key:
                    return await self._summarize_moonshot(prompt)
                return "Riassunto non disponibile."
        
        elif self.provider == "moonshot" and self.moonshot_api_key:
            return await self._summarize_moonshot(prompt)
        
        return "Riassunto non disponibile."
    
    async def _summarize_moonshot(self, prompt: str) -> str:
        """Summarize using Moonshot."""
        try:
            headers = {
                "Authorization": f"Bearer {self.moonshot_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "moonshot-v1-8k",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 256
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.moonshot_base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
                
        except Exception as e:
            print(f"[!] Moonshot summarize error: {e}")
            return "Riassunto non disponibile."
    
    def _parse_response(self, raw_text: str) -> LLMResponse:
        """Parsa la risposta MARKUP dall'LLM - NUOVO FORMATO SEMPLICE."""
        result = LLMResponse(text=raw_text)
        
        if not raw_text:
            return result
        
        # 1. Cerca il blocco METADATA
        metadata_match = re.search(r'---METADATA---\s*(.*?)(?=\n\n|$)', raw_text, re.DOTALL)
        
        if metadata_match:
            metadata = metadata_match.group(1).strip()
            print("[OK] METADATA block found")
            
            # Estrai campi con regex
            # VISUAL: descrizione
            visual_match = re.search(r'VISUAL:\s*(.+?)(?=\n\w+:|\n\n|$)', metadata, re.DOTALL)
            if visual_match:
                result.visual_en = visual_match.group(1).strip().replace('\n', ' ')
            
            # TAGS: tag1, tag2, tag3
            tags_match = re.search(r'TAGS:\s*(.+?)(?=\n\w+:|\n\n|$)', metadata, re.DOTALL)
            if tags_match:
                tags_str = tags_match.group(1).strip()
                # Split by comma e pulisci
                result.tags_en = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            # BODY_FOCUS: parte del corpo (può essere vuoto)
            body_match = re.search(r'BODY_FOCUS:\s*(\w*)', metadata)
            if body_match and body_match.group(1).strip():
                result.body_focus = body_match.group(1).strip()
            
            # APPROACH: tipo di approccio
            approach_match = re.search(r'APPROACH:\s*(\w+)', metadata)
            if approach_match:
                result.approach_used = approach_match.group(1).strip()
            
            # Estrai updates per GameStateUpdate
            updates = {}
            
            # TIME -> time_of_day
            time_match = re.search(r'TIME:\s*(\w+)', metadata)
            if time_match:
                updates['time_of_day'] = time_match.group(1).strip()
            
            # LOCATION -> location
            location_match = re.search(r'LOCATION:\s*(.+?)(?=\n\w+:|\n\n|$)', metadata, re.DOTALL)
            if location_match:
                updates['location'] = location_match.group(1).strip().replace('\n', ' ')
            
            # AFFINITY -> affinity_change
            affinity_match = re.search(r'AFFINITY:\s*([+-]?\d+)', metadata)
            if affinity_match:
                affinity_val = int(affinity_match.group(1))
                # Dobbiamo sapere il nome del character, per ora usiamo placeholder
                # Verrà gestito dall'engine
                updates['affinity_change'] = {'companion': affinity_val}
            
            # OUTFIT -> current_outfit
            outfit_match = re.search(r'OUTFIT:\s*(\w+)', metadata)
            if outfit_match:
                updates['current_outfit'] = outfit_match.group(1).strip()
            
            # NPC -> npc_updates
            npc_match = re.search(r'NPC:\s*(.+?)(?=\n\w+:|\n\n|$)', metadata, re.DOTALL)
            if npc_match and npc_match.group(1).strip():
                npc_str = npc_match.group(1).strip()
                npc_updates = {}
                # Parse formato: "Name:key=value,Name2:key2=value2"
                for npc_entry in npc_str.split(','):
                    if ':' in npc_entry:
                        name, rest = npc_entry.split(':', 1)
                        name = name.strip()
                        if '=' in rest:
                            key, value = rest.split('=', 1)
                            if name not in npc_updates:
                                npc_updates[name] = {}
                            npc_updates[name][key.strip()] = value.strip()
                if npc_updates:
                    updates['npc_updates'] = npc_updates
            
            # Crea GameStateUpdate
            if updates:
                result.updates = GameStateUpdate(**updates)
            
            print(f"[OK] Parsed: visual={len(result.visual_en)} chars, tags={len(result.tags_en)} items")
            
        else:
            # Fallback: cerca formato JSON vecchio (per retrocompatibilità)
            print("[!] No METADATA block, trying JSON fallback...")
            self._parse_json_fallback(raw_text, result)
        
        # FINAL CLEANUP - rimuovi METADATA/JSON dal testo per display
        result.text = re.sub(r'---METADATA---\s*[\s\S]*?(?=\n\n|$)', '', result.text, flags=re.IGNORECASE)
        result.text = re.sub(r"```json\s*[\s\S]*?```", "", result.text, flags=re.IGNORECASE)
        result.text = re.sub(r"```\s*[\s\S]*?```", "", result.text)
        result.text = result.text.strip()
        
        return result
    
    def _parse_json_fallback(self, raw_text: str, result: LLMResponse):
        """Fallback per formato JSON vecchio."""
        try:
            # Cerca JSON
            json_match = re.search(r"```json\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
            if not json_match:
                json_match = re.search(r"(\{[\s\S]*?\"visual_en\"[\s\S]*?\})", raw_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1).strip()
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
                
                data = json.loads(json_str)
                result.visual_en = data.get("visual_en", "")
                result.tags_en = data.get("tags_en", [])
                result.body_focus = data.get("body_focus")
                result.approach_used = data.get("approach_used", "standard")
                updates = data.get("updates", {})
                result.updates = GameStateUpdate(**updates) if updates else GameStateUpdate()
                print("[OK] JSON fallback parsed")
        except Exception as e:
            print(f"[!] JSON fallback failed: {e}")


    async def _generate_moonshot_json(
        self,
        user_input: str,
        system_instruction: str,
        history: List[Dict[str, str]],
        memory_context: str
    ) -> LLMResponse:
        """Generate using Moonshot with JSON mode (forced JSON output).
        
        Moonshot API (OpenAI-compatible) supports response_format={"type": "json_object"}
        which forces the model to return valid JSON.
        """
        
        # JSON Schema for the response
        json_schema = {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Narrative text in Italian, 3-4 sentences, second person"
                },
                "visual_en": {
                    "type": "string",
                    "description": "Visual description for Stable Diffusion. Static pose only, NO expressions/movement. 20-35 words."
                },
                "tags_en": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "12-20 SD tags, comma-separated concepts. NO weights, NO person names."
                },
                "body_focus": {
                    "type": "string",
                    "enum": ["", "legs", "ass", "breasts", "pussy", "face", "hands", "torso", "back"],
                    "description": "Body part to focus on, or empty"
                },
                "approach_used": {
                    "type": "string",
                    "enum": ["standard", "physical_action", "question", "choice"],
                    "description": "NPC approach type"
                },
                "time_of_day": {
                    "type": "string",
                    "enum": ["Morning", "Afternoon", "Evening", "Night"],
                    "description": "Time of day"
                },
                "location": {
                    "type": "string",
                    "description": "Current location"
                },
                "affinity_change": {
                    "type": "number",
                    "description": "Affinity change (+/- integer)"
                },
                "current_outfit": {
                    "type": "string",
                    "description": "Outfit key the character is wearing"
                }
            },
            "required": ["text", "visual_en", "tags_en"]
        }
        
        # Build messages
        messages = []
        
        # System instruction with JSON guidance
        json_system_prompt = f"""{system_instruction}

CRITICAL: You MUST respond with a valid JSON object matching this exact schema:
- text: Narrative in Italian (required)
- visual_en: Visual description for image generation (required)
- tags_en: Array of SD tags like ["medium shot", "standing", "classroom"] (required)
- body_focus: Body part focus or empty string (optional)
- approach_used: One of standard/physical_action/question/choice (optional)
- time_of_day: Morning/Afternoon/Evening/Night (optional)
- location: Location name (optional)
- affinity_change: Number like +2 or -1 (optional)
- current_outfit: Outfit key (optional)

Example response:
{{
  "text": "Luna ti guarda con un sorriso malizioso. Si avvicina lentamente, i fianchi che ondeggiano ad ogni passo.",
  "visual_en": "Medium shot from eye level, Luna walking toward viewer with swaying hips, hand on hip, classroom afternoon light",
  "tags_en": ["medium shot", "eye level", "walking pose", "hand on hip", "looking at viewer", "classroom", "afternoon light", "depth of field", "masterpiece"],
  "body_focus": "",
  "approach_used": "physical_action",
  "affinity_change": 2
}}"""
        
        messages.append({
            "role": "system",
            "content": json_system_prompt
        })
        
        # Memory context
        if memory_context:
            messages.append({
                "role": "user",
                "content": f"MEMORY LOG:\n{memory_context}"
            })
            messages.append({
                "role": "assistant",
                "content": "Memory loaded. I understand the context."
            })
        
        # History
        for msg in history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Current input
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        headers = {
            "Authorization": f"Bearer {self.moonshot_api_key}",
            "Content-Type": "application/json"
        }
        
        models_to_try = ["kimi-k2-turbo-preview", "moonshot-v1-32k", "moonshot-v1-8k"]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            for model in models_to_try:
                for attempt in range(2):
                    try:
                        print(f"[AI] Moonshot JSON mode calling {model} (attempt {attempt + 1})...")
                        
                        payload = {
                            "model": model,
                            "messages": messages,
                            "temperature": 0.95,
                            "max_tokens": 2048,
                            "response_format": {"type": "json_object"}  # <-- JSON MODE!
                        }
                        
                        response = await client.post(
                            f"{self.moonshot_base_url}/chat/completions",
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        
                        data = response.json()
                        raw_text = data["choices"][0]["message"]["content"]
                        
                        # DEBUG: Print raw JSON
                        print(f"\n{'='*60}")
                        print(f"[?] MOONSHOT JSON RAW ({len(raw_text)} chars):")
                        print(f"{'='*60}")
                        print(raw_text[:2000] if len(raw_text) > 2000 else raw_text)
                        print(f"{'='*60}\n")
                        
                        # Parse JSON directly (should be valid!)
                        try:
                            json_data = json.loads(raw_text)
                            
                            # Build LLMResponse from JSON
                            result = LLMResponse(
                                text=json_data.get("text", ""),
                                visual_en=json_data.get("visual_en", ""),
                                tags_en=json_data.get("tags_en", []),
                                body_focus=json_data.get("body_focus") or None,
                                approach_used=json_data.get("approach_used", "standard")
                            )
                            
                            # Build GameStateUpdate from JSON
                            updates = {}
                            if "time_of_day" in json_data and json_data["time_of_day"]:
                                updates["time_of_day"] = json_data["time_of_day"]
                            if "location" in json_data and json_data["location"]:
                                updates["location"] = json_data["location"]
                            if "current_outfit" in json_data and json_data["current_outfit"]:
                                updates["current_outfit"] = json_data["current_outfit"]
                            if "affinity_change" in json_data:
                                updates["affinity_change"] = {"companion": int(json_data["affinity_change"])}
                            
                            if updates:
                                result.updates = GameStateUpdate(**updates)
                            
                            print(f"[OK] Moonshot JSON parsed: visual={len(result.visual_en)} chars, tags={len(result.tags_en)} items")
                            return result
                            
                        except json.JSONDecodeError as e:
                            print(f"[!] JSON decode error (shouldn't happen in JSON mode!): {e}")
                            # Fallback to text parsing
                            return self._parse_response(raw_text)
                            
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 400:
                            error_text = e.response.text
                            print(f"[!] Moonshot 400 Error: {error_text[:300]}")
                            if "json_schema" in error_text.lower() or "response_format" in error_text.lower():
                                print("[!] JSON mode not supported by this model, falling back to text mode...")
                                return None  # Signal to use text mode
                        elif e.response.status_code == 401:
                            print(f"[ERR] Moonshot 401 Unauthorized")
                            break
                        else:
                            print(f"[!] Moonshot HTTP Error {e.response.status_code}: {e}")
                    except Exception as e:
                        print(f"[!] Moonshot JSON Error: {e}")
                        continue
        
        print("[ERR] All Moonshot JSON attempts failed")
        return None

