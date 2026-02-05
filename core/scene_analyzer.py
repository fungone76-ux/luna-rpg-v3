"""Analisi semantica intelligente delle scene con LLM.

Sostituisce il vecchio PromptDispatcher basato su regex con una comprensione
teffettiva del contesto narrativo.
"""
import json
from typing import Optional

from google import genai
from google.genai import types

from core.models import SceneAnalysis, CompositionType, WorldConfig
from config.settings import Settings


class SceneAnalyzer:
    """Analizza il contesto narrativo per determinare la composizione dell'immagine.
    
    Esempio:
        "Guardo Luna sedersi vicino a Stella" 
        → primary=Luna, secondary=[], background=[Stella]
        
        "Luna e Stella si abbracciano"
        → primary=None, secondary=[Luna, Stella], composition=GROUP
    """
    
    SYSTEM_PROMPT = """You are a Scene Composition Analyzer for a visual novel AI.
Your job is to analyze narrative text and determine WHO should be visible in the generated image.

RULES:
1. primary_subject: The MAIN character in focus (the one DOING the action). Null if it is a group scene.
2. secondary_subjects: Other characters VISIBLY PRESENT in the scene (not just mentioned).
3. background_mentions: Characters NAMED but NOT visually present (e.g., "near Stella" - Stella provides context but may not be in frame).
4. composition_type: CLOSE_UP (face/detail), MEDIUM_SHOT (waist up), WIDE_SHOT (full body/environment), GROUP (2+ equal subjects).

IMPORTANT DISTINCTIONS:
- "Luna sits next to Stella" -> Luna is primary, Stella is secondary (both visible)
- "I watch Luna sit down near Stella" -> Luna is primary, Stella is background (Luna in focus, Stella just context)
- "Luna and Stella hug" -> GROUP, both secondary, no primary
- "Luna looks at Stella" -> Luna is primary (active), Stella is secondary (object of gaze)

Available characters: {available_companions}

Respond ONLY with valid JSON in this exact format:
{{
    "primary_subject": "Name or null",
    "secondary_subjects": ["Name1", "Name2"],
    "background_mentions": ["Name3"],
    "composition_type": "close_up|medium_shot|wide_shot|group",
    "action_focus": "brief description of main action",
    "frame_type": "close_up|medium_shot|wide_shot|group",
    "reasoning": "explanation of your decision"
}}"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.client: Optional[genai.Client] = None
        self.model_id: Optional[str] = None
        
        if self.settings.gemini_api_key:
            try:
                self.client = genai.Client(api_key=self.settings.gemini_api_key)
                self.model_id = "gemini-3-flash-preview"  # Veloce ed economico per scene analysis
            except Exception as e:
                print(f"[!] SceneAnalyzer init error: {e}")
    
    async def analyze(
        self, 
        narrative_text: str, 
        visual_request: str,
        world_config: WorldConfig
    ) -> SceneAnalysis:
        """Analizza la scena e restituisce la composizione.
        
        Args:
            narrative_text: Testo narrativo completo
            visual_request: La parte visual_en specifica
            world_config: Configurazione mondo per sapere chi sono i personaggi
        """
        if not self.client:
            # Fallback se LLM non disponibile: analisi semplice
            return self._fallback_analysis(narrative_text, visual_request, world_config)
        
        available = list(world_config.companions.keys())
        
        system_prompt = self.SYSTEM_PROMPT.format(
            available_companions=", ".join(available)
        )
        
        user_prompt = f"""Analyze this scene:

NARRATIVE: {narrative_text}
VISUAL REQUEST: {visual_request}

