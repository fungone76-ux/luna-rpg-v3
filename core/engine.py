"""Main Game Engine - Async orchestrator with Quest System v3."""
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import db_manager, DatabaseManager
from core.models import (
    GameSession, WorldConfig, LLMResponse, SceneAnalysis, 
    GameStateUpdate, CompanionConfig
)
from core.state_manager import StateManager
from core.memory_manager import MemoryManager
from core.quest_engine import QuestEngine, QuestAction, QuestUpdateResult

from core.prompt_builders import (
    SingleCharacterBuilder, MultiCharacterBuilder, 
    NPCBuilder, PromptResult
)
from core.world_loader import WorldLoader
from media.llm_client import LLMClient
from media.comfy_image_client import ComfyImageClient
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
        
        # Clients
        self.llm = LLMClient()
        self.image_gen = ComfyImageClient()
        self.audio = AudioClient()
        self.video_gen = VideoClient()
        
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
        print(f"[O] DEBUG: Active companion={current_char}, outfit={current_outfit}")
        
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
            memory_context=memory_block
        )
        
        # ========== STEP 5: SALVA MESSAGGI ==========
        await self.memory.add_message(
            db, "user", user_input, self.state.current.turn_count
        )
        await self.memory.add_message(
            db, "model", response.text, self.state.current.turn_count,
            response.visual_en, response.tags_en
        )
        
        # ========== STEP 6: AGGIORNA STATO ==========
        if response.updates:
            await self.state.update(db, response.updates)
            if response.updates.new_fact:
                await self.memory.add_fact(
                    db, response.updates.new_fact, self.state.current.turn_count
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
        
        # Aggiungi notifiche quest al testo
        if quest_updates.narrative_context:
            result["text"] = quest_updates.narrative_context + "\n\n" + result["text"]
        
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
        """Esegue azioni definite dalle quest."""
        for action in actions:
            action_type = action.action
            print(f"[QuestAction] Executing: {action_type}")
            
            try:
                if action_type == "set_location":
                    self.state.current.location = action.target
                    self.state._db_session.location = action.target
                
                elif action_type == "set_outfit":
                    char = action.character
                    outfit = action.outfit
                    if char == self.state.current.companion_name:
                        self.state.current.current_outfit = outfit
                        self.state._db_session.current_outfit = outfit
                    else:
                        if char not in self.state.current.npc_states:
                            self.state.current.npc_states[char] = {}
                        self.state.current.npc_states[char]["current_outfit"] = outfit
                
                elif action_type == "add_flag" or action_type == "set_flag":
                    self.state.current.flags[action.key] = action.value
                    self.state._db_session.flags = self.state.current.flags
                
                elif action_type == "change_affinity":
                    char = action.character
                    delta = action.value or 0
                    if char in self.state.current.affinity:
                        self.state.current.affinity[char] = max(0, min(100, 
                            self.state.current.affinity[char] + delta))
                        self.state._db_session.affinity = self.state.current.affinity
                
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
                    self.state._db_session.time_of_day = action.target
                
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
    
    def _build_system_prompt_with_analysis(self, analysis: Dict[str, Any], quest_updates=None) -> str:
        """Costruisce system prompt con contesto quest."""
        base_prompt = self._build_system_prompt()
        
        directives = []
        
        if analysis.get("primary_subject"):
            directives.append(f"FOCUS CHARACTER: {analysis['primary_subject']}")
        
        if analysis.get("composition_type"):
            comp_map = {
                "close_up": "Use CLOSE UP framing",
                "medium_shot": "Use MEDIUM SHOT framing",
                "wide_shot": "Use WIDE/COWBOY SHOT framing"
            }
            directives.append(comp_map.get(analysis["composition_type"], ""))
        
        if analysis.get("body_focus"):
            directives.append(f"BODY FOCUS: {analysis['body_focus']}")
        
        # Aggiungi contesto quest
        if self.quest_engine:
            quest_context = self.quest_engine.get_active_quests_context()
            if quest_context:
                directives.append(f"\n=== ACTIVE QUESTS ===\n{quest_context}")
            
            # Aggiungi emotional state della companion attuale
            current_char = self.state.current.companion_name
            emo_state = self.quest_engine.get_companion_emotional_state(
                current_char, self._get_game_state_snapshot()
            )
            if emo_state and emo_state != "default":
                directives.append(f"\n{current_char} is currently feeling: {emo_state}")
        
        if directives:
            directive_text = "\n\n=== DIRECTIVES ===\n" + "\n".join(directives)
            return base_prompt + directive_text
        
        return base_prompt
    
    def _build_scene_analysis_from_response(self, response, predictive_analysis):
        """Costruisce SceneAnalysis dai metadata."""
        from core.models import CompositionType
        
        primary = self.state.current.companion_name
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
        
        return await self.image_gen.generate(
            prompt_result, 
            character_name=self.state.current.companion_name if self.state else "Luna"
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
        
        return await self.video_gen.generate(
            llm_client=self.llm,
            image_path=image_path,
            context=rich_context,
            character=self.state.current.companion_name,
            location=self.state.current.location,
            action=action,
            motion_speed=self.settings.video_motion_speed,
            user_action=user_action
        )
    
    def _build_system_prompt(self) -> str:
        """Costruisce system prompt per LLM."""
        if not self.state or not self.world_data:
            return "You are a Game Master."
        
        meta = self.world_data.get("meta", {})
        game = self.state.current
        
        char_name = game.companion_name
        current_aff = game.affinity.get(char_name, 0)
        partner_pers = self.state.get_personality_for_affinity(char_name, self.world_data)
        
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
                npc_instructions=npc_instructions,
                time_of_day=game.time_of_day,
                location=game.location,
                current_outfit=game.current_outfit
            )
            
            if visual_path.exists():
                visual_guide = visual_path.read_text(encoding="utf-8")
                full_prompt = nsfw_header + player_context + main_prompt + "\n\n" + visual_guide
            else:
                full_prompt = nsfw_header + player_context + main_prompt
            
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
