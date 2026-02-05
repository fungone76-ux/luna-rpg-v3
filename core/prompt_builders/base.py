"""Base classes and constants for prompt building."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PromptResult:
    """Risultato della costruzione del prompt."""
    positive: str
    negative: str
    width: int = 896
    height: int = 1152
    

# === BASE PROMPTS HARDCODATI (INVARIATI DALLA V2) ===
# Questi sono i prompt base specifici per ogni personaggio con le loro LoRA

BASE_PROMPTS = {
    "Luna": (
        "score_9, score_8_up, masterpiece, photorealistic, detailed, atmospheric, "
        "stsdebbie, dynamic pose, 1girl, mature woman, brown hair, shiny skin, head tilt, "
        "massive breasts, cleavage, "
        "<lora:stsDebbie-10e:0.7> <lora:Expressive_H-000001:0.20> <lora:FantasyWorldPonyV2:0.40>"
    ),
    "Stella": (
        "score_9, score_8_up, masterpiece, NSFW, photorealistic, 1girl, "
        "alice_milf_catchers, massive breasts, cleavage, blonde hair, beautiful blue eyes, "
        "shapely legs, hourglass figure, skinny body, narrow waist, wide hips, "
        "<lora:alice_milf_catchers_lora:0.7> <lora:Expressive_H:0.2>"
    ),
    "Maria": (
        "score_9, score_8_up, stsSmith, ultra-detailed, realistic lighting, 1girl, "
        "mature female, (middle eastern woman:1.5), veiny breasts, black hair, short hair, "
        "evil smile, glowing magic, "
        "<lora:stsSmith-10e:0.65> <lora:Expressive_H:0.2> <lora:FantasyWorldPonyV2:0.40>"
    )
}

# NPC base senza LoRA specifiche
NPC_BASE = (
    "score_9, score_8_up, masterpiece, photorealistic, 1girl, "
    "detailed face, cinematic lighting, 8k, realistic skin texture"
)

NPC_MALE_BASE = (
    "score_9, score_8_up, masterpiece, photorealistic, 1boy, "
    "male npc, detailed face, cinematic lighting, 8k"
)

# Negative prompts di base
NEGATIVE_BASE = (
    "score_5, score_4, low quality, worst quality, "
    "anime, manga, cartoon, 3d render, cgi, illustration, painting, drawing, sketch, "
    "monochrome, grayscale, "
    "deformed, bad anatomy, worst face, extra fingers, mutated, "
    "text, watermark, signature, logo, "
    "glasses, sunglasses, eyewear, spectacles, monocle, goggles, eyeglasses, "
    "blurry face, messy face, spotted face, blotched skin, skin blemishes, "
    "uneven eyes, crossed eyes, disfigured face, bad face"
)

# === ANTI-FUSION KEYWORDS ===
# Tag da aggiungere al negative per evitare fusioni in scene multi-personaggio

ANTI_FUSION_NEGATIVE = (
    "fused bodies, merged anatomy, conjoined twins, shared limbs, "
    "identical faces, same face, cloned appearance, mirror image, "
    "symmetrical poses, same pose, same angle, "
    "monochrome hair, uniform hairstyle, matching outfits, "
    "ambiguous identity, unclear which is which, blended silhouettes, "
    "overlapping bodies without depth, twin, clone, duplicate"
)

DIFFERENTIATION_BOOSTERS = [
    "different hair color",
    "different hair style", 
    "different outfits",
    "distinct faces",
    "separate bodies",
    "individual poses"
]


def remove_conflicting_footwear(outfit_desc: str, visual_context: str) -> str:
    """Rimuove scarpe se la scena richiede piedi nudi."""
    import re
    vis_lower = visual_context.lower()
    if any(k in vis_lower for k in ["barefoot", "feet", "toes", "foot worship", "soles", "scalza"]):
        clean = re.sub(
            r"\b(boots|shoes|sneakers|heels|loafers|footwear)\b", 
            "", outfit_desc, flags=re.IGNORECASE
        )
        return re.sub(r",\s*,", ",", clean).strip(" ,")
    return outfit_desc


def get_outfit_for_character(
    char_name: str,
    current_outfit_key: str,
    world_wardrobe: Dict[str, Dict[str, str]],
    visual_context: str = ""
) -> str:
    """Costruisce la stringa outfit per un personaggio."""
    wardrobe = world_wardrobe.get(char_name, {})
    outfit_desc = wardrobe.get(current_outfit_key, current_outfit_key)
    
    # Pulizia
    clean_desc = str(outfit_desc).lower().replace("wearing ", "")
    clean_desc = clean_desc.replace("(", "").replace(")", "").strip()
    
    # Fix scarpe
    clean_desc = remove_conflicting_footwear(clean_desc, visual_context)
    
    if "nude" in clean_desc or "naked" in clean_desc:
        return f"(nude:1.3), {clean_desc}"
    return f"(wearing {clean_desc}:1.3)"


def clean_base_prompt(base: str, is_multi: bool = False) -> str:
    """Pulisce il base prompt rimuovendo tag ridondanti."""
    import re
    # NON rimuoviamo piu' score_9, score_8_up, etc. - sono essenziali per Pony/Illustrious
    banned = []  # Vuoto - non rimuoviamo piu' nulla dai base prompt
    
    
    result = base
    
    # In multi-character, rimuovi SOLO 1girl/1boy (sostituiti con 2girls/3girls nel builder)
    if is_multi:
        for tag in ["1girl", "1boy"]:
            result = re.sub(f",?\\s*{re.escape(tag)},?", ",", result, flags=re.IGNORECASE)
        result = result.strip(", ")
    
    return result


def extract_style_loras(base_prompt: str) -> Tuple[str, List[str]]:
    """Estrae le LoRA di stile dal prompt base."""
    import re
    
    STYLE_KEYWORDS = ["FantasyWorldPony", "PonyV2", "Expressive", "Style", "Lighting", "Detail"]
    found_styles = []
    
    def replace_lora(match):
        lora_content = match.group(1)
        if any(k.lower() in lora_content.lower() for k in STYLE_KEYWORDS):
            found_styles.append(match.group(0))
            return ""  # Rimuovi dal testo base
        return match.group(0)
    
    cleaned = re.sub(r"<lora:([^:>]+)(?::[^>]+)?>", replace_lora, base_prompt)
    return cleaned.strip(", "), found_styles
