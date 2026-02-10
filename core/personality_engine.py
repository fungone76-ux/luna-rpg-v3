"""Personality Engine v2 - Dynamic Character Psychology.

Tracks player behavior patterns and character perceptions over time.
All outputs to LLM are in English for better model performance.
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class TraitIntensity(str, Enum):
    """Intensity levels of behavioral traits."""
    SUBTLE = "subtle"      # Barely noticeable
    MODERATE = "moderate"  # Evident
    STRONG = "strong"      # Dominant


@dataclass
class NPCToNPCRelation:
    """Relationship between two NPCs (gossip/jealousy system)."""
    target_npc: str
    rapport: int = 0         # -100 (hatred) to 100 (best friends)
    jealousy_sensitivity: float = 0.5  # 0-1, how much they care about player
    awareness_of_player: int = 0  # How much they know about player's activities


class PowerDynamic(str, Enum):
    """Who holds power in the relationship."""
    PLAYER_DOMINANT = "player_leads"
    EQUAL = "balanced"
    NPC_DOMINANT = "npc_leads"


@dataclass
class BehavioralMemory:
    """Memory of how the player has behaved toward this character."""
    trait: str                    # "aggressive", "shy", "romantic", "dominant"
    occurrences: int = 0
    last_turn: int = 0
    intensity: TraitIntensity = TraitIntensity.SUBTLE
    
    def update(self, turn: int):
        """Update memory with new occurrence."""
        self.occurrences += 1
        self.last_turn = turn
        if self.occurrences > 5:
            self.intensity = TraitIntensity.STRONG
        elif self.occurrences > 2:
            self.intensity = TraitIntensity.MODERATE


@dataclass 
class Impression:
    """Dynamic impression metrics for a relationship."""
    trust: int = 0           # -100 to 100
    attraction: int = 0      # -100 to 100  
    fear: int = 0            # -100 to 100
    curiosity: int = 50      # -100 to 100
    dominance_balance: int = 0  # -100 (player leads) to 100 (NPC leads)
    
    def get_dominant_emotion(self) -> str:
        """Return the dominant emotional impression."""
        values = {
            "trust": self.trust,
            "attraction": self.attraction,
            "fear": self.fear,
            "curiosity": self.curiosity
        }
        return max(values, key=values.get)


class PersonalityEngine:
    """
    Manages dynamic character psychology and player perception.
    All string outputs intended for LLM consumption are in English.
    """
    
    # Behavior patterns to detect in player input
    BEHAVIOR_PATTERNS = {
        "aggressive": [
            "take", "grab", "push", "force", "order", "command",
            "prendi", "spingi", "ordina", "sforza", "afferra"
        ],
        "shy": [
            "shy", "blush", "nervous", "timid", "embarrassed", "look away",
            "timido", "rossore", "scusa", "imbarazzo", "nervoso"
        ],
        "romantic": [
            "love", "heart", "kiss", "sweet", "gentle", "caress",
            "amore", "cuore", "bacio", "dolce", "carezza", "amorevole"
        ],
        "dominant": [
            "kneel", "obey", "submit", "silence", "enough", "stop",
            "inginocchiati", "obbedisci", "smetti", "silenzio", "basta"
        ],
        "submissive": [
            "please", "beg", "sorry", "you decide", "as you wish",
            "per favore", "ti prego", "scusa", "decidi tu", "come vuoi"
        ],
        "curious": [
            "why", "how", "tell me", "explain", "what",
            "perché", "come", "dimmi", "parlami", "spiegami"
        ],
        "teasing": [
            "tease", "play", "joke", "provoke", "mischief",
            "scherzo", "gioco", "provoco", "malizia", "stuzzico"
        ]
    }
    
    def __init__(self, world_data: Dict[str, Any], game_state: Any):
        self.world_data = world_data
        self.game_state = game_state
        
        # Initialize behavioral memory for each companion
        self.behavioral_memory: Dict[str, Dict[str, BehavioralMemory]] = {
            name: {} for name in world_data.get("companions", {}).keys()
        }
        
        # Dynamic impressions for each relationship
        self.impressions: Dict[str, Impression] = {
            name: Impression() for name in world_data.get("companions", {}).keys()
        }
        
        # NPC-to-NPC relationship matrix (jealousy/gossip system)
        self.npc_relations: Dict[str, List[NPCToNPCRelation]] = self._init_npc_relations()
        
        # Player archetype cache
        self._cached_archetype: Optional[str] = None
        self._cache_turn: int = -1
    
    def _init_npc_relations(self) -> Dict[str, List[NPCToNPCRelation]]:
        """Initialize relationship matrix between NPCs."""
        companions_dict = self.world_data.get("companions", {})
        companions = list(companions_dict.keys())
        relations = {}
        
        for c1 in companions:
            relations[c1] = []
            for c2 in companions:
                if c1 != c2:
                    # Load from YAML if defined, else default
                    config = companions_dict.get(c1)
                    rel_config = {}
                    
                    # Access Pydantic model attributes correctly
                    if config and config.personality_system and config.personality_system.relationship:
                        rel_config = config.personality_system.relationship.get(c2, {})
                    
                    relations[c1].append(NPCToNPCRelation(
                        target_npc=c2,
                        rapport=rel_config.get("initial_rapport", 0) if isinstance(rel_config, dict) else 0,
                        jealousy_sensitivity=rel_config.get("jealousy", 0.5) if isinstance(rel_config, dict) else 0.5,
                        awareness_of_player=0
                    ))
        return relations
    
    def analyze_player_action(self, companion: str, user_input: str, 
                             turn_count: int) -> Dict[str, Any]:
        """
        Analyze player input and update behavioral memory.
        Returns detected changes for logging.
        """
        input_lower = user_input.lower()
        changes = {}
        
        for trait, keywords in self.BEHAVIOR_PATTERNS.items():
            if any(kw in input_lower for kw in keywords):
                if trait not in self.behavioral_memory[companion]:
                    self.behavioral_memory[companion][trait] = BehavioralMemory(trait)
                
                self.behavioral_memory[companion][trait].update(turn_count)
                changes[trait] = self.behavioral_memory[companion][trait].intensity.value
                
                # Update dynamic impressions
                self._update_impressions_from_trait(companion, trait)
        
        return changes
    
    def _update_impressions_from_trait(self, companion: str, trait: str):
        """Update impression metrics based on detected trait."""
        imp = self.impressions[companion]
        
        trait_effects = {
            "aggressive": {"trust": -5, "fear": +10, "attraction": -2, "dominance": -10},
            "romantic": {"trust": +5, "attraction": +15, "dominance": -5},
            "shy": {"curiosity": +10, "dominance": +5, "attraction": +3},
            "dominant": {"dominance": -15, "fear": -5, "trust": -3},
            "submissive": {"dominance": +10, "trust": +3},
            "curious": {"curiosity": +5, "trust": +2},
            "teasing": {"attraction": +5, "trust": -2}
        }
        
        effects = trait_effects.get(trait, {})
        for metric, delta in effects.items():
            if metric == "dominance":
                imp.dominance_balance = max(-100, min(100, imp.dominance_balance + delta))
            else:
                current = getattr(imp, metric)
                setattr(imp, metric, max(-100, min(100, current + delta)))
    
    def update_npc_awareness(self, companion_spent_time: str, turn_count: int):
        """
        Update what other NPCs think about who player spends time with.
        Increases jealousy/awareness for other NPCs.
        Called when player spends a turn with a companion.
        """
        for other_npc, relations in self.npc_relations.items():
            if other_npc != companion_spent_time:
                for rel in relations:
                    if rel.target_npc == companion_spent_time:
                        # Increase awareness that player is spending time with someone else
                        rel.awareness_of_player = min(100, rel.awareness_of_player + 10)
                        # Decrease rapport due to jealousy
                        jealousy_penalty = int(5 * rel.jealousy_sensitivity)
                        rel.rapport = max(-100, rel.rapport - jealousy_penalty)
    
    def get_jealousy_impact(self, companion: str) -> Dict[str, Any]:
        """
        Calculate gameplay impact of jealousy for a companion.
        Returns modifiers to apply to affinity changes.
        """
        impacts = {
            "affinity_modifier": 0,
            "emotional_override": None,
            "warning_message": None
        }
        
        # Check if this companion is jealous of others
        total_awareness = 0
        for rel in self.npc_relations.get(companion, []):
            if rel.awareness_of_player > 30:
                total_awareness += rel.awareness_of_player
                
        if total_awareness > 50:
            # High awareness = jealous behavior
            impacts["affinity_modifier"] = -2  # Harder to gain affinity
            impacts["emotional_override"] = "jealous"
            impacts["warning_message"] = f"{companion} seems distant... she knows you've been with others."
        elif total_awareness > 20:
            # Moderate awareness = suspicious
            impacts["affinity_modifier"] = -1
            impacts["emotional_override"] = "suspicious"
        
        return impacts
    
    def get_power_dynamic(self, companion: str) -> PowerDynamic:
        """Determine who leads in this relationship."""
        dom = self.impressions[companion].dominance_balance
        if dom < -30:
            return PowerDynamic.PLAYER_DOMINANT
        elif dom > 30:
            return PowerDynamic.NPC_DOMINANT
        return PowerDynamic.EQUAL
    
    def calculate_player_archetype(self, turn_count: int) -> str:
        """
        Calculate emergent player archetype from behavior patterns.
        Cached per turn for performance.
        """
        if self._cache_turn == turn_count and self._cached_archetype:
            return self._cached_archetype
        
        # Aggregate behaviors across all companions
        totals = {"aggressive": 0, "romantic": 0, "shy": 0, 
                 "dominant": 0, "curious": 0, "teasing": 0}
        
        for companion_memories in self.behavioral_memory.values():
            for trait, mem in companion_memories.items():
                if trait in totals:
                    totals[trait] += mem.occurrences
        
        # Determine archetype
        max_trait = max(totals, key=totals.get)
        total_actions = sum(totals.values())
        
        if total_actions < 3:
            archetype = "The Observer (undefined)"
        elif totals["aggressive"] > totals["romantic"] and totals["aggressive"] > 3:
            archetype = "The Dominant (prefers control and assertion)"
        elif totals["romantic"] > totals["aggressive"]:
            archetype = "The Romantic (prefers seduction and emotional connection)"
        elif totals["shy"] > 2:
            archetype = "The Shy Strategist (indirect, observant approach)"
        elif totals["dominant"] > 2:
            archetype = "The Commander (expects obedience)"
        else:
            archetype = "The Balanced (adaptable approach)"
        
        self._cached_archetype = archetype
        self._cache_turn = turn_count
        return archetype
    
    def get_gossip_context(self, companion: str) -> str:
        """Generate context about what this NPC knows of others (jealousy awareness)."""
        # Guard clause: if game_state not available, return neutral
        if not self.game_state or not hasattr(self.game_state, 'affinity'):
            return "unaware of other relationships"
        
        awareness = []
        
        for rel in self.npc_relations.get(companion, []):
            other = rel.target_npc
            # Check if player has high affinity with other
            other_affinity = self.game_state.affinity.get(other, 0)
            
            if rel.awareness_of_player > 50 and other_affinity > 40:
                awareness.append(
                    f"is very jealous of your relationship with {other}"
                )
            elif rel.awareness_of_player > 20 and other_affinity > 20:
                awareness.append(
                    f"is suspicious about your interest in {other}"
                )
            elif rel.awareness_of_player > 10:
                awareness.append(
                    f"has noticed you spending time with {other}"
                )
        
        return "; ".join(awareness) if awareness else "unaware of other relationships"
    
    def format_behavioral_memory(self, companion: str) -> str:
        """Format behavioral memory for LLM context (in English)."""
        memories = self.behavioral_memory[companion]
        if not memories:
            return "Still learning who you are"
        
        active_traits = []
        for trait, mem in memories.items():
            if mem.intensity == TraitIntensity.STRONG:
                active_traits.append(f"very {trait}")
            elif mem.intensity == TraitIntensity.MODERATE:
                active_traits.append(f"somewhat {trait}")
        
        if not active_traits:
            return "has not formed a strong opinion yet"
        
        return f"perceives you as: {', '.join(active_traits)}"
    
    def format_power_dynamic_description(self, companion: str) -> str:
        """Generate English description of power dynamic."""
        dynamic = self.get_power_dynamic(companion)
        
        descriptions = {
            PowerDynamic.PLAYER_DOMINANT: 
                "You are clearly in charge. She follows your lead and defers to you.",
            PowerDynamic.NPC_DOMINANT: 
                "She controls the situation. You find yourself obeying her implicitly.",
            PowerDynamic.EQUAL: 
                "Power is balanced between you, shifting based on context."
        }
        return descriptions[dynamic]
    
    def generate_system_prompt_context(self, companion: str, 
                                      base_affinity: int) -> str:
        """
        Generate complete personality context for LLM system prompt.
        All output in English.
        """
        imp = self.impressions[companion]
        archetype = self.calculate_player_archetype(
            self.game_state.turn_count
        )
        
        # Check jealousy impact
        jealousy = self.get_jealousy_impact(companion)
        
        lines = [
            f"=== CHARACTER PSYCHOLOGY: {companion.upper()} ===",
            "",
            "HOW SHE SEES YOU:",
            f"- Detected Archetype: {archetype}",
            f"- Behavioral Memory: {self.format_behavioral_memory(companion)}",
            f"- Trust Level: {imp.trust}/100",
            f"- Attraction Level: {imp.attraction}/100",
            f"- Fear Level: {imp.fear}/100",
            f"- Curiosity: {imp.curiosity}/100",
            "",
            f"POWER DYNAMIC: {self.format_power_dynamic_description(companion)}",
            "",
            f"SOCIAL AWARENESS: {self.get_gossip_context(companion)}",
            "",
            "=== BEHAVIORAL RULES ===",
            f"- Current Trust influences: {'openness' if imp.trust > 30 else 'caution' if imp.trust < -20 else 'neutral'}",
            f"- Current Attraction influences: {'flirtation' if imp.attraction > 40 else 'distance' if imp.attraction < 0 else 'friendship'}",
            f"- Power dynamic means: {'she submits to your lead' if imp.dominance_balance < -30 else 'she expects you to follow' if imp.dominance_balance > 30 else 'equal negotiation'}",
        ]
        
        # Add jealousy warning if applicable
        if jealousy["warning_message"]:
            lines.append(f"\n⚠️ JEALOUSY ALERT: {jealousy['warning_message']}")
            lines.append(f"→ Affinity gains reduced by {abs(jealousy['affinity_modifier'])} due to jealousy")
        
        return "\n".join(lines)
    
    def get_emotional_state_override(self, companion: str) -> Optional[str]:
        """
        Check if impressions should override default emotional state.
        Returns emotional state name or None.
        """
        imp = self.impressions[companion]
        
        # Check jealousy first (can override other states)
        jealousy = self.get_jealousy_impact(companion)
        if jealousy["emotional_override"]:
            return jealousy["emotional_override"]
        
        # High fear + low trust = defensive/hostile
        if imp.fear > 50 and imp.trust < -20:
            return "guarded"
        
        # High attraction + high trust = seductive
        if imp.attraction > 60 and imp.trust > 40:
            return "seductive"
        
        # Very high fear = submissive
        if imp.fear > 70:
            return "submissive"
        
        return None
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize per salvataggio JSON blob nel database.
        
        Versione compatta e flat per efficienza.
        """
        return {
            "impressions": {
                char: {
                    "trust": imp.trust,
                    "attraction": imp.attraction,
                    "fear": imp.fear,
                    "curiosity": imp.curiosity,
                    "dominance_balance": imp.dominance_balance
                }
                for char, imp in self.impressions.items()
            },
            "behavioral_memory": {
                char: {
                    trait: {
                        "occ": mem.occurrences,
                        "turn": mem.last_turn,
                        "int": mem.intensity.value
                    }
                    for trait, mem in traits.items()
                }
                for char, traits in self.behavioral_memory.items()
            },
            "npc_relations": {
                char: [
                    {
                        "t": rel.target_npc,
                        "r": rel.rapport,
                        "j": rel.jealousy_sensitivity,
                        "a": rel.awareness_of_player
                    }
                    for rel in rels
                ]
                for char, rels in self.npc_relations.items()
            },
            "cache": {
                "arch": self._cached_archetype,
                "turn": self._cache_turn
            }
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any], world_data: Dict, game_state: Any) -> "PersonalityEngine":
        """Deserialize da JSON blob database.
        
        Ricostruisce lo stato completo del PersonalityEngine.
        """
        engine = cls.__new__(cls)
        engine.world_data = world_data
        engine.game_state = game_state
        
        # Inizializza strutture vuote
        companions = list(world_data.get("companions", {}).keys())
        engine.behavioral_memory = {name: {} for name in companions}
        engine.impressions = {name: Impression() for name in companions}
        engine.npc_relations = engine._init_npc_relations()
        
        # Ripristina impressions
        for char, imp_data in data.get("impressions", {}).items():
            if char in engine.impressions:
                engine.impressions[char] = Impression(
                    trust=imp_data.get("trust", 0),
                    attraction=imp_data.get("attraction", 0),
                    fear=imp_data.get("fear", 0),
                    curiosity=imp_data.get("curiosity", 50),
                    dominance_balance=imp_data.get("dominance_balance", 0)
                )
        
        # Ripristina behavioral_memory
        for char, traits in data.get("behavioral_memory", {}).items():
            if char in engine.behavioral_memory:
                for trait_name, mem_data in traits.items():
                    # Supporta sia formato breve che lungo
                    occ = mem_data.get("occ") or mem_data.get("occurrences", 0)
                    turn = mem_data.get("turn") or mem_data.get("last_turn", 0)
                    int_val = mem_data.get("int") or mem_data.get("intensity", "subtle")
                    
                    engine.behavioral_memory[char][trait_name] = BehavioralMemory(
                        trait=trait_name,
                        occurrences=occ,
                        last_turn=turn,
                        intensity=TraitIntensity(int_val) if isinstance(int_val, str) else TraitIntensity.SUBTLE
                    )
        
        # Ripristina npc_relations
        for char, rels_data in data.get("npc_relations", {}).items():
            if char in engine.npc_relations:
                for rel_data in rels_data:
                    target = rel_data.get("t") or rel_data.get("target")
                    for rel in engine.npc_relations[char]:
                        if rel.target_npc == target:
                            rel.rapport = rel_data.get("r") or rel_data.get("rapport", 0)
                            rel.jealousy_sensitivity = rel_data.get("j") or rel_data.get("jealousy", 0.5)
                            rel.awareness_of_player = rel_data.get("a") or rel_data.get("awareness", 0)
                            break
        
        # Ripristina cache
        cache = data.get("cache", {})
        engine._cached_archetype = cache.get("arch") or data.get("archetype_cache")
        engine._cache_turn = cache.get("turn", -1) if isinstance(cache.get("turn"), int) else data.get("cache_turn", -1)
        
        return engine
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for database storage (legacy, usa serialize())."""
        return self.serialize()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], world_data: Dict, 
                  game_state: Any) -> "PersonalityEngine":
        """Deserialize from database."""
        engine = cls.__new__(cls)
        engine.world_data = world_data
        engine.game_state = game_state
        
        # Restore behavioral memory
        engine.behavioral_memory = {}
        for char, traits in data.get("behavioral_memory", {}).items():
            engine.behavioral_memory[char] = {}
            for trait_name, mem_data in traits.items():
                engine.behavioral_memory[char][trait_name] = BehavioralMemory(
                    trait=mem_data["trait"],
                    occurrences=mem_data["occurrences"],
                    last_turn=mem_data["last_turn"],
                    intensity=TraitIntensity(mem_data["intensity"])
                )
        
        # Restore impressions
        engine.impressions = {}
        for char, imp_data in data.get("impressions", {}).items():
            engine.impressions[char] = Impression(
                trust=imp_data["trust"],
                attraction=imp_data["attraction"],
                fear=imp_data["fear"],
                curiosity=imp_data["curiosity"],
                dominance_balance=imp_data["dominance_balance"]
            )
        
        # Re-init NPC relations structure from world_data
        engine.npc_relations = engine._init_npc_relations()
        # Restore saved values
        for char, rels_data in data.get("npc_relations", {}).items():
            for rel_data in rels_data:
                for rel in engine.npc_relations[char]:
                    if rel.target_npc == rel_data["target"]:
                        rel.rapport = rel_data.get("rapport", 0)
                        rel.jealousy_sensitivity = rel_data.get("jealousy", 0.5)
                        rel.awareness_of_player = rel_data.get("awareness", 0)
        
        engine._cached_archetype = None
        engine._cache_turn = -1
        
        return engine
