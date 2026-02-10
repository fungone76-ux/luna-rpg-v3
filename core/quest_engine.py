"""Quest Engine - Sistema gestione quest modulare."""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import re

from core.quest_models import (
    QuestDefinition, QuestState, QuestStatus, QuestStage, 
    Condition, QuestAction, Milestone
)


@dataclass
class QuestUpdateResult:
    """Risultato di un update del quest engine."""
    new_quests: List[str] = field(default_factory=list)
    stage_changes: List[Dict[str, Any]] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    failed_quests: List[str] = field(default_factory=list)
    unlocked_quests: List[str] = field(default_factory=list)
    actions_to_execute: List[QuestAction] = field(default_factory=list)
    narrative_context: str = ""


class QuestEngine:
    """
    Engine generico per quest. 
    Non conosce il contenuto specifico - legge tutto dal world_data.
    """
    
    def __init__(self, world_data: Dict[str, Any]):
        self.world_data = world_data
        self.quest_definitions: Dict[str, QuestDefinition] = world_data.get("quests", {})
        self.milestones: Dict[str, List[Milestone]] = world_data.get("milestones", {})
        self.endgame = world_data.get("endgame")
        
        # Stato runtime (caricato da DB nella sessione)
        self.active_states: Dict[str, QuestState] = {}
        self.completed_quest_ids: set = set()
        
        # Validazione al boot
        self._validate_quest_definitions()
    
    def _validate_quest_definitions(self):
        """Valida che tutte le quest rispettino lo schema minimo."""
        errors = []
        
        for quest_id, quest in self.quest_definitions.items():
            # Check meta
            if not quest.meta.title:
                errors.append(f"Quest '{quest_id}' missing title")
            
            # Check stages
            if not quest.stages:
                errors.append(f"Quest '{quest_id}' has no stages")
            elif "start" not in quest.stages and len(quest.stages) > 0:
                # Non è un errore fatale, ma avvisa
                pass
            
            # Check che ogni stage abbia transitions se non è finale
            for stage_id, stage in quest.stages.items():
                if not stage.transitions and stage_id not in ["_complete", "_fail"]:
                    # Stage senza uscita - potrebbe essere finale
                    pass
        
        if errors:
            print(f"[QuestEngine] Validation warnings:")
            for e in errors[:5]:  # Mostra max 5
                print(f"  - {e}")
        
        print(f"[QuestEngine] Loaded {len(self.quest_definitions)} quest definitions")
    
    def load_saved_states(self, saved_states: List[QuestState]):
        """Carica stati salvati dal database."""
        for state in saved_states:
            self.active_states[state.quest_id] = state
            if state.status == QuestStatus.COMPLETED:
                self.completed_quest_ids.add(state.quest_id)
    
    def get_all_states(self) -> List[QuestState]:
        """Ritorna tutti gli stati per salvataggio."""
        return list(self.active_states.values())
    
    # ============================================================
    # API PUBBLICA
    # ============================================================
    
    def check_activations(self, game_state: Dict[str, Any]) -> List[str]:
        """
        Controlla quali quest si devono attivare.
        
        Args:
            game_state: Dict con affinity, location, flags, turn_count, etc.
        
        Returns:
            Lista di quest_id da attivare
        """
        activated = []
        
        for quest_id, quest in self.quest_definitions.items():
            # Salta se già attiva o completata
            if quest_id in self.active_states:
                state = self.active_states[quest_id]
                if state.status in [QuestStatus.ACTIVE, QuestStatus.COMPLETED]:
                    continue
            
            activation = quest.activation
            
            # Check tipo attivazione
            if activation.type == "auto":
                if self._evaluate_conditions(activation.conditions, game_state):
                    activated.append(quest_id)
            
            elif activation.type == "trigger":
                trigger_event = activation.trigger_event
                if trigger_event and game_state.get("last_event") == trigger_event:
                    activated.append(quest_id)
        
        return activated
    
    def activate_quest(self, quest_id: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Attiva una quest e ritorna le azioni da eseguire.
        
        Returns:
            Dict con actions, narrative_context, etc.
        """
        if quest_id not in self.quest_definitions:
            return None
        
        quest = self.quest_definitions[quest_id]
        
        # Trova lo stage iniziale
        start_stage_id = "start"
        if start_stage_id not in quest.stages:
            # Prendi il primo stage disponibile
            start_stage_id = list(quest.stages.keys())[0]
        
        # Crea stato
        state = QuestState(
            quest_id=quest_id,
            status=QuestStatus.ACTIVE,
            current_stage_id=start_stage_id,
            started_at=game_state.get("turn_count", 0)
        )
        self.active_states[quest_id] = state
        
        # Esegui on_enter dello stage iniziale
        start_stage = quest.stages[start_stage_id]
        actions = start_stage.on_enter
        
        print(f"[QuestEngine] Activated quest: {quest.meta.title} (stage: {start_stage_id})")
        
        return {
            "quest_id": quest_id,
            "title": quest.meta.title,
            "actions": actions,
            "narrative_context": start_stage.narrative_prompt,
            "hidden": quest.meta.hidden
        }
    
    def process_turn(self, quest_id: str, game_state: Dict[str, Any], user_input: str) -> Optional[QuestUpdateResult]:
        """
        Processa un turno per una quest attiva.
        
        Returns:
            QuestUpdateResult con cambiamenti, o None se nessun cambiamento
        """
        if quest_id not in self.active_states:
            return None
        
        state = self.active_states[quest_id]
        if state.status != QuestStatus.ACTIVE:
            return None
        
        quest = self.quest_definitions[quest_id]
        current_stage = quest.stages.get(state.current_stage_id)
        
        if not current_stage:
            return None
        
        # Prepara game_state esteso
        check_state = {**game_state, "user_input": user_input}
        
        # Valuta exit_conditions
        triggered_idx = None
        for i, condition in enumerate(current_stage.exit_conditions):
            if self._evaluate_condition(condition, check_state):
                triggered_idx = i
                break
        
        # Trova transizione
        target_stage_id = None
        for trans in current_stage.transitions:
            cond_name = trans.condition
            
            # Mappa indice a nome condizione
            if triggered_idx is not None and cond_name == f"condition_{triggered_idx}":
                target_stage_id = trans.target_stage
                break
            elif cond_name == "default" and triggered_idx is None:
                target_stage_id = trans.target_stage
                break
        
        if not target_stage_id:
            return None  # Nessuna transizione triggerata
        
        # Esegui transizione
        result = QuestUpdateResult()
        
        if target_stage_id == "_complete":
            self._complete_quest(quest_id, game_state, result)
        elif target_stage_id == "_fail":
            self._fail_quest(quest_id, game_state, result)
        else:
            self._transition_stage(quest_id, target_stage_id, game_state, result)
        
        return result if (result.stage_changes or result.completed_quests) else None
    
    def check_milestones(self, companion_name: str, game_state: Dict[str, Any]) -> List[Milestone]:
        """Controlla quali milestone sono stati raggiunti per una companion."""
        if not self.milestones or companion_name not in self.milestones:
            return []
        
        reached = []
        companion_milestones = self.milestones[companion_name]
        
        for milestone in companion_milestones:
            if self._evaluate_milestone(milestone, game_state, companion_name):
                reached.append(milestone)
        
        return reached
    
    def get_ui_milestone_status(self, companion_name: str, game_state: Dict[str, Any]) -> List[dict]:
        """
        Restituisce lo stato di tutti i milestone per la UI.
        
        Returns:
            Lista di dict con 'id', 'name', 'icon', 'reached' per ogni milestone
        """
        if not self.milestones or companion_name not in self.milestones:
            return []
        
        # Trova quali milestone sono stati raggiunti
        reached_milestones = self.check_milestones(companion_name, game_state)
        reached_ids = {m.id for m in reached_milestones}
        
        # Costruisci lista completa per UI
        result = []
        for milestone in self.milestones[companion_name]:
            result.append({
                'id': milestone.id,
                'name': milestone.name,
                'icon': milestone.icon,
                'reached': milestone.id in reached_ids
            })
        
        return result
    
    def get_active_quests_context(self) -> str:
        """Genera contesto per il system prompt."""
        if not self.active_states:
            return ""
        
        contexts = []
        for quest_id, state in self.active_states.items():
            if state.status != QuestStatus.ACTIVE:
                continue
            
            quest = self.quest_definitions.get(quest_id)
            if not quest:
                continue
            
            stage = quest.stages.get(state.current_stage_id)
            if not stage:
                continue
            
            ctx = f"Quest: {quest.meta.title} - {stage.title}"
            if stage.narrative_prompt:
                ctx += f". Context: {stage.narrative_prompt[:100]}..."
            contexts.append(ctx)
        
        return "\n".join(contexts) if contexts else ""
    
    def check_endgame_victory(self, game_state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Controlla se le condizioni di vittoria sono soddisfatte.
        
        Returns:
            (vittoria, lista companion conquistati)
        """
        if not self.endgame:
            return False, []
        
        conquered = []
        
        for condition in self.endgame.victory_conditions:
            target = condition.get("target")
            requires = condition.get("requires", [])
            
            all_met = True
            for req in requires:
                if not self._evaluate_endgame_requirement(req, target, game_state):
                    all_met = False
                    break
            
            if all_met:
                conquered.append(target)
        
        # Check se tutti i target sono conquistati
        all_targets = [c.get("target") for c in self.endgame.victory_conditions]
        victory = len(conquered) == len(all_targets) and len(all_targets) > 0
        
        return victory, conquered
    
    # ============================================================
    # METODI PRIVATI
    # ============================================================
    
    def _evaluate_conditions(self, conditions: List[Condition], game_state: Dict) -> bool:
        """Valuta una lista di condizioni (AND logico)."""
        if not conditions:
            return True
        return all(self._evaluate_condition(c, game_state) for c in conditions)
    
    def _evaluate_condition(self, condition: Condition, game_state: Dict) -> bool:
        """Valuta singola condizione."""
        cond_type = condition.type
        
        if cond_type == "affinity":
            char = condition.target
            current = game_state.get("affinity", {}).get(char, 0)
            return self._compare(current, condition.operator, condition.value)
        
        elif cond_type == "location":
            current = game_state.get("location", "")
            return self._compare(current, condition.operator, condition.value)
        
        elif cond_type == "time":
            current = game_state.get("time_of_day", "")
            return self._compare(current, condition.operator, condition.value)
        
        elif cond_type == "flag":
            key = condition.target
            current = game_state.get("flags", {}).get(key)
            return self._compare(current, condition.operator, condition.value)
        
        elif cond_type == "turn_count":
            current = game_state.get("turn_count", 0)
            return self._compare(current, condition.operator, condition.value)
        
        elif cond_type == "inventory":
            item = condition.target or condition.value
            inventory = game_state.get("inventory", [])
            has_item = item in inventory
            if condition.operator == "contains":
                return has_item
            elif condition.operator == "eq":
                return has_item
            return False
        
        elif cond_type == "action":
            pattern = condition.pattern or ""
            user_input = game_state.get("user_input", "").lower()
            return bool(re.search(pattern, user_input, re.IGNORECASE))
        
        return False
    
    def _compare(self, current: Any, operator: str, target: Any) -> bool:
        """Operatore di confronto generico."""
        try:
            if operator == "eq":
                return str(current) == str(target)
            elif operator == "gt":
                return float(current) > float(target)
            elif operator == "lt":
                return float(current) < float(target)
            elif operator == "gte":
                return float(current) >= float(target)
            elif operator == "lte":
                return float(current) <= float(target)
            elif operator == "contains":
                return str(target).lower() in str(current).lower()
        except (ValueError, TypeError):
            return False
        return False
    
    def _evaluate_milestone(self, milestone: Milestone, game_state: Dict, companion: str) -> bool:
        """Valuta se un milestone è raggiunto."""
        cond = milestone.condition
        
        # Check affinità
        if "affinity" in cond:
            required = cond["affinity"]
            current = game_state.get("affinity", {}).get(companion, 0)
            if current < required:
                return False
        
        # Check flag
        if "flag" in cond:
            flag_name = cond["flag"]
            if not game_state.get("flags", {}).get(flag_name):
                return False
        
        return True
    
    def _evaluate_endgame_requirement(self, req: Dict, companion: str, game_state: Dict) -> bool:
        """Valuta requisito endgame."""
        if "affinity" in req:
            current = game_state.get("affinity", {}).get(companion, 0)
            if current < req["affinity"]:
                return False
        
        if "flag" in req:
            flag_name = req["flag"]
            if not game_state.get("flags", {}).get(flag_name):
                return False
        
        return True
    
    def _transition_stage(self, quest_id: str, new_stage_id: str, game_state: Dict, result: QuestUpdateResult):
        """Gestisce transizione a nuovo stage."""
        state = self.active_states[quest_id]
        quest = self.quest_definitions[quest_id]
        
        # Aggiorna stato
        old_stage = state.current_stage_id
        state.current_stage_id = new_stage_id
        
        # Prendi nuovo stage
        stage = quest.stages.get(new_stage_id)
        if not stage:
            return
        
        result.stage_changes.append({
            "quest_id": quest_id,
            "from": old_stage,
            "to": new_stage_id,
            "title": stage.title
        })
        
        # Aggiungi azioni
        result.actions_to_execute.extend(stage.on_enter)
        result.narrative_context = stage.narrative_prompt
        
        print(f"[QuestEngine] {quest.meta.title}: {old_stage} -> {new_stage_id}")
    
    def _complete_quest(self, quest_id: str, game_state: Dict, result: QuestUpdateResult):
        """Completa una quest."""
        state = self.active_states[quest_id]
        state.status = QuestStatus.COMPLETED
        state.completed_at = game_state.get("turn_count", 0)
        self.completed_quest_ids.add(quest_id)
        
        quest = self.quest_definitions[quest_id]
        result.completed_quests.append(quest_id)
        
        # Processa rewards
        if quest.rewards:
            # Affinity
            for char, value in quest.rewards.affinity.items():
                result.actions_to_execute.append(QuestAction(
                    action="change_affinity",
                    character=char,
                    value=value
                ))
            
            # Flags
            for key, value in quest.rewards.flags.items():
                result.actions_to_execute.append(QuestAction(
                    action="set_flag",
                    key=key,
                    value=value
                ))
            
            # Unlock quests
            for unlock_quest_id in quest.rewards.unlock_quests:
                result.unlocked_quests.append(unlock_quest_id)
        
        print(f"[QuestEngine] Quest completed: {quest.meta.title}")
    
    def _fail_quest(self, quest_id: str, game_state: Dict, result: QuestUpdateResult):
        """Segna quest come fallita."""
        state = self.active_states[quest_id]
        state.status = QuestStatus.FAILED
        
        quest = self.quest_definitions[quest_id]
        result.failed_quests.append(quest_id)
        
        print(f"[QuestEngine] Quest failed: {quest.meta.title}")
    
    def get_companion_emotional_state(self, companion: str, game_state: Dict) -> Optional[str]:
        """Determina lo stato emotivo attuale di una companion."""
        char_config = self.world_data.get("companions", {}).get(companion)
        if not char_config or not char_config.personality_system:
            return "default"
        
        ps = char_config.personality_system
        flags = game_state.get("flags", {})
        
        # Check trigger_flags per ogni stato
        for state_name, state_data in ps.emotional_states.items():
            if state_name == "default":
                continue
            trigger_flags = state_data.trigger_flags if hasattr(state_data, "trigger_flags") else []
            if any(flags.get(f) for f in trigger_flags):
                return state_name
        
        return "default"
