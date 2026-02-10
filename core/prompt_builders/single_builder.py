"""Builder per scene single-character."""
import random
import re
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
        
        # DEBUG: Log dei valori per verificare chi viene generato
        print(f"    [DEBUG] Scene primary_subject: {scene.primary_subject}")
        print(f"    [DEBUG] GameSession companion: {game_session.companion_name}")
        print(f"    [DEBUG] Final char_name: {char_name}")
        
        # Lista delle companion conosciute (hanno LoRA specifici)
        known_companions = set(world_data.get("companions", {}).keys())
        is_known_companion = char_name in known_companions
        print(f"    [DEBUG] Known companions: {known_companions}")
        print(f"    [DEBUG] Is known companion: {is_known_companion}")
        
        # Recupera outfit corrente
        if char_name == game_session.companion_name:
            outfit_key = game_session.current_outfit
        else:
            npc_state = game_session.npc_states.get(char_name, {})
            outfit_key = npc_state.get("current_outfit", "default")
        
        # Costruisci base prompt
        if is_known_companion:
            # Companion conosciuta: usa il suo base prompt (con LoRA)
            base_raw = BASE_PROMPTS.get(char_name, NPC_BASE)
        else:
            # NPC generico o sconosciuto: usa base prompt generico SENZA LoRA
            base_raw = NPC_BASE
        
        base_clean = clean_base_prompt(base_raw, is_multi=False)
        
        # Se è un NPC generico, rimuovi i LoRA dei companion
        if not is_known_companion:
            # Rimuovi tutti i LoRA (pattern: <lora:...>)
            base_clean = re.sub(r'<lora:[^>]+>', '', base_clean)
            # Rimuovi tag personaggio-specifici
            base_clean = re.sub(r'\b(stsdebbie|stssmith|alice_milf_catchers)\b', '', base_clean, flags=re.IGNORECASE)
            # Pulisci spazi multipli
            base_clean = re.sub(r'\s+', ' ', base_clean).strip(', ')
            print(f"    [NPC Generic] Using base without character LoRAs for '{char_name}'")
        
        # Costruisci outfit (solo per companion conosciute)
        world_wardrobe = {
            name: data.wardrobe
            for name, data in world_data.get("companions", {}).items()
        }
        outfit_str = get_outfit_for_character(
            char_name, outfit_key, world_wardrobe, visual_en
        )
        
        # Se è un NPC generico, non forzare l'outfit della companion
        if not is_known_companion:
            outfit_str = ""  # Lascia che l'LLM decida l'outfit dalla descrizione visiva
        
        # Assembla prompt
        parts = []
        
        # 1. Character base
        static_poses = ["standing", "seated", "sitting", "leaning", "arms_crossed"]
        has_static_pose = any(p in " ".join(tags_en).lower() for p in static_poses)
        if has_static_pose and "dynamic pose" in base_clean.lower():
            base_clean = base_clean.replace("dynamic pose", "").replace(", ,", ",").strip(", ")
        parts.append(base_clean)
        
        # 2. Outfit (solo per companion conosciute)
        if outfit_str:
            parts.append(outfit_str.replace(":1.3", "").replace(":1.2", ""))
        
        # 3. Tags - Rimuovi tag personaggio-specifici per NPC generici
        clean_tags = []
        for t in tags_en:
            t_lower = t.lower()
            # Per NPC generici, rimuovi tutti i tag dei companion
            if not is_known_companion and t_lower in ["stsdebbie", "alice_milf_catchers", "stssmith", 
                                                       "brown hair", "blonde", "1girl"]:
                continue
            clean_tags.append(t)
        
        if clean_tags:
            parts.append(", ".join(clean_tags))
        else:
            parts.append("detailed background, natural lighting")
        
        # 4. Visual description (ESSENZIALE per NPC generici!)
        if visual_en and len(visual_en) > 5:
            visual_clean = visual_en.strip().rstrip(",.;")
            if visual_clean:
                parts.append(visual_clean)
                print(f"    [Visual] {visual_clean[:60]}...")
        
        # 5. Composition boost
        if body_focus:
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
