from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from .participant import Participant
from .time_slot import TimeSlot


class MeetingState(BaseModel):
    """Global state passed between agents during scheduling."""
    
    # Input
    raw_input: str = ""  # Original text input from users
    
    # Processed data
    participants: List[Participant] = Field(default_factory=list)
    candidate_slots: List[TimeSlot] = Field(default_factory=list)
    
    # Conflict tracking
    conflicts: List[str] = Field(default_factory=list)
    
    # Negotiation tracking
    negotiation_history: List[Dict[str, Any]] = Field(default_factory=list)
    negotiation_rounds: int = 0
    max_negotiation_rounds: int = 3
    
    # Final result
    final_slot: Optional[TimeSlot] = None
    final_message: Optional[str] = None
    
    # Status tracking
    status: str = "initialized"  # initialized → parsed → checked → negotiating → resolved/failed
    
    def add_conflict(self, conflict: str) -> None:
        """Add a conflict description."""
        self.conflicts.append(conflict)
    
    def has_conflicts(self) -> bool:
        """Check if any conflicts exist."""
        return len(self.conflicts) > 0
    
    def can_negotiate(self) -> bool:
        """Check if more negotiation rounds are possible."""
        return self.negotiation_rounds < self.max_negotiation_rounds
    
    def record_negotiation(self, target: str, message: str, result: str) -> None:
        """Record a negotiation attempt."""
        self.negotiation_history.append({
            "round": self.negotiation_rounds + 1,
            "target": target,
            "message": message,
            "result": result
        })
        self.negotiation_rounds += 1
    
    def get_participant(self, name: str) -> Optional[Participant]:
        """Find a participant by name."""
        for p in self.participants:
            if p.name.lower() == name.lower():
                return p
        return None
