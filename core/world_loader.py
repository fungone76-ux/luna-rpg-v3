"""YAML World loader and validator - Version 4 with Modular Loading.

Supports both legacy single-file format and new modular folder format.
All world data is merged into a single structure in memory.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml

from core.prompt_builders.base import BASE_PROMPTS
from core.quest_models import (
    QuestDefinition, QuestMeta, QuestActivation, QuestStage, 
    QuestAction, Condition, Transition, QuestRewards,
    EmotionalState, AffinityTier, PersonalitySystem, CompanionV3Config,
    GlobalEvent, Milestone, EndgameConfig, PlayerCharacter
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
        # EXPERIMENTAL: wardrobe now supports both string (legacy) and dict with sd_prompt
        "wardrobe": data.get("wardrobe", {}),
        # NUOVO: Dialogue tone modulare per affinità
        "dialogue_tone": data.get("dialogue_tone", {}),
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
        """List available worlds (both legacy files and modular folders)."""
        results = []
        
        if not self.worlds_path.exists():
            return []
        
        # Legacy YAML files
        for file in self.worlds_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(file.read_text(encoding="utf-8"))
                meta = data.get("meta", {})
                results.append({
                    "id": meta.get("id", file.stem),
                    "name": meta.get("name", file.stem),
                    "genre": meta.get("genre", "Unknown"),
                    "filename": file.name,
                    "version": meta.get("version", "unknown"),
                    "format": "legacy"
                })
            except Exception as e:
                print(f"[!] Error loading {file}: {e}")
        
        # Modular folders
        for folder in self.worlds_path.iterdir():
            if folder.is_dir() and (folder / "_meta.yaml").exists():
                try:
                    meta_data = yaml.safe_load((folder / "_meta.yaml").read_text(encoding="utf-8"))
                    meta = meta_data.get("meta", {})
                    results.append({
                        "id": meta.get("id", folder.name),
                        "name": meta.get("name", folder.name),
                        "genre": meta.get("genre", "Unknown"),
                        "filename": folder.name,
                        "version": meta.get("version", "unknown"),
                        "format": "modular"
                    })
                except Exception as e:
                    print(f"[!] Error loading folder {folder}: {e}")
        
        return results
    
    def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """Load a world with support for both legacy and modular formats.
        
        Legacy: worlds/school_life.yaml (single file)
        Modular: worlds/school_life/*.yaml (folder with multiple files)
        """
        # NUOVO: Mapping da nomi legacy a cartelle modulari
        modular_mappings = {
            "school_life": "school_life_modular",
            # Aggiungi altri mapping se necessario
        }
        
        # Se il world_id è un nome legacy, usa la cartella modulare
        if world_id in modular_mappings:
            modular_id = modular_mappings[world_id]
            folder_path = self.worlds_path / modular_id
            if folder_path.exists() and folder_path.is_dir():
                print(f"[WorldLoader] Mapping '{world_id}' -> '{modular_id}'")
                return self._load_modular_world(folder_path, modular_id)
        
        # Check for modular folder first (con nome diretto)
        folder_path = self.worlds_path / world_id.replace(".yaml", "")
        if folder_path.exists() and folder_path.is_dir():
            print(f"[WorldLoader] Loading modular world: {world_id}")
            return self._load_modular_world(folder_path, world_id)
        
        # Fallback to legacy single file
        if not world_id.endswith(".yaml"):
            filename = f"{world_id}.yaml"
        else:
            filename = world_id
        
        filepath = self.worlds_path / filename
        
        if not filepath.exists():
            print(f"[ERR] World not found: {filepath}")
            return None
        
        return self._load_legacy_world(filepath, filename)
    
    def _load_modular_world(self, folder_path: Path, world_id: str) -> Optional[Dict[str, Any]]:
        """Load world from modular folder structure."""
        try:
            # Find all YAML files in folder
            yaml_files = list(folder_path.glob("*.yaml"))
            if not yaml_files:
                print(f"[ERR] No YAML files found in {folder_path}")
                return None
            
            # Start with empty structure
            merged_data = {
                "meta": {},
                "npc_logic": {},
                "companions": {},
                "quests": {},
                "milestones": {},
                "endgame": None,
                "global_events": {},
                "locations": {},
                "time": {},
                "player_character": None,
                "visual_style": {}
            }
            
            # Load _meta.yaml first if exists
            meta_file = folder_path / "_meta.yaml"
            if meta_file.exists():
                meta_data = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
                merged_data["meta"] = meta_data.get("meta", {})
                merged_data["npc_logic"] = meta_data.get("npc_logic", {})
                merged_data["player_character"] = meta_data.get("player_character")
                merged_data["endgame"] = meta_data.get("endgame")
                merged_data["visual_style"] = meta_data.get("visual_style", {})
                print(f"[WorldLoader] Loaded _meta.yaml")
            
            # Process all other files
            for yaml_file in yaml_files:
                if yaml_file.name == "_meta.yaml":
                    continue
                
                try:
                    file_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                    if not file_data:
                        continue
                    
                    # Merge companions (from individual character files)
                    if "companion" in file_data:
                        companion_data = file_data["companion"]
                        name = companion_data.get("name", yaml_file.stem)
                        merged_data["companions"][name] = companion_data
                        print(f"[WorldLoader] Loaded companion: {name}")
                    
                    # Merge multiple companions if present
                    if "companions" in file_data:
                        for name, data in file_data["companions"].items():
                            merged_data["companions"][name] = data
                            print(f"[WorldLoader] Loaded companion: {name}")
                    
                    # Merge quests
                    if "quests" in file_data:
                        merged_data["quests"].update(file_data["quests"])
                        print(f"[WorldLoader] Loaded {len(file_data['quests'])} quests from {yaml_file.name}")
                    
                    # Merge milestones (can be dict by character or list for single character)
                    if "milestones" in file_data:
                        milestones_data = file_data["milestones"]
                        if isinstance(milestones_data, dict):
                            # Dict format: {character_name: [milestones]}
                            for char_name, milestones in milestones_data.items():
                                if char_name not in merged_data["milestones"]:
                                    merged_data["milestones"][char_name] = []
                                merged_data["milestones"][char_name].extend(milestones)
                        elif isinstance(milestones_data, list):
                            # List format: milestones for the character in this file
                            # Get character name from companion section or filename
                            char_name = None
                            if "companion" in file_data:
                                char_name = file_data["companion"].get("name")
                            if not char_name:
                                char_name = yaml_file.stem.capitalize()
                            if char_name not in merged_data["milestones"]:
                                merged_data["milestones"][char_name] = []
                            merged_data["milestones"][char_name].extend(milestones_data)
                    
                    # Merge locations (supporta sia dict che lista)
                    if "locations" in file_data:
                        loc_data = file_data["locations"]
                        if isinstance(loc_data, list):
                            # Lista di location -> converti a dict by id
                            for loc in loc_data:
                                if isinstance(loc, dict) and "id" in loc:
                                    merged_data["locations"][loc["id"]] = loc
                            print(f"[WorldLoader] Loaded {len(loc_data)} locations from {yaml_file.name}")
                        elif isinstance(loc_data, dict):
                            # Già dict by id
                            merged_data["locations"].update(loc_data)
                            print(f"[WorldLoader] Loaded {len(loc_data)} locations from {yaml_file.name}")
                    
                    # Merge time cycle
                    if "time" in file_data:
                        merged_data["time"] = file_data["time"]
                    
                    # Merge global events
                    if "global_events" in file_data:
                        merged_data["global_events"].update(file_data["global_events"])
                    
                except Exception as e:
                    print(f"[!] Error loading {yaml_file.name}: {e}")
                    continue
            
            # Convert merged data to proper objects
            return self._process_world_data(merged_data, world_id)
            
        except Exception as e:
            print(f"[ERR] Error loading modular world {world_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _load_legacy_world(self, filepath: Path, filename: str) -> Optional[Dict[str, Any]]:
        """Load legacy single-file world format."""
        try:
            data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            return self._process_world_data(data, filename)
        except Exception as e:
            print(f"[ERR] Error loading legacy world {filename}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _process_world_data(self, data: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
        """Process raw world data into proper objects (used by both loaders)."""
        try:
            # Basic validation
            if "meta" not in data:
                print(f"[!] World {source_name} missing 'meta' section")
                return None
            
            if "companions" not in data or not data["companions"]:
                print(f"[!] World {source_name} missing 'companions' section")
                return None
            
            # Convert companions
            raw_companions = data.get("companions", {})
            converted_companions = {}
            for name, companion_data in raw_companions.items():
                print(f"[DEBUG Loader] Processing companion: {name}")
                print(f"[DEBUG Loader] Raw wardrobe type: {type(companion_data.get('wardrobe'))}")
                print(f"[DEBUG Loader] Raw wardrobe: {companion_data.get('wardrobe', {})}")
                
                converted = _convert_companion_v2_to_v3(name, companion_data)
                
                print(f"[DEBUG Loader] Converted wardrobe type: {type(converted.get('wardrobe'))}")
                print(f"[DEBUG Loader] Converted wardrobe: {converted.get('wardrobe', {})}")
                
                companion_obj = CompanionV3Config(**converted)
                
                print(f"[DEBUG Loader] Object wardrobe type: {type(companion_obj.wardrobe)}")
                print(f"[DEBUG Loader] Object wardrobe: {companion_obj.wardrobe}")
                
                converted_companions[name] = companion_obj
            data["companions"] = converted_companions
            
            # Convert quests
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
            
            # Convert milestones
            if "milestones" in data:
                milestones = {}
                for char_name, milestone_list in data["milestones"].items():
                    milestones[char_name] = [Milestone(**m) for m in milestone_list]
                data["milestones"] = milestones
            
            # Convert endgame
            if "endgame" in data and data["endgame"]:
                data["endgame"] = EndgameConfig(**data["endgame"])
            
            # Convert global_events
            if "global_events" in data:
                events = {}
                for event_id, event_data in data["global_events"].items():
                    events[event_id] = GlobalEvent(**event_data)
                data["global_events"] = events
            
            # Convert player_character
            if "player_character" in data and data["player_character"]:
                data["player_character"] = PlayerCharacter(**data["player_character"])
                print(f"[WorldLoader] Loaded player character: {data['player_character'].identity.name}")
            
            # Optional defaults
            if "npc_logic" not in data:
                data["npc_logic"] = {}
            if "visual_style" not in data:
                data["visual_style"] = {}
            if "locations" not in data:
                data["locations"] = {}
            if "time" not in data:
                data["time"] = {}
            
            print(f"[WorldLoader] World '{data['meta'].get('name', source_name)}' loaded successfully")
            return data
            
        except Exception as e:
            print(f"[ERR] Error processing world {source_name}: {e}")
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
