"""Builder per scene multi-personaggio con anti-fusion avanzato."""
from typing import Dict, List, Optional, Set, Tuple

from core.models import SceneAnalysis, GameSession
from core.prompt_builders.base import (
    PromptResult, BASE_PROMPTS, NPC_BASE, NEGATIVE_BASE, ANTI_FUSION_NEGATIVE,
    get_outfit_for_character, clean_base_prompt, extract_style_loras,
    DIFFERENTIATION_BOOSTERS
)


class MultiCharacterBuilder:
    """Costruisce prompt per scene con 2+ personaggi.
    
    Implementa strategie avanzate anti-fusion:
    1. BREAK token tra personaggi
    2. LoRA di stile globali (non per personaggio)
    3. Tag di differenziazione espliciti
    4. Composizione posizionale (left/right)
    """
    
    # Mapping colori capelli per forzare differenziazione
    HAIR_COLORS = {
        "Luna": "brown hair",
        "Stella": "blonde hair", 
        "Maria": "black hair"
    }
    
    def build(
        self,
        scene: SceneAnalysis,
        visual_en: str,
        tags_en: List[str],
        game_session: GameSession,
        world_data: Dict,
        body_focus: Optional[str] = None
    ) -> PromptResult:
        """Costruisce prompt multi-character."""
        
        subjects = scene.get_all_present_subjects()
        if len(subjects) < 2:
            # Fallback a single se c'è un solo soggetto
            from core.prompt_builders.single_builder import SingleCharacterBuilder
            return SingleCharacterBuilder().build(
                scene, visual_en, tags_en, game_session, world_data,
                body_focus=body_focus
            )
        
        # Estrai wardrobe dal world data
        world_wardrobe = {
            name: data.wardrobe
            for name, data in world_data.get("companions", {}).items()
        }
        
        # Costruisci blocchi per ogni personaggio
        char_blocks = []
        global_loras: Set[str] = set()
        hair_colors_used = []
        
        for i, name in enumerate(subjects):
            block = self._build_character_block(
                name=name,
                index=i,
                total=len(subjects),
                game_session=game_session,
                world_wardrobe=world_wardrobe,
                visual_en=visual_en,
                global_loras=global_loras,
                hair_colors_used=hair_colors_used
            )
            char_blocks.append(block)
        
        # Assembla prompt globale
        parts = []
        
        # 1. LoRA di stile globali (una sola volta)
        if global_loras:
            parts.append(" ".join(sorted(global_loras)))
        
        # 2. Quality base + realism boosters
        parts.append("score_9, score_8_up, masterpiece, photorealistic, realistic, real life, detailed skin, professional photography, 8k")
        
        # 3. Tag gruppo
        parts.append(f"{len(subjects)}girls")
        
        # 4. Differenziazione esplicita
        diff_tags = self._build_differentiation_tags(subjects, hair_colors_used)
        if diff_tags:
            parts.append(", ".join(diff_tags))
        
        # 5. Blocchi personaggi separati da BREAK
        parts.append(" BREAK ".join(char_blocks))
        
        # 6. Context globale
        if visual_en:
            parts.append(visual_en)  # NO WEIGHT
        
        # Tags puliti
        banned = ["best quality", "best_quality", "masterpiece", "score_9", "1girl", "2girls", "3girls", 
                  "photorealistic", "detailed", "ultra_detailed"]
        clean_tags = [t for t in tags_en if t.lower() not in banned]
        if clean_tags:
            parts.append(", ".join(clean_tags))
        
        # Body focus per scene multi (applica a tutti i personaggi visibili)
        if body_focus:
            if body_focus in ["legs", "feet", "lower_body"]:
                parts.append("cowboy_shot, lower_body, legs_visible")
            elif body_focus in ["chest", "breasts", "torso"]:
                parts.append("medium_shot, upper_body, torso_focus")
            elif body_focus in ["face", "expression"]:
                parts.append("portrait, face_focus")
            elif body_focus in ["back", "behind"]:
                parts.append("from_behind, back_focus")
        
        # Location
        if game_session.location:
            parts.append(f"background is {game_session.location}")
        
        positive = " ".join([p.strip() for p in parts if p])
        
        # Negative avanzato anti-fusion
        negative = f"{NEGATIVE_BASE}, {ANTI_FUSION_NEGATIVE}"
        
        # Aggiungi negative specifico per i colori dei capelli
        hair_negative = self._build_hair_negative(subjects)
        if hair_negative:
            negative += f", {hair_negative}"
        
        return PromptResult(
            positive=positive,
            negative=negative,
            width=1024,  # Più largo per scene multi
            height=1152
        )
    
    def _build_character_block(
        self,
        name: str,
        index: int,
        total: int,
        game_session: GameSession,
        world_wardrobe: Dict,
        visual_en: str,
        global_loras: Set[str],
        hair_colors_used: List[str]
    ) -> str:
        """Costruisce il blocco per un singolo personaggio."""
        
        # Base prompt
        base_raw = BASE_PROMPTS.get(name, NPC_BASE)
        base_clean, style_loras = extract_style_loras(clean_base_prompt(base_raw, is_multi=True))
        
        # Accumula LoRA di stile
        for lora in style_loras:
            global_loras.add(lora)
        
        # Outfit
        if name == game_session.companion_name:
            outfit_key = game_session.current_outfit
        else:
            npc_state = game_session.npc_states.get(name, {})
            outfit_key = npc_state.get("current_outfit", "default")
        
        outfit_str = get_outfit_for_character(
            name, outfit_key, world_wardrobe, visual_en
        )
        
        # Posizionamento per evitare sovrapposizioni
        if total == 2:
            position = "left side" if index == 0 else "right side"
        elif total >= 3:
            positions = ["left", "center", "right"]
            position = positions[index % 3]
        else:
            position = ""
        
        # Hair color enforcement
        hair_color = self.HAIR_COLORS.get(name, "")
        if hair_color:
            hair_colors_used.append(hair_color)
            hair_tag = hair_color  # NO WEIGHT
        else:
            hair_tag = ""
        
        # Assembla blocco
        parts = [name]  # NO WEIGHT
        if hair_tag:
            parts.append(hair_tag)
        parts.append(base_clean)
        parts.append(outfit_str)
        if position:
            parts.append(f"({position})")
        
        return ", ".join([p for p in parts if p])
    
    def _build_differentiation_tags(self, subjects: List[str], hair_colors: List[str]) -> List[str]:
        """Costruisce tag che forzano la differenziazione."""
        tags = []
        
        # Forza diversità capelli
        if len(subjects) == 2 and len(hair_colors) == 2:
            tags.append(f"{hair_colors[0]} and {hair_colors[1]}")
        
        # Tag generici anti-fusion
        tags.extend([
            "distinct individuals",
            "separate figures",
            "different poses"
        ])
        
        # Specifici per il numero
        if len(subjects) == 2:
            tags.extend(["duo", "two distinct women"])
        elif len(subjects) == 3:
            tags.extend(["trio", "three distinct women"])
        
        return tags
    
    def _build_hair_negative(self, subjects: List[str]) -> str:
        """Costruisce negative per prevenire stessi colori capelli."""
        if len(subjects) < 2:
            return ""
        
        # Se abbiamo Luna (brown) e Stella (blonde), aggiungi negative
        # per prevenire che entrambe abbiano lo stesso colore
        negatives = []
        
        if "Luna" in subjects and "Stella" in subjects:
            negatives.extend([
                "both blonde", "both brown hair",
                "same hair color", "uniform hair"
            ])
        
        if "Maria" in subjects:
            negatives.extend([
                "all black hair", "all same hair"
            ])
        
        return ", ".join(negatives)
