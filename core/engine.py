"""Main Game Engine - Async orchestrator with Quest System v3 and Personality Engine."""
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import db_manager
from core.models import (
    GameSession, WorldConfig, LLMResponse, SceneAnalysis, 
    GameStateUpdate
)
from core.state_manager import StateManager
from core.memory_manager import MemoryManager
from core.quest_engine import QuestEngine, QuestAction, QuestUpdateResult
from core.personality_engine import PersonalityEngine
from core.time_manager import TimeManager

from core.prompt_builders import (
    SingleCharacterBuilder, MultiCharacterBuilder, 
    NPCBuilder
)
from core.world_loader import WorldLoader
from media.llm_client import LLMClient
from media.comfy_image_client import ComfyImageClient
from media.image_client import ImageClient  # SD WebUI
from media.audio_client import AudioClient
from media.video_client import VideoClient


class GameEngine:
    """Engine principale del gioco con Quest System v3.
    
    Orchestra:
    - LLM per narrativa
    - Predictive scene analysis (euristiche su input utente)
    - PromptBuilder per generazione immagini
    - StateManager per persistenza
    - MemoryManager per contesto
    - QuestEngine per storyline dinamiche
    """
    
    def __init__(self):
        # Settings
        from config.settings import Settings
        self.settings = Settings()
        
        # Clients (inizializzati in base alla modalità)
        self.llm = LLMClient()
        self.image_gen = None  # Sarà impostato in setup_clients
        self.image_gen_comfy = ComfyImageClient()  # Per RunPod
        self.image_gen_sd = ImageClient()  # Per locale (SD WebUI)
        self.audio = AudioClient()
        self.video_gen = VideoClient()
        self._is_runpod_mode = False
        
        # Core
        self.world_loader = WorldLoader()
        
        # Builders
        self.single_builder = SingleCharacterBuilder()
        self.multi_builder = MultiCharacterBuilder()
        self.npc_builder = NPCBuilder()
        
        # State (inizializzato su start/load)
        self.state: Optional[StateManager] = None
        self.memory: Optional[MemoryManager] = None
        self.world_data: Optional[Dict[str, Any]] = None
        self.quest_engine: Optional[QuestEngine] = None
        self.personality_engine: Optional[PersonalityEngine] = None
        self.time_manager: Optional[TimeManager] = None
        
        # Logger per dialogo e prompt (iniettato da main_window)
        self.dialog_logger = None
        self._current_turn = 0
    
    async def _manage_vram(self, action: str) -> bool:
        """Gestisce la staffetta VRAM tra SD e ComfyUI."""
        if action == "unload":
            return await self.image_gen.unload_model()
        elif action == "reload":
            return await self.image_gen.reload_model()
        return False
    
    async def initialize_database(self):
        """Inizializza database all'avvio."""
        await db_manager.create_tables()
        await db_manager.migrate_add_personality_state()  # Migration v3.2
    
    def setup_clients(self, use_runpod: bool = False, runpod_id: str = None):
        """Configura i client in base alla modalità scelta.
        
        Args:
            use_runpod: True per RunPod, False per locale
            runpod_id: ID del pod RunPod (se use_runpod=True)
        """
        self._is_runpod_mode = use_runpod
        
        if use_runpod and runpod_id:
            # Modalità RunPod: usa ComfyUI per immagini e video
            print(f"[Engine] Modalità RUNPOD (Pod: {runpod_id})")
            self.image_gen = self.image_gen_comfy
            # Aggiorna settings per RunPod
            import os
            os.environ["EXECUTION_MODE"] = "RUNPOD"
            os.environ["RUNPOD_ID"] = runpod_id
            # Ricarica settings
            from config.settings import get_settings
            get_settings.cache_clear()
            new_settings = get_settings()
            # Aggiorna client con nuovi settings
            self.image_gen_comfy = ComfyImageClient(new_settings)
            self.image_gen = self.image_gen_comfy
            self.video_gen = VideoClient(new_settings)
        else:
            # Modalità Locale: usa SD WebUI (porta 7860)
            print("[Engine] Modalità LOCALE (SD WebUI @ http://127.0.0.1:7860)")
            self.image_gen = self.image_gen_sd
            # Assicurati che video_gen usi i settings locali
            from config.settings import get_settings
            local_settings = get_settings()
            self.video_gen = VideoClient(local_settings)
        
        print(f"[Engine] Image client: {'ComfyUI (RunPod)' if use_runpod else 'SD WebUI (Local)'}")
        print(f"[Engine] Video disponibile: {self.video_gen.settings.video_available}")
    
    async def create_game(
        self,
        db: AsyncSession,
        world_id: str,
        companion_name: str
    ) -> GameSession:
        """Crea nuova partita."""
        # Carica mondo
        self.world_data = self.world_loader.load_world(world_id)
        if not self.world_data:
            raise ValueError(f"World not found: {world_id}")
        
        # State
        self.state = StateManager()
        session = await self.state.create_new(
            db, world_id, companion_name, self.world_data
        )
        
        # Memory
        self.memory = MemoryManager(
            session_id=session.id,
            llm_client=self.llm
        )
        
        # Quest Engine
        self.quest_engine = QuestEngine(self.world_data)
        
        # Personality Engine (nuovo)
        self.personality_engine = PersonalityEngine(self.world_data, self.state.current)
        
        # Time Manager - Living World
        self.time_manager = TimeManager()
        
        return session
    
    async def load_game(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Optional[GameSession]:
        """Carica partita esistente."""
        self.state = StateManager()
        session = await self.state.load(db, session_id)
        
        if not session:
            return None
        
        # Carica world data
        self.world_data = self.world_loader.load_world(session.world_id)
        
        # Memory
        self.memory = MemoryManager(
            session_id=session.id,
            llm_client=self.llm
        )
        
        # Quest Engine con stati salvati
        self.quest_engine = QuestEngine(self.world_data)
        saved_quest_states = await db_manager.get_quest_states(db, session_id)
        from core.quest_models import QuestState
        quest_states = [QuestState(**s.__dict__) for s in saved_quest_states]
        self.quest_engine.load_saved_states(quest_states)
        
        # Personality Engine - carica stato salvato se presente
        saved_personality = await db_manager.get_personality_state(db, session_id)
        if saved_personality:
            self.personality_engine = PersonalityEngine.deserialize(
                saved_personality, self.world_data, self.state.current
            )
            print(f"[Personality] Loaded saved state for session {session_id}")
        else:
            self.personality_engine = PersonalityEngine(self.world_data, self.state.current)
        
        # Time Manager - inizializza (puoi aggiungere persistenza se necessario)
        self.time_manager = TimeManager()
        
        return session
    
    async def process_turn(
        self,
        db: AsyncSession,
        user_input: str,
        generate_image: bool = True,
        generate_audio: bool = False
    ) -> Dict[str, Any]:
        """Processa un turno di gioco completo con Quest System v3."""
        if not self.state or not self.memory or not self.world_data:
            return {"error": "Game not initialized"}
        
        current_char = self.state.current.companion_name
        current_outfit = self.state.current.current_outfit
        self._current_turn += 1
        
        # Log inizio turno nel dialog_logger
        if self.dialog_logger and user_input:
            self.dialog_logger.log_turn_start(self._current_turn)
            self.dialog_logger.log_player_message(user_input)
        
        print(f"[O] DEBUG: Active companion={current_char}, outfit={current_outfit}")
        
        # ========== STEP 0: PERSONALITY ANALYSIS ==========
        if self.personality_engine:
            behavior_changes = self.personality_engine.analyze_player_action(
                current_char, user_input, self.state.current.turn_count
            )
            if behavior_changes:
                print(f"[Personality] Detected: {behavior_changes}")
            
            # Update NPC awareness (jealousy, etc.)
            self.personality_engine.update_npc_awareness(
                current_char, self.state.current.turn_count
            )
        
        # ========== STEP 1: QUEST SYSTEM UPDATE ==========
        quest_updates = QuestUpdateResult()
        if self.quest_engine:
            game_state_snapshot = self._get_game_state_snapshot()
            
            # 1.1 Check attivazioni nuove quest
            new_quests = self.quest_engine.check_activations(game_state_snapshot)
            for quest_id in new_quests:
                result = self.quest_engine.activate_quest(quest_id, game_state_snapshot)
                if result:
                    await self._execute_quest_actions(db, result.get("actions", []))
                    quest_updates.new_quests.append(quest_id)
                    if not result.get("hidden"):
                        quest_updates.narrative_context += f"\n[Quest Started: {result['title']}]"
            
            # 1.2 Update quest attive
            for quest_id in list(self.quest_engine.active_states.keys()):
                result = self.quest_engine.process_turn(quest_id, game_state_snapshot, user_input)
                if result:
                    quest_updates.actions_to_execute.extend(result.actions_to_execute)
                    quest_updates.stage_changes.extend(result.stage_changes)
                    quest_updates.completed_quests.extend(result.completed_quests)
                    quest_updates.failed_quests.extend(result.failed_quests)
                    quest_updates.unlocked_quests.extend(result.unlocked_quests)
                    
                    # Esegui azioni immediate
                    await self._execute_quest_actions(db, result.actions_to_execute)
            
            # 1.3 Salva stati quest nel DB
            for quest_state in self.quest_engine.get_all_states():
                await db_manager.save_quest_state(
                    db, self.state.session_id,
                    quest_state.quest_id, quest_state.status,
                    quest_state.current_stage_id, quest_state.stage_data,
                    quest_state.started_at, quest_state.completed_at
                )
            
            # 1.4 Check milestones
            for char_name in self.world_data.get("companions", {}).keys():
                milestones = self.quest_engine.check_milestones(char_name, game_state_snapshot)
                for m in milestones:
                    print(f"[Milestone] {char_name}: {m.name} reached!")
        
        # ========== STEP 2: SCENE ANALYSIS (Predictive) ==========
        print("[?] STEP 2: Predictive analysis of user input...")
        predictive_analysis = await self._analyze_user_intent(user_input)
        
        predicted_subject = predictive_analysis.get('primary_subject')
        if predicted_subject and predicted_subject != self.state.current.companion_name:
            print(f"[->] Predicted switch to {predicted_subject}")
            await self.state.switch_companion(db, predicted_subject, self.world_data)
        
        # ========== STEP 3: SYSTEM PROMPT CON QUEST CONTEXT ==========
        system_prompt = self._build_system_prompt_with_analysis(predictive_analysis, quest_updates)
        
        # ========== STEP 4: CHIAMA LLM ==========
        memory_block = await self.memory.get_context_block(db)
        history = await self.memory.get_recent_history(db)
        
        response: LLMResponse = await self.llm.generate_response(
            user_input=user_input,
            system_instruction=system_prompt,
            history=history,
            memory_context=memory_block,
            companion_name=self.state.current.companion_name
        )
        
        # ========== STEP 5: SALVA MESSAGGI ==========
        await self.memory.add_message(
            db, "user", user_input, self.state.current.turn_count
        )
        await self.memory.add_message(
            db, "model", response.text, self.state.current.turn_count,
            response.visual_en, response.tags_en
        )
        
        # Log risposta personaggio nel dialog_logger
        if self.dialog_logger:
            self.dialog_logger.log_character_response(current_char, response.text)
        
        # ========== STEP 6: VALIDATE AND APPLY STATE CHANGES ==========
        # LLM suggests changes; Python validates and applies correct values
        print(f"[DEBUG] LLM proposed affinity_change: {response.updates.affinity_change}")
        validated_updates = self._validate_llm_updates(response, current_char)
        print(f"[DEBUG] Validated affinity_change: {validated_updates.affinity_change}")
        
        if validated_updates:
            old_affinity = self.state.current.affinity.copy()
            await self.state.update(db, validated_updates)
            new_affinity = self.state.current.affinity
            # Log cambiamenti affinità
            for char in old_affinity:
                if old_affinity[char] != new_affinity[char]:
                    print(f"[AFFINITY] {char}: {old_affinity[char]} -> {new_affinity[char]} (+{new_affinity[char] - old_affinity[char]})")
            if validated_updates.new_fact:
                await self.memory.add_fact(
                    db, validated_updates.new_fact, self.state.current.turn_count
                )
        
        # ========== STEP 7: SCENE ANALYSIS ==========
        scene_analysis = self._build_scene_analysis_from_response(response, predictive_analysis)
        
        # ========== STEP 8: PREPARA RISULTATO ==========
        result = {
            "text": response.text,
            "scene_analysis": scene_analysis,
            "visual_en": response.visual_en,
            "tags_en": response.tags_en,
            "updates": response.updates,
            "image_path": None,
            "audio_played": False,
            "quest_updates": {
                "new": quest_updates.new_quests,
                "completed": quest_updates.completed_quests,
                "stage_changes": quest_updates.stage_changes
            }
        }
        
        # Nota: le notifiche quest sono ora iniettate nel system prompt
        # per integrazione narrativa naturale (non più prepend al testo)
        
        # ========== STEP 9: GENERA IMMAGINE ==========
        body_focus = response.body_focus
        if not body_focus and user_input:
            body_focus = self._detect_body_focus_from_text(user_input)
        
        if generate_image:
            image_path = await self._generate_image(
                scene_analysis, response.visual_en, response.tags_en,
                body_focus=body_focus
            )
            result["image_path"] = image_path
        
        # ========== STEP 10: AUDIO ==========
        if generate_audio:
            played = await self.audio.speak(response.text, self.state.current.companion_name)
            result["audio_played"] = played
        
        # ========== STEP 11: SAVE PERSONALITY STATE ==========
        if self.personality_engine:
            await db_manager.save_personality_state(
                db, self.state.session_id, self.personality_engine.serialize()
            )
        
        # ========== STEP 12: LIVING WORLD - TIME & NPC SCHEDULES ==========
        if self.time_manager:
            self.time_manager.advance_turn()
            
            # Aggiorna stato NPC basato su schedule
            for npc_name, npc_data in self.world_data.get("companions", {}).items():
                # CRITICAL FIX: Mai aggiornare lo schedule del companion ATTIVO!
                # Questo previene che Luna venga teletrasportata in palestra mentre le parli.
                if npc_name == self.state.current.companion_name:
                    continue

                # Per gli altri NPC, applica lo schedule normalmente
                schedule = self.time_manager.get_npc_schedule(npc_data)
                if schedule:
                    if npc_name not in self.state.current.npc_states:
                        self.state.current.npc_states[npc_name] = {}

                    # Aggiorna location e outfit se definiti nello schedule
                    if "location" in schedule:
                        self.state.current.npc_states[npc_name]["location"] = schedule["location"]
                    if "outfit" in schedule:
                        self.state.current.npc_states[npc_name]["current_outfit"] = schedule["outfit"]

            # Salva NPC states aggiornati nel DB
            await self.state.save_session_state(
                db,
                npc_states=self.state.current.npc_states,
                time_of_day=self.time_manager.get_time_of_day()
            )
            
            # Aggiorna time_of_day se cambiato
            new_time = self.time_manager.get_time_of_day()
            if new_time != self.state.current.time_of_day:
                self.state.current.time_of_day = new_time
                print(f"[Time] Now {self.time_manager.get_formatted_time()} - {new_time}")
        
        return result
    
    def _get_game_state_snapshot(self) -> Dict[str, Any]:
        """Crea snapshot dello stato per il quest engine."""
        if not self.state or not self.state.current:
            return {}
        
        game = self.state.current
        return {
            "affinity": game.affinity,
            "location": game.location,
            "time_of_day": game.time_of_day,
            "flags": game.flags,
            "turn_count": game.turn_count,
            "inventory": game.inventory,
            "companion": game.companion_name,
            "current_outfit": game.current_outfit
        }
    
    async def _execute_quest_actions(self, db: AsyncSession, actions: List[QuestAction]):
        """Esegue azioni definite dalle quest.
        
        NOTE: Modifica solo self.state.current (in-memory). 
        Il chiamante deve salvare esplicitamente su DB via state.save() o simile.
        Il parametro 'db' è ricevuto per compatibilità ma non usato direttamente qui.
        """
        for action in actions:
            action_type = action.action
            print(f"[QuestAction] Executing: {action_type}")
            
            try:
                if action_type == "set_location":
                    self.state.current.location = action.target
                    # DB update via db parameter
                
                elif action_type == "set_outfit":
                    char = action.character
                    outfit = action.outfit
                    if char == self.state.current.companion_name:
                        self.state.current.current_outfit = outfit
                    else:
                        if char not in self.state.current.npc_states:
                            self.state.current.npc_states[char] = {}
                        self.state.current.npc_states[char]["current_outfit"] = outfit
                
                elif action_type == "add_flag" or action_type == "set_flag":
                    self.state.current.flags[action.key] = action.value
                
                elif action_type == "change_affinity":
                    char = action.character
                    delta = action.value or 0
                    if char in self.state.current.affinity:
                        self.state.current.affinity[char] = max(0, min(100, 
                            self.state.current.affinity[char] + delta))
                
                elif action_type == "increment_stat":
                    char = action.character
                    stat = action.stat
                    if char == self.state.current.companion_name:
                        # Stats sono in flags per semplicità
                        key = f"{char.lower()}_{stat}"
                        current = self.state.current.flags.get(key, 0)
                        self.state.current.flags[key] = current + 1
                
                elif action_type == "set_emotional_state":
                    # Lo stato emotivo è gestito via flags
                    char = action.character
                    state = action.target
                    self.state.current.flags[f"{char.lower()}_emotional_state"] = state
                
                elif action_type == "set_time":
                    self.state.current.time_of_day = action.target
                
                elif action_type == "unlock_achievement":
                    print(f"[Achievement] Unlocked: {action.achievement}")
                
            except Exception as e:
                print(f"[!] QuestAction error: {e}")
        
        await db.commit()
    
    def _detect_body_focus_from_text(self, text: str) -> Optional[str]:
        """Analizza testo utente per forzare body focus."""
        text_lower = text.lower()
        
        keywords = {
            "legs": ["gambe", "legs", "cosce", "thighs", "piedi", "feet"],
            "torso": ["seno", "tette", "boobs", "breasts", "petto", "chest"],
            "face": ["faccia", "face", "viso", "occhi", "eyes", "sorriso"],
            "ass": ["culo", "ass", "natica", "butt", "bottom"],
            "hands": ["mani", "hands", "dita"],
        }
        
        for focus, words in keywords.items():
            if any(word in text_lower for word in words):
                look_verbs = ["guardo", "vedo", "osservo", "ammiro", "fisso"]
                if any(verb in text_lower for verb in look_verbs):
                    return focus
        
        return None
    
    async def _analyze_user_intent(self, user_input: str) -> Dict[str, Any]:
        """Analizza l'input utente per PREDIRE la scena."""
        from core.models import CompositionType
        
        text_lower = user_input.lower()
        body_focus = self._detect_body_focus_from_text(user_input)
        
        mentioned_chars = []
        for char_name in self.world_data.get("companions", {}).keys():
            if char_name.lower() in text_lower:
                mentioned_chars.append(char_name)
        
        predicted_subject = self.state.current.companion_name
        for char in mentioned_chars:
            if char != self.state.current.companion_name:
                predicted_subject = char
                break
        
        composition = "medium_shot"
        if body_focus in ["legs", "feet"]:
            composition = "wide_shot"
        elif body_focus in ["face", "hands"]:
            composition = "close_up"
        
        return {
            "primary_subject": predicted_subject,
            "body_focus": body_focus,
            "composition_type": composition,
            "mentioned_characters": mentioned_chars,
            "is_multi_character": len(mentioned_chars) >= 2
        }
    
    def _build_system_prompt_with_analysis(
        self, 
        analysis: Dict[str, Any], 
        quest_updates: QuestUpdateResult = None
    ) -> str:
        """Build system prompt with personality, quest context, and scene analysis.
        All context provided to LLM is in English for optimal model performance.
        """
        base_prompt = self._build_system_prompt()
        
        context_sections = []
        
        # 1. Scene Composition Directives
        if analysis.get("primary_subject"):
            context_sections.append(f"FOCUS CHARACTER: {analysis['primary_subject']}")
        
        if analysis.get("composition_type"):
            comp_map = {
                "close_up": "Use CLOSE UP framing",
                "medium_shot": "Use MEDIUM SHOT framing", 
                "wide_shot": "Use WIDE/COWBOY SHOT framing"
            }
            context_sections.append(comp_map.get(analysis["composition_type"], ""))
        
        if analysis.get("body_focus"):
            context_sections.append(f"BODY FOCUS: {analysis['body_focus']}")
        
        # 2. Personality Engine Context (NEW - in English)
        emotional_override = None  # Inizializza sempre
        if self.personality_engine:
            current_char = self.state.current.companion_name
            current_affinity = self.state.current.affinity.get(current_char, 0)
            
            personality_context = self.personality_engine.generate_system_prompt_context(
                current_char, current_affinity
            )
            context_sections.append(personality_context)
            
            # Emotional state override check
            emotional_override = self.personality_engine.get_emotional_state_override(current_char)
            if emotional_override:
                context_sections.append(f"\n[EMOTIONAL STATE OVERRIDE: {emotional_override}]")
        
        # 3. Quest Context & Dynamic Events (Seamless Narrative)
        if self.quest_engine:
            quest_context = self.quest_engine.get_active_quests_context()
            if quest_context:
                context_sections.append(f"\n=== ACTIVE QUESTS ===\n{quest_context}")
            
            # NUOVO: Quest events da narrare (seamless integration)
            if quest_updates and (quest_updates.new_quests or quest_updates.stage_changes):
                event_narratives = []
                
                for quest_id in quest_updates.new_quests:
                    quest_def = self.quest_engine.quest_definitions.get(quest_id)
                    if quest_def and not quest_def.meta.hidden:
                        stage = quest_def.stages.get(self.quest_engine.active_states[quest_id].current_stage_id)
                        if stage and stage.narrative_prompt:
                            event_narratives.append(f"{quest_def.meta.character or 'Someone'}: {stage.narrative_prompt}")
                
                for change in quest_updates.stage_changes:
                    quest_def = self.quest_engine.quest_definitions.get(change['quest_id'])
                    if quest_def:
                        stage = quest_def.stages.get(change['to'])
                        if stage and stage.narrative_prompt:
                            event_narratives.append(f"Development: {stage.narrative_prompt}")
                
                if event_narratives:
                    context_sections.append("\n=== IMMINENT EVENTS ===")
                    context_sections.append("Narrate these events naturally in your response. Do NOT use meta-terms like 'quest' or 'stage':")
                    for i, event in enumerate(event_narratives, 1):
                        context_sections.append(f"{i}. {event}")
            
            # Emotional state from quest system (fallback)
            if emotional_override is None:
                current_char = self.state.current.companion_name
                emo_state = self.quest_engine.get_companion_emotional_state(
                    current_char, self._get_game_state_snapshot()
                )
                if emo_state and emo_state != "default":
                    context_sections.append(f"\n{current_char} emotional state: {emo_state}")
        
        # 4. Current Game State (READ-ONLY for LLM)
        game = self.state.current
        state_context = f"""
=== CURRENT GAME STATE (READ ONLY) ===
Turn: {game.turn_count}
Character: {game.companion_name}
Current Outfit: {game.current_outfit}
Current Affinity with {game.companion_name}: {game.affinity.get(game.companion_name, 0)}/100
Location: {game.location}
Time: {game.time_of_day}
Active Flags: {list(game.flags.keys())[:5]}...

CRITICAL: You CANNOT directly modify these numbers. 
Describe the scene and suggest changes; the system will validate and apply them.
IMPORTANT: The character is currently wearing '{game.current_outfit}'. Describe this outfit accurately in your visual description.
"""
        context_sections.append(state_context)
        
        if context_sections:
            context_text = "\n\n".join(context_sections)
            return f"{base_prompt}\n\n{context_text}"
        
        return base_prompt
    
    def _build_scene_analysis_from_response(self, response, predictive_analysis):
        """Costruisce SceneAnalysis dai metadata."""
        from core.models import CompositionType
        
        # Usa il predicted_subject dall'analisi predittiva se disponibile
        # Questo permette di gestire NPC generici (es. bibliotecaria) diversi dalla companion corrente
        predicted_subject = predictive_analysis.get("primary_subject")
        if predicted_subject:
            primary = predicted_subject
        else:
            primary = self.state.current.companion_name
        
        # Se l'LLM suggerisce un cambio companion via npc_updates, usa quello
        if response.updates and response.updates.npc_updates:
            primary = response.updates.npc_updates.get("companion", primary)
        
        secondary = []
        mentioned = predictive_analysis.get("mentioned_characters", [])
        for char in mentioned:
            if char != primary:
                secondary.append(char)
        
        comp_type = predictive_analysis.get("composition_type", "medium_shot")
        try:
            composition = CompositionType(comp_type)
        except:
            composition = CompositionType.MEDIUM_SHOT
        
        return SceneAnalysis(
            primary_subject=primary,
            secondary_subjects=secondary,
            composition_type=composition,
            action_focus=response.visual_en or "",
            reasoning="Built from predictive analysis"
        )
    
    async def _generate_image(self, scene, visual_en, tags_en, body_focus=None):
        """Genera immagine basata su analisi scena."""
        if not scene.is_multi_character:
            prompt_result = self.single_builder.build(
                scene, visual_en, tags_en, 
                self.state.current, self.world_data,
                body_focus=body_focus
            )
        else:
            prompt_result = self.multi_builder.build(
                scene, visual_en, tags_en,
                self.state.current, self.world_data,
                body_focus=body_focus
            )
        
        # Log prompt immagine
        char_name = self.state.current.companion_name if self.state else "Luna"
        if self.dialog_logger:
            self.dialog_logger.log_image_prompt(char_name, prompt_result.positive)
        
        return await self.image_gen.generate(
            prompt_result, 
            character_name=char_name
        )
    
    async def generate_video(self, image_path, action="posing", narrative_context="", 
                           visual_description="", user_action=None):
        """Genera video da immagine."""
        if not self.state:
            return None
        
        rich_context = f"""WORLD: {self.state.current.location}
TURN: {self.state.current.turn_count}
CHARACTER: {self.state.current.companion_name}
ACTION: {action}

VISUAL: {visual_description if visual_description else 'N/A'}
NARRATIVE: {narrative_context if narrative_context else 'N/A'}

AFFINITY: {self.state.current.affinity}"""
        
        save_dir = Path("storage/videos")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        return await self.video_gen.generate(
            llm_client=self.llm,
            image_path=image_path,
            context=rich_context,
            character=self.state.current.companion_name,
            location=self.state.current.location,
            action=action,
            save_dir=save_dir,
            motion_speed=self.settings.video_motion_speed,
            user_action=user_action,
            dialog_logger=self.dialog_logger
        )
    
    def _build_dialogue_tone(self, char_name: str, affinity: int) -> str:
        """Costruisce il dialogue tone dinamico basato sull'affinità.
        
        Legge dal YAML del personaggio la configurazione dialogue_tone
        e seleziona il tier appropriato in base all'affinità corrente.
        """
        companion_data = self.world_data.get("companions", {}).get(char_name)
        if not companion_data:
            return f"Speak as {char_name} naturally."
        
        dialogue_config = getattr(companion_data, 'dialogue_tone', None)
        if not dialogue_config:
            # Fallback se non c'è dialogue_tone nel YAML
            return f"**{char_name}**: Speak in character based on affinity level {affinity}."
        
        # Ottieni base e tiers
        base = dialogue_config.get("base", f"Personaggio {char_name}")
        tiers = dialogue_config.get("affinity_tiers", {})
        
        # Trova il tier corretto in base all'affinità
        current_tier = None
        for tier_range, tier_data in tiers.items():
            # Parse range come "0-25", "26-50", ecc.
            if "-" in tier_range:
                min_aff, max_aff = tier_range.split("-")
                if int(min_aff) <= affinity <= int(max_aff):
                    current_tier = tier_data
                    break
        
        # Se non trovato, usa il primo tier o base
        if not current_tier and tiers:
            current_tier = list(tiers.values())[0]
        
        if not current_tier:
            return f"**{char_name}**: {base}"
        
        # Costruisci il testo del dialogue tone
        tier_name = current_tier.get("name", "Unknown")
        tone_desc = current_tier.get("tone", base)
        examples = current_tier.get("examples", [])
        markers = current_tier.get("voice_markers", [])
        
        lines = [
            f"**{char_name} - {tier_name} (Affinity: {affinity})**",
            f"",
            f"**TONE:** {tone_desc}",
            f"",
        ]
        
        if examples:
            lines.append("**EXAMPLE PHRASES:**")
            for ex in examples[:3]:  # Max 3 esempi
                lines.append(f'  "{ex}"')
            lines.append("")
        
        if markers:
            lines.append("**VOICE MARKERS:**")
            for marker in markers[:4]:  # Max 4 markers
                lines.append(f"  - {marker}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_system_prompt(self) -> str:
        """Costruisce system prompt per LLM."""
        if not self.state or not self.world_data:
            return "You are a Game Master."
        
        meta = self.world_data.get("meta", {})
        game = self.state.current
        
        char_name = game.companion_name
        current_aff = game.affinity.get(char_name, 0)
        partner_pers = self.state.get_personality_for_affinity(char_name, self.world_data)
        
        # NUOVO: Genera dialogue_tone dinamico basato sull'affinità
        dialogue_tone = self._build_dialogue_tone(char_name, current_aff)
        
        # NUOVO: Lista outfit disponibili per il personaggio corrente
        char_config = self.world_data.get("companions", {}).get(char_name)
        available_outfits = []
        if char_config and hasattr(char_config, 'wardrobe'):
            available_outfits = list(char_config.wardrobe.keys())
        
        outfit_instructions = f"""
=== OUTFIT SYSTEM FOR {char_name} ===
Current Outfit: {game.current_outfit}
Available Outfits: {', '.join(available_outfits)}

WHEN THE PLAYER ASKS TO CHANGE OUTFIT (e.g., "wear pajamas", "put on swimsuit"):
1. Narrate the character changing clothes naturally
2. Describe the NEW outfit in visual_en field
3. Set the new outfit key in "current_outfit" field of your JSON response
4. The system will validate and apply the change

WHEN THE PLAYER ASKS "what do you want to wear?" or "choose your outfit":
1. The character chooses based on personality, affinity ({current_aff}), and context
2. Higher affinity = more daring choices (lingerie, nude)
3. Lower affinity = conservative (uniform, casual)
4. Set the chosen outfit in "current_outfit" field

IMPORTANT: Always describe the outfit the character is ACTUALLY wearing in visual_en!

"""
        
        npc_instructions = ""
        for npc_name in self.world_data.get("companions", {}).keys():
            if npc_name != char_name:
                npc_aff = game.affinity.get(npc_name, 0)
                npc_pers = self.state.get_personality_for_affinity(npc_name, self.world_data)
                npc_outfit = self.state.get_outfit_for(npc_name)
                npc_instructions += f"- {npc_name}: {npc_pers} [Outfit: {npc_outfit}]\n"
        
        prompt_path = Path("prompts/system_prompt_compact.txt")
        if not prompt_path.exists():
            prompt_path = Path("prompts/system_prompt.txt")

        visual_path = Path("prompts/visual_director.txt")

        nsfw_header = """[CONTEXT: This is a mature dramatic visual novel for adults. 
All characters are consenting adults aged 21+. 
Use artistic, metaphorical, and suggestive language.
Focus on emotions, atmosphere, tension, and character dynamics.]\n"""

        # Note: Player context and Psychology context are injected BEFORE main prompt
        # to influence LLM behavior without modifying the system prompt file

        # Aggiungi contesto Player Character (NUOVO) - VERSIONE COMPLETA
        player_context = ""
        if "player_character" in self.world_data:
            pc = self.world_data["player_character"]
            if hasattr(pc, 'format_for_prompt'):
                # Versione completa con tutti i dettagli (~3000 token)
                player_context = "\n\n" + pc.format_for_prompt() + "\n\n"
            else:
                # Fallback se è un dict
                pc_identity = pc.get('identity', {})
                player_context = f"""

=== YOU (The Player Character) ===
Name: {pc_identity.get('name', 'Protagonist')}
Age: {pc_identity.get('age', 18)}
Background: {pc_identity.get('background', 'New student')}

=== NARRATIVE RULES FOR PLAYER ===
1. NPCs should acknowledge the player as "the new transfer student"
2. Use phrases like: "You look lost", "Are you the new guy?", "First day?"
3. The player doesn't know the school layout - describe locations if asked
4. Other students may be curious, suspicious, or ignore him
5. The player is still adjusting to the new environment

"""

        try:
            template = prompt_path.read_text(encoding="utf-8")
            main_prompt = template.format(
                genre=meta.get("genre", "RPG"),
                world_name=meta.get("name", "Unknown"),
                world_lore=meta.get("world_lore", ""),
                events_str="",
                char_name=char_name,
                partner_personality=partner_pers,
                dialogue_tone=dialogue_tone,
                npc_instructions=npc_instructions,
                time_of_day=game.time_of_day,
                location=game.location,
                current_outfit=game.current_outfit
            )

            if visual_path.exists():
                visual_guide = visual_path.read_text(encoding="utf-8")
                full_prompt = nsfw_header + player_context + main_prompt + outfit_instructions + "\n\n" + visual_guide
            else:
                full_prompt = nsfw_header + player_context + main_prompt + outfit_instructions

            return full_prompt

        except Exception as e:
            print(f"[!] Error formatting prompt: {e}")
            return nsfw_header + self._default_system_prompt(meta, char_name, partner_pers, game)

    def _default_system_prompt(self, meta, char_name, partner_pers, game):
        """Fallback se manca template."""
        # Aggiungi player character info se disponibile
        player_info = ""
        if self.world_data and "player_character" in self.world_data:
            pc = self.world_data["player_character"]
            if hasattr(pc, 'identity'):
                player_info = f"""

YOU ARE: {pc.identity.name} ({pc.identity.age} years old)
Background: {pc.identity.background[:100]}...
"""
            elif isinstance(pc, dict):
                pc_id = pc.get('identity', {})
                player_info = f"""

YOU ARE: {pc_id.get('name', 'Protagonist')} ({pc_id.get('age', 18)} years old)
"""

        return f"""You are the Game Master of a {meta.get('genre', 'RPG')} game.
World: {meta.get('name', 'Unknown')}
{player_info}

ACTIVE PARTNER ({char_name}):
{partner_pers}
Outfit: {game.current_outfit}

TIME: {game.time_of_day} | LOCATION: {game.location}

RULES:
1. Narrate in ITALIAN
2. Second person perspective ("Tu")
3. MAX 3-4 sentences per turn
4. All characters are adults (18+)
5. Acknowledge the player as "the new transfer student" if appropriate
"""

    def _validate_llm_updates(self, response: LLMResponse, current_companion: str) -> GameStateUpdate:
        """
        Validate LLM-proposed updates against game rules.
        Python is the source of truth; LLM suggestions are advisory only.
        """
        if not response.updates:
            return GameStateUpdate()

        proposed = response.updates
        validated = GameStateUpdate()

        # 1. Validate Affinity Changes
        if proposed.affinity_change:
            validated.affinity_change = {}

            # Retrocompatibilità: se affinity_change è un numero, converti in dizionario
            affinity_changes = proposed.affinity_change
            if isinstance(affinity_changes, (int, float)):
                # Numero singolo - applica al companion corrente
                affinity_changes = {current_companion: int(affinity_changes)}
                print(f"[Validate] Converted legacy affinity_change to: {affinity_changes}")

            for char, delta in affinity_changes.items():
                # Clamp to reasonable range per turn (-5 to +5)
                clamped_delta = max(-5, min(5, delta))

                # Check personality-based modifiers
                if self.personality_engine:
                    imp = self.personality_engine.impressions.get(char)
                    if imp:
                        # If high fear, reduce positive gains
                        if imp.fear > 50 and clamped_delta > 0:
                            clamped_delta = max(1, clamped_delta - 2)
                        # If high attraction, boost positive gains slightly
                        if imp.attraction > 60 and clamped_delta > 0:
                            clamped_delta = min(5, clamped_delta + 1)

                    # Apply jealousy impact (if player has been with other companions)
                    if char == current_companion:
                        jealousy = self.personality_engine.get_jealousy_impact(char)
                        if jealousy["affinity_modifier"] != 0:
                            old_delta = clamped_delta
                            clamped_delta = max(-5, min(5, clamped_delta + jealousy["affinity_modifier"]))
                            if clamped_delta != old_delta:
                                print(f"[Jealousy] {char}: affinity change modified by {jealousy['affinity_modifier']} due to jealousy")

                validated.affinity_change[char] = clamped_delta

                # Log if we modified the value
                if clamped_delta != delta:
                    print(f"[Validate] Affinity change for {char}: {delta} -> {clamped_delta}")

        # 2. Validate Flag Changes (prevent LLM from inventing arbitrary flags)
        if proposed.flags:
            validated.flags = {}
            for flag_name, value in proposed.flags.items():
                # Only allow known flag patterns or location/time updates
                allowed_patterns = [
                    "luna_", "stella_", "maria_",  # Character flags
                    "location_", "time_",           # World state
                    "quest_", "event_"              # Quest/Story flags
                ]
                if any(flag_name.startswith(p) for p in allowed_patterns):
                    validated.flags[flag_name] = value
                else:
                    print(f"[Validate] Rejected unknown flag: {flag_name}")

        # 3. Validate Outfit Changes
        if proposed.current_outfit:
            # Check if outfit exists in wardrobe for this character
            char_config = self.world_data.get("companions", {}).get(current_companion)
            is_valid_id = False

            if char_config and char_config.wardrobe:
                is_valid_id = proposed.current_outfit in char_config.wardrobe

            # Allow if it's a valid ID OR a creative description (contains "wearing" or spaces)
            is_creative_desc = "wearing " in proposed.current_outfit.lower() or " " in proposed.current_outfit

            if is_valid_id or is_creative_desc:
                validated.current_outfit = proposed.current_outfit
                if not is_valid_id:
                    print(f"[Validate] Creative outfit accepted: {proposed.current_outfit}")
            else:
                print(f"[Validate] Rejected unknown outfit ID: {proposed.current_outfit}")

        # 4. Validate Location/Time (must be from predefined set)
        if proposed.location:
            valid_locations = list(self.world_data.get("locations", {}).keys())
            if proposed.location in valid_locations or proposed.location in [
                "Classroom 3B", "School Gate", "Library", "Gym", "Nurse Office"
            ]:
                validated.location = proposed.location
            else:
                print(f"[Validate] Rejected unknown location: {proposed.location}")

        if proposed.time_of_day:
            if proposed.time_of_day in ["Morning", "Afternoon", "Evening", "Night"]:
                validated.time_of_day = proposed.time_of_day

        # 5. Copy other fields that don't need validation
        if proposed.new_fact:
            validated.new_fact = proposed.new_fact

        if proposed.add_item:
            validated.add_item = proposed.add_item

        if proposed.remove_item:
            validated.remove_item = proposed.remove_item

        if proposed.stat_changes:
            validated.stat_changes = proposed.stat_changes

        if proposed.npc_updates:
            validated.npc_updates = proposed.npc_updates

        return validated

    def _select_outfit_for_character(self, char_name: str) -> str:
        """Python seleziona l'outfit più appropriato per il personaggio.
        
        La scelta è basata su:
        - Affinità (alta = outfit audaci, bassa = conservativi)
        - Contesto (location, time)
        - Disponibilità nel wardrobe
        """
        import random
        
        char_config = self.world_data.get("companions", {}).get(char_name)
        if not char_config or not hasattr(char_config, 'wardrobe'):
            return "default"
        
        wardrobe = char_config.wardrobe
        available_outfits = list(wardrobe.keys())
        
        if not available_outfits:
            return "default"
        
        affinity = self.state.current.affinity.get(char_name, 0)
        location = self.state.current.location
        time_of_day = self.state.current.time_of_day
        
        # Categorie di outfit per tipo
        conservative = ["teacher_suit", "uniform_mod", "cleaning_uniform", 
                       "strict_teacher", "casual_teacher", "casual", "apron"]
        casual = ["casual_teacher", "casual", "private_tutoring", 
                 "cheerleader", "pajamas"]
        daring = ["swimsuit", "beach_teacher", "prom_dress", "night_robe", 
                 "gym_teacher", "lingerie"]
        explicit = ["nude", "lingerie"]
        
        # Filtro outfit disponibili per categoria
        available_conservative = [o for o in conservative if o in available_outfits]
        available_casual = [o for o in casual if o in available_outfits]
        available_daring = [o for o in daring if o in available_outfits]
        available_explicit = [o for o in explicit if o in available_outfits]
        
        # Logica di selezione basata su affinità
        if affinity >= 75:
            # Alta affinità: 40% audace, 30% explicit, 20% casual, 10% conservativo
            candidates = (available_daring * 4) + (available_explicit * 3) + \
                        (available_casual * 2) + available_conservative
        elif affinity >= 50:
            # Media-alta: 30% audace, 40% casual, 20% conservativo, 10% explicit
            candidates = (available_daring * 3) + (available_casual * 4) + \
                        (available_conservative * 2) + available_explicit
        elif affinity >= 25:
            # Media: 20% audace, 50% casual, 30% conservativo
            candidates = (available_daring * 2) + (available_casual * 5) + \
                        (available_conservative * 3)
        else:
            # Bassa affinità: 10% casual, 70% conservativo, 20% default/current
            candidates = available_casual + (available_conservative * 7)
        
        # Contesto-specific boost
        context_boost = []
        if "gym" in location.lower() or "palestra" in location.lower():
            context_boost = [o for o in ["gym_teacher"] if o in available_outfits]
        elif "beach" in location.lower() or "spiaggia" in location.lower():
            context_boost = [o for o in ["swimsuit", "beach_teacher"] if o in available_outfits]
        elif "bed" in location.lower() or "bedroom" in location.lower() or "camera" in location.lower():
            context_boost = [o for o in ["pajamas", "night_robe", "lingerie"] if o in available_outfits]
        elif time_of_day == "Night":
            context_boost = [o for o in ["night_robe", "pajamas", "lingerie"] if o in available_outfits]
        
        # Aggiungi context boost con peso maggiore
        candidates = context_boost * 3 + candidates
        
        # Se non ci sono candidati, usa tutti gli outfit disponibili
        if not candidates:
            candidates = available_outfits
        
        # Rimuovi duplicati mantenendo ordine
        seen = set()
        unique_candidates = []
        for o in candidates:
            if o not in seen:
                seen.add(o)
                unique_candidates.append(o)
        
        # Scegli random tra i candidati
        chosen = random.choice(unique_candidates)
        
        print(f"[OutfitSelect] {char_name} (affinity={affinity}, loc={location}) -> {chosen}")
        return chosen