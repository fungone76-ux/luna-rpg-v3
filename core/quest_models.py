"""Pydantic models for Quest System."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

from core.models import PersonalityTier


class QuestStatus(str, Enum):
    """Stati possibili di una quest."""
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestMeta(BaseModel):
    """Metadati di una quest."""
    title: str
    description: str
    type: Literal["main", "side"] = "side"
    character: Optional[str] = None
    required: bool = False
    priority: int = 50
    hidden: bool = False
    final: bool = False


class Condition(BaseModel):
    """Condizione per attivazione o transizione."""
    type: Literal["affinity", "location", "time", "flag", "turn_count", "inventory", "action"]
    target: Optional[str] = None  # Per affinity: nome character; per flag: nome flag
    operator: Literal["eq", "gt", "lt", "gte", "lte", "contains"] = "eq"
    value: Any = None
    pattern: Optional[str] = None  # Per type: action (regex)


class QuestAction(BaseModel):
    """Azione da eseguire (on_enter, rewards, etc)."""
    action: Literal[
        "set_location", "set_outfit", "set_flag", "add_flag", "add_item", "remove_item",
        "change_affinity", "spawn_npc", "despawn_npc", "unlock_exit", "lock_exit",
        "set_emotional_state", "increment_stat", "set_time", "check_harem_viability",
        "unlock_achievement", "trigger_jealousy_event", "set_outfit_modifier"
    ]
    # Parametri opzionali dipendenti dall'azione
    target: Optional[str] = None
    character: Optional[str] = None
    outfit: Optional[str] = None
    key: Optional[str] = None
    value: Any = None
    stat: Optional[str] = None
    achievement: Optional[str] = None
    effect: Optional[str] = None


class Transition(BaseModel):
    """Transizione tra stage."""
    condition: Optional[str] = None  # "condition_0", "condition_1", "default", "_complete", "_fail"
    target_stage: Optional[str] = None
    fallback: Optional[str] = None  # Per harem_check fallback
    target: Optional[str] = None  # Shortcut per "_complete" o "_fail"


class QuestStage(BaseModel):
    """Singolo stage di una quest."""
    title: str
    narrative_prompt: str
    on_enter: List[QuestAction] = Field(default_factory=list)
    exit_conditions: List[Condition] = Field(default_factory=list)
    transitions: List[Transition] = Field(default_factory=list)


class QuestActivation(BaseModel):
    """Come si attiva una quest."""
    type: Literal["manual", "auto", "random", "trigger"]
    chance: Optional[float] = None  # Per random (0.0-1.0)
    trigger_event: Optional[str] = None
    conditions: List[Condition] = Field(default_factory=list)


class QuestRewards(BaseModel):
    """Ricompense quest."""
    affinity: Dict[str, int] = Field(default_factory=dict)
    items: List[str] = Field(default_factory=list)
    flags: Dict[str, Any] = Field(default_factory=dict)
    unlock_quests: List[str] = Field(default_factory=list)


class QuestDefinition(BaseModel):
    """Definizione completa di una quest dal YAML."""
    meta: QuestMeta
    activation: QuestActivation
    stages: Dict[str, QuestStage]
    rewards: Optional[QuestRewards] = None


class QuestState(BaseModel):
    """Stato runtime di una quest (da salvare nel DB)."""
    quest_id: str
    status: QuestStatus = QuestStatus.NOT_STARTED
    current_stage_id: Optional[str] = None
    stage_data: Dict[str, Any] = Field(default_factory=dict)  # Dati persistenti per stage
    started_at: int = 0  # turn_count
    completed_at: Optional[int] = None
    
    def is_completed(self) -> bool:
        return self.status == QuestStatus.COMPLETED
    
    def is_active(self) -> bool:
        return self.status == QuestStatus.ACTIVE


class EmotionalState(BaseModel):
    """Stato emotivo di una companion."""
    description: str
    dialogue_tone: str
    approach: str
    trigger_flags: List[str] = Field(default_factory=list)


class AffinityTier(BaseModel):
    """Tier di affinità nel personality_system."""
    tier_name: str
    description: str
    available_actions: List[str] = Field(default_factory=list)
    locked_actions: List[str] = Field(default_factory=list)
    unlock_outfits: List[str] = Field(default_factory=list)


class PersonalitySystem(BaseModel):
    """Sistema personality dinamico (dal nuovo YAML)."""
    core_traits: Dict[str, str] = Field(default_factory=dict)
    emotional_states: Dict[str, EmotionalState] = Field(default_factory=dict)
    affinity_tiers: Dict[str, AffinityTier] = Field(default_factory=dict)
    relationship: Dict[str, Any] = Field(default_factory=dict)


class CompanionV3Config(BaseModel):
    """Configurazione companion con personality_system (esteso)."""
    name: str
    base_prompt: str
    default_outfit: str
    wardrobe: Dict[str, str]
    personality_system: Optional[PersonalitySystem] = None
    # Per backward compatibility
    personality_tiers: List[PersonalityTier] = Field(default_factory=list)
    relationship: Dict[str, Any] = Field(default_factory=dict)


class Milestone(BaseModel):
    """Milestone per una companion."""
    id: str
    name: str
    condition: Dict[str, Any]  # affinity: X, flag: "..."
    icon: str


class EndgameConfig(BaseModel):
    """Configurazione endgame."""
    description: str
    victory_conditions: List[Dict[str, Any]]
    ui_indicators: Dict[str, str]


class GlobalEventEffect(BaseModel):
    """Effetto di un evento globale."""
    description: str
    actions: List[QuestAction] = Field(default_factory=list)
    duration: Optional[int] = None  # turni


class GlobalEvent(BaseModel):
    """Evento globale casuale."""
    meta: Dict[str, str]
    trigger: Dict[str, Any]
    effect: GlobalEventEffect
    on_expire: Optional[List[QuestAction]] = None
    special_conditions: Optional[List[Dict[str, Any]]] = None
    variants: Optional[List[Dict[str, Any]]] = None
    random_owner: Optional[bool] = None
    resolution: Optional[Dict[str, Any]] = None


class WorldConfigV3(BaseModel):
    """Configurazione mondo completa (versione 3 con quest)."""
    meta: Dict[str, Any]
    npc_logic: Dict[str, Any]
    companions: Dict[str, CompanionV3Config]
    quests: Optional[Dict[str, QuestDefinition]] = None
    global_events: Optional[Dict[str, GlobalEvent]] = None
    endgame: Optional[EndgameConfig] = None
    milestones: Optional[Dict[str, List[Milestone]]] = None
    visual_style: Optional[Dict[str, Any]] = None


# Ricostruisci i modelli che hanno forward references
CompanionV3Config.model_rebuild()
