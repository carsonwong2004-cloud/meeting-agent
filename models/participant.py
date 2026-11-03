from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union
from .time_slot import TimeSlot


class Participant(BaseModel):
    """Represents a person who needs to attend the meeting."""
    
    name: str
    free_slots: List[TimeSlot] = Field(default_factory=list)
    constraints: Union[str, List[str], None] = None  # Accept both string and list
    flexibility_score: int = Field(default=5, ge=1, le=10, alias="flexibility")
    
    class Config:
        populate_by_name = True  # Allow both 'flexibility' and 'flexibility_score'
    
    @field_validator('constraints', mode='before')
    @classmethod
    def normalize_constraints(cls, v):
        """Convert constraints to list format, handle None."""
        if v is None or v == "null":
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(c) for c in v if c]
        return []
    
    def has_constraint(self) -> bool:
        """Check if participant has any scheduling constraints."""
        return bool(self.constraints)
    
    def is_flexible(self) -> bool:
        """Check if participant is considered flexible (>= 6/10)."""
        return self.flexibility_score >= 6
    
    def is_available_on_day(self, day: str) -> bool:
        """Check if participant has any availability on a given day."""
        return any(slot.day.lower() == day.lower() for slot in self.free_slots)
    
    def get_slots_on_day(self, day: str) -> List[TimeSlot]:
        """Get all time slots for a specific day."""
        return [slot for slot in self.free_slots if slot.day.lower() == day.lower()]
    
    def __str__(self) -> str:
        slots_str = f"{len(self.free_slots)} slots"
        constraint_str = f", constraint: {self.constraints[0] if self.constraints else 'None'}"
        return f"{self.name} ({slots_str}, flexibility: {self.flexibility_score}/10{constraint_str})"
