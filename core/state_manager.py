"""Game state management with database persistence."""
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import DatabaseManager, db_manager, SessionModel
from core.models import GameSession, GameStateUpdate, CompanionConfig


class StateManager:
    """Gestisce stato gioco con persistenza SQLite."""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or db_manager
        self._session: Optional[GameSession] = None
        self._db_session: Optional[SessionModel] = None
    
    @property
    def current(self) -> Optional[GameSession]:
        """Sessione corrente in memoria."""
        return self._session
    
    @property
    def session_id(self) -> Optional[int]:
        """ID sessione DB."""
        return self._session.id if self._session else None
    
    async def create_new(
        self,
        db: AsyncSession,
        world_id: str,
        companion_name: str,
        world_data: Dict[str, Any]
    ) -> GameSession:
        """Crea nuova sessione."""
        companions = world_data.get("companions", {})
        
        # Se companion non valido, prendi il primo
        if companion_name not in companions:
            companion_name = list(companions.keys())[0]
        
        # Inizializza affinità
        affinity = {name: 0 for name in companions.keys()}
        
        # Inizializza NPC states
        npc_states = {}
        for name, data in companions.items():
            if name != companion_name:
                npc_states[name] = {
                    "current_outfit": data.default_outfit,
                    "location": "Unknown"
                }
        
        # Determina location iniziale
        start_location = "Start"
        if world_id == "school_life":
            start_location = "School Entrance Gate"
        elif world_id == "fantasy_dark":
            start_location = "Dungeon Cell"
        
        # Crea su DB
        db_session = await self.db.create_game_session(
            db, world_id, companion_name, affinity
        )
        
        # Popola campi extra
        db_session.npc_states = npc_states
        db_session.location = start_location
        db_session.current_outfit = companions[companion_name].default_outfit
        
        await db.commit()
        await db.refresh(db_session)
        
        # Crea modello Pydantic
        self._db_session = db_session
        self._session = GameSession.model_validate(db_session)
        
        print(f"[*] Session created: {companion_name} in {world_id}")
        return self._session
    
    async def load(self, db: AsyncSession, session_id: int) -> Optional[GameSession]:
        """Carica sessione esistente."""
        db_session = await self.db.get_session_by_id(db, session_id)
        if not db_session:
            return None
        
        self._db_session = db_session
        self._session = GameSession.model_validate(db_session)
        
        print(f"[OK] Loaded session: {self._session.id}")
        return self._session
    
    async def update(self, db: AsyncSession, updates: GameStateUpdate):
        """Applica aggiornamenti dallo stato LLM."""
        if not self._session or not self._db_session:
            return
        
        # Campi diretti
        if updates.location:
            self._session.location = updates.location
            self._db_session.location = updates.location
        
        if updates.current_outfit:
            self._session.current_outfit = updates.current_outfit
            self._db_session.current_outfit = updates.current_outfit
        
        if updates.time_of_day:
            self._session.time_of_day = updates.time_of_day
            self._db_session.time_of_day = updates.time_of_day
        
        if updates.gold is not None:
            self._session.gold = updates.gold
            self._db_session.gold = updates.gold
        
        if updates.hp is not None:
            self._session.hp = updates.hp
            self._db_session.hp = updates.hp
        
        # Affinità
        if updates.affinity_change:
            for char, change in updates.affinity_change.items():
                if char in self._session.affinity:
                    new_val = self._session.affinity[char] + change
                    self._session.affinity[char] = max(0, min(100, new_val))
            self._db_session.affinity = self._session.affinity
        
        # NPC updates
        if updates.npc_updates:
            for npc_name, npc_data in updates.npc_updates.items():
                if npc_name not in self._session.npc_states:
                    self._session.npc_states[npc_name] = {}
                
                if "outfit" in npc_data:
                    self._session.npc_states[npc_name]["current_outfit"] = npc_data["outfit"]
                    print(f"[O] {npc_name} changed outfit to: {npc_data['outfit']}")
            
            self._db_session.npc_states = self._session.npc_states
        
        # Inventario
        if updates.add_item:
            if updates.add_item not in self._session.inventory:
                self._session.inventory.append(updates.add_item)
                self._db_session.inventory = self._session.inventory
        
        if updates.remove_item:
            if updates.remove_item in self._session.inventory:
                self._session.inventory.remove(updates.remove_item)
                self._db_session.inventory = self._session.inventory
        
        # Flags
        if updates.flags:
            self._session.flags.update(updates.flags)
            self._db_session.flags = self._session.flags
        
        # Stats
        if updates.stat_changes:
            for stat, change in updates.stat_changes.items():
                if stat in self._session.stats:
                    new_val = self._session.stats[stat] + change
                    self._session.stats[stat] = max(0, new_val)
            self._db_session.stats = self._session.stats
        
        # Incrementa turno
        self._session.turn_count += 1
        self._db_session.turn_count = self._session.turn_count
        
        await db.commit()
    
    async def save_manual(self, db: AsyncSession, name: str = "manual") -> int:
        """Salvataggio manuale (snapshot)."""
        if not self._session or not self._db_session:
            return 0
        
        # Commit esplicito per sicurezza
        try:
            await db.commit()
            print(f"[SAVE] Game saved (session {self.session_id}) - {name}")
            return self.session_id
        except Exception as e:
            print(f"[ERR] Save error: {e}")
            await db.rollback()
            return 0
    
    async def list_saves(self, db: AsyncSession) -> list:
        """Lista tutte le sessioni salvate."""
        from core.database import SessionModel
        from sqlalchemy import select
        
        result = await db.execute(
            select(SessionModel).order_by(SessionModel.updated_at.desc())
        )
        return result.scalars().all()
    
    def get_personality_for_affinity(
        self, 
        char_name: str, 
        world_data: Dict
    ) -> str:
        """Ottiene descrizione personalità basata su affinità corrente.
        
        Il formato YAML è: personality_tiers: {soglia: descrizione}
        Esempio: {0: "Tier 1...", 20: "Tier 2..."}
        """
        if not self._session:
            return "Standard personality."
        
        current_aff = self._session.affinity.get(char_name, 0)
        
        # Trova tier appropriato
        companions = world_data.get("companions", {})
        char_data = companions.get(char_name)
        
        best_desc = "Standard personality."
        best_threshold = -1
        
        # Supporto formato v3 (personality_system.affinity_tiers dict)
        if char_data and char_data.personality_system and char_data.personality_system.affinity_tiers:
            tiers_dict = char_data.personality_system.affinity_tiers
            for tier_key, tier_data in sorted(tiers_dict.items(), key=lambda x: int(x[0])):
                threshold = int(tier_key)
                if current_aff >= threshold and threshold > best_threshold:
                    best_threshold = threshold
                    best_desc = tier_data.description
        # Supporto formato v2 (personality_tiers lista)
        elif char_data and char_data.personality_tiers:
            for tier in char_data.personality_tiers:
                threshold = tier.threshold
                description = tier.description
                if current_aff >= threshold and threshold > best_threshold:
                    best_threshold = threshold
                    best_desc = description
        
        return f"Affinity {current_aff} -> {best_desc}"
    
    def get_outfit_for(self, char_name: str) -> str:
        """Ottiene outfit corrente di un personaggio."""
        if not self._session:
            return "default"
        
        if char_name == self._session.companion_name:
            return self._session.current_outfit
        
        npc_state = self._session.npc_states.get(char_name, {})
        return npc_state.get("current_outfit", "default")
    
    async def switch_companion(self, db: AsyncSession, new_companion: str, world_data: Dict[str, Any]):
        """Cambia il companion attivo, salvando/caricando outfit correttamente.
        
        Quando il player passa da un personaggio all'altro:
        1. Salva l'outfit del vecchio companion nei npc_states
        2. Imposta il nuovo companion
        3. Carica l'outfit del nuovo companion (da npc_states o default)
        """
        if not self._session or not self._db_session:
            return
        
        old_companion = self._session.companion_name
        
        if old_companion == new_companion:
            return  # Niente da fare
        
        companions = world_data.get("companions", {})
        if new_companion not in companions:
            print(f"[!] Invalid companion: {new_companion}")
            return
        
        # 1. Salva outfit del vecchio companion nei npc_states
        if old_companion not in self._session.npc_states:
            self._session.npc_states[old_companion] = {}
        self._session.npc_states[old_companion]["current_outfit"] = self._session.current_outfit
        
        # 2. Carica outfit del nuovo companion (se esiste nei npc_states)
        new_outfit = "default"
        if new_companion in self._session.npc_states:
            new_outfit = self._session.npc_states[new_companion].get("current_outfit", "default")
            # Rimuovi dai npc_states perché ora è il companion attivo
            del self._session.npc_states[new_companion]
        else:
            # Usa default dal world data
            new_outfit = companions[new_companion].default_outfit
        
        # 3. Aggiorna sessione
        self._session.companion_name = new_companion
        self._session.current_outfit = new_outfit
        
        self._db_session.companion_name = new_companion
        self._db_session.current_outfit = new_outfit
        self._db_session.npc_states = self._session.npc_states
        
        await db.commit()
        print(f"[->] Switched from {old_companion} ({self._session.npc_states.get(old_companion, {}).get('current_outfit', 'default')}) to {new_companion} ({new_outfit})")
