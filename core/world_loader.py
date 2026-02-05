"""YAML World loader and validator - Version 3 with Quest System."""
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml

from core.prompt_builders.base import BASE_PROMPTS
from core.quest_models import (
    QuestDefinition, QuestMeta, QuestActivation, QuestStage, 
    QuestAction, Condition, Transition, QuestRewards,
    EmotionalState, AffinityTier, PersonalitySystem, CompanionV3Config
)


def _convert_companion_v2_to_v3(name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Converte formato companion v2/v3 (YAML) a dict processabile."""
    # Se ha personality_system, è già v3
    if "personality_system" in data:
        return _convert_companion_v3(name, data)
    
    # Altrimenti converti da v2
    tiers_raw = data.get("personality_tiers", {})
    personality_tiers = []
    if isinstance(tiers_raw, dict):
        for threshold, description in tiers_raw.items():
            personality_tiers.append({
                "threshold": int(threshold),
                "description": description
            })
    else:
        personality_tiers = tiers_raw
    
    base_prompt = BASE_PROMPTS.get(name, BASE_PROMPTS.get("Luna", ""))
    
    return {
        "name": name,
        "base_prompt": base_prompt,
        "default_outfit": data.get("default_outfit", "default"),
        "wardrobe": data.get("wardrobe", {}),
        "personality_tiers": personality_tiers,
        "personality_system": None,
        "relationship": data.get("relationship", {})
    }


def _convert_companion_v3(name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa companion formato v3 con personality_system."""
    psys_data = data.get("personality_system", {})
    
    # Converti emotional_states
    emotional_states = {}
    for state_name, state_data in psys_data.get("emotional_states", {}).items():
        emotional_states[state_name] = EmotionalState(**state_data)
    
    # Converti affinity_tiers (chiave è stringa "0", "25", etc)
    affinity_tiers = {}
    for tier_key, tier_data in psys_data.get("affinity_tiers", {}).items():
        str_key = str(tier_key)
        affinity_tiers[str_key] = AffinityTier(**tier_data)
    
    personality_system = PersonalitySystem(
        core_traits=psys_data.get("core_traits", {}),
        emotional_states=emotional_states,
        affinity_tiers=affinity_tiers,
        relationship=psys_data.get("relationship", {})
    )
    
    return {
        "name": name,
        "base_prompt": data.get("base_prompt", BASE_PROMPTS.get(name, "")),
        "default_outfit": data.get("default_outfit", "default"),
        "wardrobe": data.get("wardrobe", {}),
        "personality_system": personality_system,
        "personality_tiers": [],  # Non usato in v3
        "relationship": psys_data.get("relationship", {})
    }


def _convert_quest(quest_id: str, data: Dict[str, Any]) -> QuestDefinition:
    """Converte una quest dal YAML a QuestDefinition."""
    # Meta
    meta = QuestMeta(**data.get("meta", {}))
    
    # Activation
    activation_data = data.get("activation", {"type": "manual"})
    activation = QuestActivation(**activation_data)
    
    # Stages
    stages = {}
    for stage_id, stage_data in data.get("stages", {}).items():
        # On enter actions
        on_enter = [QuestAction(**a) for a in stage_data.get("on_enter", [])]
        
        # Exit conditions
        exit_conditions = [Condition(**c) for c in stage_data.get("exit_conditions", [])]
        
        # Transitions
        transitions = []
        for t in stage_data.get("transitions", []):
            # Supporta sia "target_stage" che "target" (shortcut)
            if "target" in t and "target_stage" not in t:
                t["target_stage"] = t.pop("target")
            transitions.append(Transition(**t))
        
        stages[stage_id] = QuestStage(
            title=stage_data.get("title", ""),
            narrative_prompt=stage_data.get("narrative_prompt", ""),
            on_enter=on_enter,
            exit_conditions=exit_conditions,
            transitions=transitions
        )
    
    # Rewards (opzionale)
    rewards = None
    if "rewards" in data:
        rewards_data = data["rewards"]
        # Handle affinity con placeholder come "{companion}"
        affinity = rewards_data.get("affinity", {})
        rewards = QuestRewards(
            affinity=affinity,
            items=rewards_data.get("items", []),
            flags=rewards_data.get("flags", {}),
            unlock_quests=rewards_data.get("unlock_quests", [])
        )
    
    return QuestDefinition(
        meta=meta,
        activation=activation,
        stages=stages,
        rewards=rewards
    )


class WorldLoader:
    """Carica e valida mondi da file YAML - Version 3."""
    
    def __init__(self, worlds_dir: str = "worlds"):
        self.worlds_path = Path(worlds_dir)
    
    def list_worlds(self) -> List[Dict[str, str]]:
        """Elenca mondi disponibili."""
        results = []
        
        if not self.worlds_path.exists():
            return []
        
        for file in self.worlds_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(file.read_text(encoding="utf-8"))
                meta = data.get("meta", {})
                results.append({
                    "id": meta.get("id", file.stem),
                    "name": meta.get("name", file.stem),
                    "genre": meta.get("genre", "Unknown"),
                    "filename": file.name,
                    "version": meta.get("version", "unknown")
                })
            except Exception as e:
                print(f"[!] Error loading {file}: {e}")
        
        return results
    
    def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """Carica un mondo specifico con supporto Quest System v3."""
        if not world_id.endswith(".yaml"):
            filename = f"{world_id}.yaml"
        else:
            filename = world_id
        
        filepath = self.worlds_path / filename
        
        if not filepath.exists():
            print(f"[ERR] World not found: {filepath}")
            return None
        
        try:
            data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            
            # Validazione base
            if "meta" not in data:
                print(f"[!] World {filename} missing 'meta' section")
                return None
            
            if "companions" not in data:
                print(f"[!] World {filename} missing 'companions' section")
                return None
            
            # Converti companions
            raw_companions = data.get("companions", {})
            converted_companions = {}
            for name, companion_data in raw_companions.items():
                converted = _convert_companion_v2_to_v3(name, companion_data)
                converted_companions[name] = CompanionV3Config(**converted)
            data["companions"] = converted_companions
            
            # Converti quests (NUOVO)
            if "quests" in data:
                raw_quests = data["quests"]
                converted_quests = {}
                for quest_id, quest_data in raw_quests.items():
                    try:
                        converted_quests[quest_id] = _convert_quest(quest_id, quest_data)
                    except Exception as e:
                        print(f"[!] Error converting quest '{quest_id}': {e}")
                data["quests"] = converted_quests
                print(f"[WorldLoader] Loaded {len(converted_quests)} quests")
            
            # Converti milestones (NUOVO)
            if "milestones" in data:
                from core.quest_models import Milestone
                milestones = {}
                for char_name, milestone_list in data["milestones"].items():
                    milestones[char_name] = [Milestone(**m) for m in milestone_list]
                data["milestones"] = milestones
            
            # Converti endgame (NUOVO)
            if "endgame" in data:
                from core.quest_models import EndgameConfig
                data["endgame"] = EndgameConfig(**data["endgame"])
            
            # Converti global_events (NUOVO)
            if "global_events" in data:
                from core.quest_models import GlobalEvent
                events = {}
                for event_id, event_data in data["global_events"].items():
                    events[event_id] = GlobalEvent(**event_data)
                data["global_events"] = events
            
            # Campi opzionali default
            if "npc_logic" not in data:
                data["npc_logic"] = {}
            if "visual_style" not in data:
                data["visual_style"] = {}
            
            print(f"[WorldLoader] World '{data['meta'].get('name', filename)}' loaded successfully")
            return data
            
        except Exception as e:
            print(f"[ERR] Error loading world {filename}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_companion_config(self, world_id: str, companion_name: str) -> Optional[CompanionV3Config]:
        """Ottiene config di un companion specifico."""
        world = self.load_world(world_id)
        if not world:
            return None
        
        return world.get("companions", {}).get(companion_name)
    
    def get_quest(self, world_id: str, quest_id: str) -> Optional[QuestDefinition]:
        """Ottiene una quest specifica dal mondo."""
        world = self.load_world(world_id)
        if not world:
            return None
        
        return world.get("quests", {}).get(quest_id)
    
    def validate_world(self, world_id: str) -> List[str]:
        """Valida un mondo e ritorna lista errori."""
        errors = []
        world = self.load_world(world_id)
        
        if not world:
            return ["World not found or failed to load"]
        
        # Validazione quests
        quests = world.get("quests", {})
        for quest_id, quest in quests.items():
            # Check che ci sia uno stage 'start' o simile
            if "start" not in quest.stages and len(quest.stages) > 0:
                first_stage = list(quest.stages.keys())[0]
                if quest.meta.required:
                    errors.append(f"Quest '{quest_id}': recommended to have 'start' stage")
            
            # Check transizioni
            for stage_id, stage in quest.stages.items():
                for trans in stage.transitions:
                    target = trans.target_stage
                    if target and target not in ["_complete", "_fail"]:
                        if target not in quest.stages:
                            errors.append(f"Quest '{quest_id}'.stage '{stage_id}': transition to unknown stage '{target}'")
        
        # Validazione companions
        companions = world.get("companions", {})
        for char_name, char in companions.items():
            if char.personality_system:
                ps = char.personality_system
                if not ps.emotional_states:
                    errors.append(f"Companion '{char_name}': no emotional_states defined")
                if not ps.affinity_tiers:
                    errors.append(f"Companion '{char_name}': no affinity_tiers defined")
        
        return errors
