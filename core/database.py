"""Async SQLAlchemy database setup."""
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON, 
    ForeignKey, create_engine, select, desc
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import declarative_base, relationship

from config.settings import get_settings

Base = declarative_base()


class SessionModel(Base):
    """Tabella sessioni di gioco."""
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True)
    world_id = Column(String, nullable=False)
    companion_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    turn_count = Column(Integer, default=0)
    
    # Stato corrente
    location = Column(String, default="Unknown")
    time_of_day = Column(String, default="Morning")
    current_outfit = Column(String, default="default")
    gold = Column(Integer, default=0)
    hp = Column(Integer, default=20)
    stats = Column(JSON, default=dict)
    
    # Dati relazionali
    affinity = Column(JSON, default=dict)  # {nome: valore}
    npc_states = Column(JSON, default=dict)  # {nome: {outfit, location}}
    inventory = Column(JSON, default=list)
    quest_log = Column(JSON, default=list)
    flags = Column(JSON, default=dict)
    
    # Relazioni
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    memories = relationship("MemoryModel", back_populates="session", cascade="all, delete-orphan")
    quest_states = relationship("QuestStateModel", back_populates="session", cascade="all, delete-orphan")


class MessageModel(Base):
    """Messaggi della conversazione (history)."""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' o 'model'
    content = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata opzionali
    visual_en = Column(Text, default="")
    tags_en = Column(JSON, default=list)
    
    session = relationship("SessionModel", back_populates="messages")


class MemoryModel(Base):
    """Memorie a lungo termine (summaries e facts)."""
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    type = Column(String, nullable=False)  # 'summary', 'fact', 'event'
    content = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    importance = Column(Integer, default=5)  # 1-10
    
    session = relationship("SessionModel", back_populates="memories")


class QuestStateModel(Base):
    """Stato delle quest per sessione."""
    __tablename__ = "quest_states"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    quest_id = Column(String, nullable=False)
    status = Column(String, default="not_started")  # not_started, active, completed, failed
    current_stage_id = Column(String, nullable=True)
    stage_data = Column(JSON, default=dict)  # Dati persistenti per stage
    started_at = Column(Integer, default=0)  # turn_count
    completed_at = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = relationship("SessionModel", back_populates="quest_states")


class DatabaseManager:
    """Gestore database async."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or get_settings().database_url
        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def create_tables(self) -> None:
        """Crea tutte le tabelle."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self) -> None:
        """Drop tutte le tabelle (ATTENZIONE!)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Context manager per sessioni DB."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    # === Query Helper ===
    
    async def create_game_session(
        self, 
        db: AsyncSession,
        world_id: str, 
        companion_name: str,
        affinity: dict
    ) -> SessionModel:
        """Crea una nuova sessione."""
        session = SessionModel(
            world_id=world_id,
            companion_name=companion_name,
            affinity=affinity
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    async def get_session_by_id(self, db: AsyncSession, session_id: int) -> Optional[SessionModel]:
        """Recupera sessione per ID."""
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_recent_messages(
        self, 
        db: AsyncSession, 
        session_id: int, 
        limit: int = 50
    ) -> list[MessageModel]:
        """Recupera ultimi N messaggi."""
        result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(desc(MessageModel.id))
            .limit(limit)
        )
        return list(result.scalars().all())[::-1]  # Ordine cronologico
    
    async def add_message(
        self,
        db: AsyncSession,
        session_id: int,
        role: str,
        content: str,
        turn_number: int,
        visual_en: str = "",
        tags_en: list = None
    ) -> MessageModel:
        """Aggiunge un messaggio."""
        msg = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            turn_number=turn_number,
            visual_en=visual_en,
            tags_en=tags_en or []
        )
        db.add(msg)
        await db.commit()
        return msg
    
    async def add_memory(
        self,
        db: AsyncSession,
        session_id: int,
        mem_type: str,
        content: str,
        turn_number: int,
        importance: int = 5
    ) -> MemoryModel:
        """Aggiunge una memoria."""
        mem = MemoryModel(
            session_id=session_id,
            type=mem_type,
            content=content,
            turn_number=turn_number,
            importance=importance
        )
        db.add(mem)
        await db.commit()
        return mem
    
    async def get_memories(
        self,
        db: AsyncSession,
        session_id: int,
        mem_type: Optional[str] = None,
        limit: int = 20
    ) -> list[MemoryModel]:
        """Recupera memorie di una sessione."""
        query = select(MemoryModel).where(MemoryModel.session_id == session_id)
        if mem_type:
            query = query.where(MemoryModel.type == mem_type)
        query = query.order_by(desc(MemoryModel.id)).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())[::-1]
    
    # === Quest State Helpers ===
    
    async def get_quest_states(self, db: AsyncSession, session_id: int) -> list[QuestStateModel]:
        """Recupera tutti gli stati quest di una sessione."""
        result = await db.execute(
            select(QuestStateModel).where(QuestStateModel.session_id == session_id)
        )
        return list(result.scalars().all())
    
    async def save_quest_state(
        self,
        db: AsyncSession,
        session_id: int,
        quest_id: str,
        status: str,
        current_stage_id: Optional[str] = None,
        stage_data: dict = None,
        started_at: int = 0,
        completed_at: Optional[int] = None
    ) -> QuestStateModel:
        """Salva o aggiorna stato di una quest."""
        # Cerca esistente
        result = await db.execute(
            select(QuestStateModel).where(
                QuestStateModel.session_id == session_id,
                QuestStateModel.quest_id == quest_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.status = status
            existing.current_stage_id = current_stage_id
            existing.stage_data = stage_data or {}
            if completed_at:
                existing.completed_at = completed_at
            await db.commit()
            return existing
        else:
            # Crea nuovo
            state = QuestStateModel(
                session_id=session_id,
                quest_id=quest_id,
                status=status,
                current_stage_id=current_stage_id,
                stage_data=stage_data or {},
                started_at=started_at,
                completed_at=completed_at
            )
            db.add(state)
            await db.commit()
            return state


# Singleton
db_manager = DatabaseManager()
