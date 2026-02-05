"""Builder per scene single-character."""
import random
from typing import Dict, List, Optional

from core.models import SceneAnalysis, GameSession
from core.prompt_builders.base import (
    PromptResult, BASE_PROMPTS, NPC_BASE, NEGATIVE_BASE,
    get_outfit_for_character, clean_base_prompt
)


class SingleCharacterBuilder:
    """Costruisce prompt per scene con un solo personaggio in focus."""
    
    def build(
        self,
        scene: SceneAnalysis,
        visual_en: str,
        tags_en: List[str],
        game_session: GameSession,
        world_data: Dict,
        body_focus: Optional[str] = None
    ) -> PromptResult:
        """Costruisce il prompt per una scena single-character.
        
        Args:
            scene: Analisi della scena (con primary_subject popolato)
            visual_en: Descrizione visiva dall'LLM
            tags_en: Tag tecnici dall'LLM
            game_session: Stato corrente del gioco
            world_data: Dati del mondo (companions, wardrobe)
        """
        char_name = scene.primary_subject or game_session.companion_name
        
        # Recupera outfit corrente
        if char_name == game_session.companion_name:
            outfit_key = game_session.current_outfit
        else:
            npc_state = game_session.npc_states.get(char_name, {})
            outfit_key = npc_state.get("current_outfit", "default")
        
        # Costruisci base prompt
        base_raw = BASE_PROMPTS.get(char_name, NPC_BASE)
        base_clean = clean_base_prompt(base_raw, is_multi=False)
        
        # Costruisci outfit
        world_wardrobe = {
            name: data.wardrobe
            for name, data in world_data.get("companions", {}).items()
        }
        outfit_str = get_outfit_for_character(
            char_name, outfit_key, world_wardrobe, visual_en
        )
        
        # Assembla prompt - SIMPLIFIED
        parts = []
        
        # 1. Character base (already has quality tags + LoRAs)
        # Remove "dynamic pose" if we have specific static poses
        static_poses = ["standing", "seated", "sitting", "leaning", "arms_crossed"]
        has_static_pose = any(p in " ".join(tags_en).lower() for p in static_poses)
        if has_static_pose and "dynamic pose" in base_clean.lower():
            base_clean = base_clean.replace("dynamic pose", "").replace(", ,", ",").strip(", ")
        parts.append(base_clean)
        
        # NOTA: I realism boosters sono stati rimossi perche' interferivano con la qualita'
        # Il base prompt contiene gia' tutti i quality tag necessari (score_9, score_8_up, etc.)
        
        # 2. Outfit (NO WEIGHT)
        parts.append(outfit_str.replace(":1.3", "").replace(":1.2", ""))
        
        # 3. Tags - KEEP ALMOST EVERYTHING, minimal cleaning
        # Only remove exact duplicates from base prompt
        base_lower = base_clean.lower()
        clean_tags = []
        for t in tags_en:
            t_lower = t.lower()
            # Skip only if already in base AND it's a character-specific tag
            if t_lower in ["stsdebbie", "alice_milf_catchers", "stssmith"]:
                continue
            clean_tags.append(t)
        
        # Add ALL tags from LLM
        if clean_tags:
            parts.append(", ".join(clean_tags))
        else:
            # Fallback se tags_en è vuoto
            parts.append("detailed background, natural lighting")
        
        # 4. Visual description - KEEP IT COMPLETELY INTACT
        # This is where the scene variety comes from!
        if visual_en and len(visual_en) > 5:
            # Remove only trailing punctuation issues
            visual_clean = visual_en.strip().rstrip(",.;")
            if visual_clean:
                parts.append(visual_clean)
                print(f"    [Visual] {visual_clean[:60]}...")
        
        # Composition boost based on scene type OR body focus
        if body_focus:
            # Override composition based on body focus
            if body_focus in ["legs", "feet", "lower_body"]:
                parts.append("cowboy_shot, lower_body, legs_focus, depth of field")
            elif body_focus in ["chest", "breasts", "torso"]:
                parts.append("medium_shot, upper_body, torso_focus, cleavage")
            elif body_focus in ["face", "expression"]:
                parts.append("close_up, portrait, face_focus, detailed_face")
            elif body_focus in ["hands", "fingers"]:
                parts.append("close_up, hand_focus, detailed_hands")
            elif body_focus in ["back", "behind"]:
                parts.append("from_behind, back_focus, back")
        else:
            # Use scene composition type
            if scene.composition_type.value == "close_up":
                parts.append("close up portrait, detailed face, depth of field")
            elif scene.composition_type.value == "wide_shot":
                parts.append("wide shot, full body, environmental")
        
        positive = ", ".join([p.strip().strip(",") for p in parts if p])
        
        return PromptResult(
            positive=positive,
            negative=NEGATIVE_BASE,
            width=896,
            height=1152
        )
