"""Pydantic models for type-safe data handling."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class CompositionType(str, Enum):
    """Tipi di inquadratura fotografica."""
    CLOSE_UP = "close_up"           # Primo piano
    MEDIUM_SHOT = "medium_shot"     # Plano medio
    WIDE_SHOT = "wide_shot"         # Campo lungo
    GROUP = "group"                 # Gruppo
    SCENE = "scene"                 # Scena ambientale


class SceneAnalysis(BaseModel):
    """Risultato analisi semantica della scena da parte dell'LLM."""
    model_config = ConfigDict(strict=True)
    
    primary_subject: Optional[str] = Field(
        None, 
        description="Personaggio principale in focus, null se gruppo"
    )
    secondary_subjects: List[str] = Field(
        default_factory=list,
        description="Personaggi visivamente presenti ma non focus"
    )
    background_mentions: List[str] = Field(
        default_factory=list, 
        description="Personaggi nominati ma non nella scena visiva"
    )
    composition_type: CompositionType = Field(
        default=CompositionType.MEDIUM_SHOT
    )
    action_focus: str = Field(
        default="",
        description="Azione principale descritta"
    )
    frame_type: Literal["close_up", "medium_shot", "wide_shot", "group"] = Field(
        default="medium_shot"
    )
    reasoning: str = Field(
        default="",
        description="Spiegazione della scelta"
    )
    
    def get_all_present_subjects(self) -> List[str]:
        """Restituisce tutti i personaggi visivamente presenti."""
        subjects = []
        if self.primary_subject:
            subjects.append(self.primary_subject)
        subjects.extend(self.secondary_subjects)
        return subjects
    
    @property
    def is_multi_character(self) -> bool:
        """True se ci sono 2+ personaggi visivamente presenti."""
        return len(self.get_all_present_subjects()) >= 2


class OutfitData(BaseModel):
    """Dati di un outfit nel wardrobe."""
    name: str
    description: str


class PersonalityTier(BaseModel):
    """Tier di personalità basato su affinità."""
    threshold: int = Field(ge=0, le=100)
    description: str


class CompanionConfig(BaseModel):
    """Configurazione di un companion dallo YAML."""
    name: str
    base_prompt: str  # LoRA e trigger words specifici
    default_outfit: str
    wardrobe: Dict[str, str]
    personality_tiers: List[PersonalityTier]


class NPCLogic(BaseModel):
    """Logica per riconoscimento NPC generici."""
    female_hints: List[str] = Field(default_factory=list)
    male_hints: List[str] = Field(default_factory=list)
    female_prompt: Optional[str] = None
    male_prompt: Optional[str] = None


class WorldMeta(BaseModel):
    """Metadati di un mondo."""
    id: str
    name: str
    genre: str
    world_lore: str
    story_structure: Dict[str, Any] = Field(default_factory=dict)


class WorldConfig(BaseModel):
    """Configurazione completa di un mondo."""
    meta: WorldMeta
    companions: Dict[str, CompanionConfig]
    npc_logic: NPCLogic
    visual_style: Optional[Dict[str, Any]] = None


class GameStateUpdate(BaseModel):
    """Aggiornamenti stato inviati dall'LLM."""
    location: Optional[str] = None
    current_outfit: Optional[str] = None
    time_of_day: Optional[str] = None
    gold: Optional[int] = None
    hp: Optional[int] = None
    add_item: Optional[str] = None
    remove_item: Optional[str] = None
    flags: Dict[str, Any] = Field(default_factory=dict)
    affinity_change: Dict[str, int] = Field(default_factory=dict)
    npc_updates: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    new_fact: Optional[str] = None
    stat_changes: Dict[str, int] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Risposta strutturata dall'LLM."""
    text: str = Field(description="Testo narrativo in italiano")
    visual_en: Optional[str] = Field(default="", description="Descrizione scena per SD")
    tags_en: List[str] = Field(default_factory=list, description="Tag tecnici SD")
    body_focus: Optional[str] = Field(default=None, description="Parte del corpo in focus (es: legs, face, torso)")
    approach_used: Optional[str] = Field(default="standard", description="Approccio usato: standard, physical_action, question, choice")
    updates: GameStateUpdate = Field(default_factory=GameStateUpdate)


class MemoryEntry(BaseModel):
    """Entrata di memoria (riassunto o fatto)."""
    id: Optional[int] = None
    type: Literal["summary", "fact", "event"] = "fact"
    content: str
    turn_count: int
    created_at: Optional[datetime] = None
    importance: int = Field(default=5, ge=1, le=10)


class GameSession(BaseModel):
    """Sessione di gioco completa."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    world_id: str
    companion_name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    turn_count: int = 0
    
    # Stato corrente
    location: str = "Unknown"
    time_of_day: str = "Morning"
    current_outfit: str = "default"
    gold: int = 0
    hp: int = 20
    stats: Dict[str, int] = Field(default_factory=lambda: {
        "strength": 10, "mind": 10, "charisma": 10
    })
    
    # Relazioni
    affinity: Dict[str, int] = Field(default_factory=dict)
    npc_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # Progressione
    inventory: List[str] = Field(default_factory=list)
    quest_log: List[str] = Field(default_factory=list)
    flags: Dict[str, Any] = Field(default_factory=dict)