Determine the image composition."""
        
        # Prova con retry e fallback
        models_to_try = [self.model_id, "gemini-2.5-flash", "gemini-2.0-flash"]
        last_error = None
        
        for model in models_to_try:
            for attempt in range(2):
                try:
                    print(f"[?] SceneAnalyzer calling {model} (attempt {attempt + 1})...")
                    response = self.client.models.generate_content(
                        model=model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.1,
                            max_output_tokens=1024
                        )
                    )
                    
                    # Parse JSON response
                    if not response or not response.text:
                        print(f"[!] SceneAnalyzer: Empty response from {model}")
                        continue
                    
                    json_str = response.text.strip()
                    print(f"[?] SceneAnalyzer raw: {repr(json_str[:300])}")
                    
                    # Rimuovi eventuali markdown code blocks
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    json_str = json_str.strip()
                    
                    # Fix per JSON con single quotes invece di double quotes
                    import re
                    if json_str.startswith("{") and "'" in json_str:
                        json_str = re.sub(r"'([^']+)':\s*", r'"\1": ', json_str)
                        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
                    
                    # Se non inizia con {, cerca JSON nell'output
                    if not json_str.startswith("{"):
                        match = re.search(r'\{[\s\S]*\}', json_str)
                        if match:
                            json_str = match.group(0)
                    
                    data = json.loads(json_str.strip())
                    
                    # Validazione e sanitizzazione
                    print(f"[OK] SceneAnalyzer success with {model}")
                    return self._sanitize_analysis(data, available)
                    
                except Exception as e:
                    last_error = e
                    print(f"[!] SceneAnalyzer error with {model}: {e}")
                    continue
        
        # Tutti i tentativi falliti
        print(f"[!] SceneAnalyzer all attempts failed. Using fallback. Last error: {last_error}")
        return self._fallback_analysis(narrative_text, visual_request, world_config)
    
    def _sanitize_analysis(self, data: dict, available: list[str]) -> SceneAnalysis:
        """Sanitizza e valida l'analisi LLM."""
        # Verifica che i nomi siano validi
        primary = data.get("primary_subject")
        if primary and primary not in available:
            primary = None
        
        secondary = [
            s for s in data.get("secondary_subjects", [])
            if s in available and s != primary
        ]
        
        background = [
            b for b in data.get("background_mentions", [])
            if b in available and b != primary and b not in secondary
        ]
        
        # Mappa composition_type
        comp_str = data.get("composition_type", "medium_shot")
        try:
            comp_type = CompositionType(comp_str.lower())
        except ValueError:
            comp_type = CompositionType.MEDIUM_SHOT
        
        return SceneAnalysis(
            primary_subject=primary,
            secondary_subjects=secondary,
            background_mentions=background,
            composition_type=comp_type,
            action_focus=data.get("action_focus", ""),
            frame_type=data.get("frame_type", "medium_shot"),
            reasoning=data.get("reasoning", "")
        )
    
    def _fallback_analysis(
        self, 
        narrative: str, 
        visual: str, 
        world: WorldConfig
    ) -> SceneAnalysis:
        """Analisi di fallback basata su keyword matching (robusto ma meno smart)."""
        text_lower = (narrative + " " + visual).lower()
        available = list(world.companions.keys())
        
        found = [name for name in available if name.lower() in text_lower]
        
        # Euristiche semplici
        if len(found) == 0:
            # Default al companion attivo (da determinare altrove)
            return SceneAnalysis(
                primary_subject=None,
                secondary_subjects=[],
                composition_type=CompositionType.MEDIUM_SHOT,
                reasoning="No characters found, default to active companion"
            )
        elif len(found) == 1:
            # Determina se è primo piano o medio
            close_indicators = ["face", "smile", "eye", "kiss", "expression", "look"]
            is_close = any(k in text_lower for k in close_indicators)
            
            return SceneAnalysis(
                primary_subject=found[0],
                secondary_subjects=[],
                composition_type=CompositionType.CLOSE_UP if is_close else CompositionType.MEDIUM_SHOT,
                reasoning=f"Single character detected: {found[0]}"
            )
        else:
            # Multi-character: cerca di capire chi è il focus
            # Se "e" o "and" tra i nomi → gruppo
            # Se uno è "vicino a" l'altro → primary + background
            
            group_indicators = [" e ", " and ", " insieme ", " together ", " abbracci", " hug", " insieme"]
            is_group = any(k in text_lower for k in group_indicators)
            
            if is_group:
                return SceneAnalysis(
                    primary_subject=None,
                    secondary_subjects=found,
                    composition_type=CompositionType.GROUP,
                    reasoning=f"Group scene detected: {', '.join(found)}"
                )
            else:
                # Primo personaggio trovato è primary, altri background
                return SceneAnalysis(
                    primary_subject=found[0],
                    secondary_subjects=found[1:] if len(found) > 1 else [],
                    composition_type=CompositionType.MEDIUM_SHOT,
                    reasoning=f"Primary: {found[0]}, others: {found[1:]}"
                )
