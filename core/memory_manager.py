"""Memory management for conversation history and long-term memory."""
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import db_manager, DatabaseManager
from core.models import MemoryEntry
from media.llm_client import LLMClient


class MemoryManager:
    """Gestisce memoria a breve e lungo termine.
    
    Features:
    - History recente (ultimi N messaggi)
    - Compressione automatica quando buffer pieno
    - Knowledge base (fatti permanenti)
    """
    
    def __init__(
        self,
        session_id: int,
        llm_client: LLMClient,
        db: DatabaseManager = None,
        history_limit: int = 50,
        prune_count: int = 20
    ):
        self.session_id = session_id
        self.llm = llm_client
        self.db = db or db_manager
        self.history_limit = history_limit
        self.prune_count = prune_count
    
    async def get_context_block(self, db: AsyncSession) -> str:
        """Costruisce blocco contesto da iniettare nel system prompt.
        
        Include:
        - Fatti importanti (knowledge base)
        - Riassunti recenti
        """
        parts = []
        
        # Knowledge base (fatti permanenti)
        facts = await self.db.get_memories(
            db, self.session_id, mem_type="fact", limit=10
        )
        if facts:
            parts.append("🧠 KNOWLEDGE BASE:")
            for f in facts:
                parts.append(f"- {f.content}")
        
        # Summaries (riassunti)
        summaries = await self.db.get_memories(
            db, self.session_id, mem_type="summary", limit=5
        )
        if summaries:
            parts.append("\n📜 STORY SO FAR:")
            for s in summaries:
                parts.append(f"- {s.content}")
        
        return "\n".join(parts)
    
    async def get_recent_history(
        self, 
        db: AsyncSession, 
        limit: int = None
    ) -> List[dict]:
        """Recupera history gerarchica per LLM.
        
        Struttura:
        - Ultimi 10 messaggi (dettaglio completo)
        - Summary intermedi (overview)
        """
        limit = limit or self.history_limit
        
        # 1. Prendi ultimi 10 messaggi freschi
        recent_limit = min(10, limit)
        recent_messages = await self.db.get_recent_messages(
            db, self.session_id, limit=recent_limit
        )
        
        # 2. Se abbiamo poco context, aggiungi summary
        history = []
        if len(recent_messages) < 5:
            summaries = await self.db.get_memories(
                db, self.session_id, mem_type="summary", limit=3
            )
            if summaries:
                summary_text = "Previously: " + " | ".join([s.content for s in summaries])
                history.append({
                    "role": "system",
                    "content": f"[Memory archive: {summary_text}]"
                })
        
        # 3. Aggiungi messaggi recenti
        for msg in recent_messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    async def add_message(
        self,
        db: AsyncSession,
        role: str,
        content: str,
        turn_number: int,
        visual_en: str = "",
        tags_en: List[str] = None
    ):
        """Aggiunge messaggio e gestisce memoria."""
        await self.db.add_message(
            db, self.session_id, role, content, 
            turn_number, visual_en, tags_en
        )
        
        # Controlla se serve compressione
        await self._check_compression(db)
    
    async def add_fact(self, db: AsyncSession, fact: str, turn_number: int):
        """Aggiunge fatto permanente alla knowledge base."""
        if not fact:
            return
        
        # Evita duplicati (check semplice)
        existing = await self.db.get_memories(
            db, self.session_id, mem_type="fact"
        )
        for e in existing:
            if e.content.lower() == fact.lower():
                return  # Già presente
        
        await self.db.add_memory(
            db, self.session_id, "fact", fact, turn_number, importance=8
        )
        print(f"🧠 New fact: {fact}")
    
    async def _check_compression(self, db: AsyncSession):
        """Controlla se history troppo lunga e comprime.
        
        Dopo il riassunto, cancella i messaggi originali per pulire il DB.
        """
        messages = await self.db.get_recent_messages(
            db, self.session_id, limit=self.history_limit + self.prune_count
        )
        
        if len(messages) > self.history_limit:
            print(f"🧠 Memory buffer full ({len(messages)}), compressing...")
            
            # Prendi i più vecchi da riassumere (quelli da rimuovere)
            to_summarize = messages[:self.prune_count]
            
            # Genera riassunto
            history_for_llm = [
                {"role": msg.role, "content": msg.content}
                for msg in to_summarize
            ]
            
            summary = await self.llm.summarize(history_for_llm)
            
            if summary and summary != "Riassunto non disponibile.":
                # Salva summary
                turn_num = to_summarize[-1].turn_number
                await self.db.add_memory(
                    db, self.session_id, "summary", summary, turn_num
                )
                
                # NUOVO: Cancella i messaggi riassunti
                message_ids = [m.id for m in to_summarize]
                await self.db.delete_messages(db, message_ids)
                
                print(f"[OK] Archived {len(to_summarize)} messages: {summary[:60]}...")
    
    async def add_event(self, db: AsyncSession, event: str, turn_number: int):
        """Registra evento importante."""
        await self.db.add_memory(
            db, self.session_id, "event", event, turn_number, importance=7
        )
