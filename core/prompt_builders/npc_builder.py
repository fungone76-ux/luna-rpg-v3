"""Builder per NPC generici (non companion principali)."""
from typing import Dict, List

from core.models import GameSession
from core.prompt_builders.base import (
    PromptResult, NPC_BASE, NPC_MALE_BASE, NEGATIVE_BASE,
    clean_base_prompt
)


class NPCBuilder:
    """Costruisce prompt per NPC generici identificati da keyword."""
    
    NPC_NEGATIVE = (
        "score_5, score_4, low quality, bad anatomy, worst face, "
        "extra fingers, cartoon, 3d render, text, watermark, "
        "familiar face, known character, main character"
    )
    
    def build(
        self,
        npc_type: str,
        visual_en: str,
        tags_en: List[str],
        game_session: GameSession,
        world_data: Dict
    ) -> PromptResult:
        """Costruisce prompt per un NPC.
        
        Args:
            npc_type: Keyword identificativa (es. "nurse", "orc", "maid")
            visual_en: Descrizione visiva
            tags_en: Tag tecnici
            game_session: Stato gioco
            world_data: Dati mondo con npc_logic
        """
        # Determina genere dai hint del world
        npc_logic = world_data.get("npc_logic", {})
        female_hints = [h.lower() for h in npc_logic.get("female_hints", [])]
        
        is_female = npc_type.lower() in female_hints
        
        # Seleziona base
        if is_female:
            base = NPC_BASE
            gender_tag = "1girl"
        else:
            base = NPC_MALE_BASE
            gender_tag = "1boy"
        
        # Inietta il tipo specifico
        base_clean = clean_base_prompt(base, is_multi=False)
        final_base = f"({npc_type}:1.2), {base_clean}"
        
        # Assembla
        parts = [final_base]
        
        # Aggiungi gender tag se non presente
        if gender_tag not in final_base.lower():
            parts.insert(0, gender_tag)
        
        # Tags puliti
        banned = ["best quality", "masterpiece", "score_9", "1girl", "1boy", "photorealistic"]
        clean_tags = [t for t in tags_en if t.lower() not in banned]
        
        if clean_tags:
            parts.append(", ".join(clean_tags))
        
        if visual_en:
            # Rimuovi nomi dei companion main dal visual NPC
            visual_clean = visual_en
            for companion in world_data.get("companions", {}).keys():
                visual_clean = visual_clean.replace(companion, "woman" if is_female else "man")
            parts.append(f"({visual_clean}:1.1)")
        
        # Location
        if game_session.location:
            parts.append(f"background is {game_session.location}")
        
        positive = ", ".join([p.strip().strip(",") for p in parts if p])
        
        return PromptResult(
            positive=positive,
            negative=self.NPC_NEGATIVE,
            width=896,
            height=1152
        )
