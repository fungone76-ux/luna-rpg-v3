"""Time management for Living World system."""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class TimeManager:
    """Gestisce il tempo di gioco con ciclo giornaliero.
    
    1 turno = 15 minuti di tempo di gioco
    """
    
    def __init__(self, start_time: Optional[datetime] = None):
        """Inizializza il tempo di gioco.
        
        Args:
            start_time: Data/ora iniziale. Default: 1 Marzo, 8:00 AM (inizio scuola)
        """
        if start_time is None:
            # Default: primo giorno di scuola, mattina
            self.current_time = datetime(2024, 3, 1, 8, 0)
        else:
            self.current_time = start_time
        
        self.minutes_per_turn = 15
        self.turn_count = 0
    
    def advance_turn(self) -> datetime:
        """Avanza il tempo di gioco di un turno."""
        self.current_time += timedelta(minutes=self.minutes_per_turn)
        self.turn_count += 1
        return self.current_time
    
    def get_time_of_day(self) -> str:
        """Ritorna il periodo del giorno in base all'ora."""
        hour = self.current_time.hour
        if 6 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 22:
            return "Evening"
        else:
            return "Night"
    
    def get_day_of_week(self) -> str:
        """Ritorna il giorno della settimana abbreviato."""
        return self.current_time.strftime("%a")  # Mon, Tue, etc.
    
    def get_formatted_time(self) -> str:
        """Ritorna l'ora formattata HH:MM."""
        return self.current_time.strftime("%H:%M")
    
    def get_formatted_date(self) -> str:
        """Ritorna la data formattata."""
        return self.current_time.strftime("%d %b")  # 01 Mar
    
    def is_weekend(self) -> bool:
        """True se sabato o domenica."""
        return self.current_time.weekday() >= 5
    
    def is_school_hours(self) -> bool:
        """True se durante le ore di scuola (8:00 - 16:00)."""
        hour = self.current_time.hour
        return 8 <= hour < 16 and not self.is_weekend()
    
    def get_npc_schedule(self, npc_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ritorna lo schedule corrente di un NPC.
        
        Args:
            npc_data: Dati NPC dal world_data (con personality_system.schedule)
        
        Returns:
            Dict con location, outfit, activity per il periodo attuale
        """
        if not npc_data or not hasattr(npc_data, 'personality_system'):
            return None
        
        ps = npc_data.personality_system
        if not ps or not hasattr(ps, 'schedule'):
            return None
        
        schedule = ps.schedule
        time_period = self.get_time_of_day()
        
        return schedule.get(time_period)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize per salvataggio."""
        return {
            "current_time": self.current_time.isoformat(),
            "turn_count": self.turn_count,
            "minutes_per_turn": self.minutes_per_turn
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeManager":
        """Deserialize da salvataggio."""
        tm = cls.__new__(cls)
        tm.current_time = datetime.fromisoformat(data["current_time"])
        tm.turn_count = data.get("turn_count", 0)
        tm.minutes_per_turn = data.get("minutes_per_turn", 15)
        return tm
    
    def get_context_string(self) -> str:
        """Ritorna stringa contesto per LLM."""
        time_day = self.get_time_of_day()
        day_name = self.get_day_of_week()
        time_str = self.get_formatted_time()
        
        context = f"Time: {time_str} ({time_day})"
        if self.is_weekend():
            context += " - Weekend"
        
        return context
