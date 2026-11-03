from pydantic import BaseModel, field_validator
from datetime import datetime, time
from typing import Optional


class TimeSlot(BaseModel):
    """Represents a time block when someone is available."""
    
    day: str  # "Monday", "Tuesday", etc.
    start_time: str  # "14:00" in 24-hour format
    end_time: str  # "16:00" in 24-hour format
    
    @field_validator('day')
    @classmethod
    def validate_day(cls, v: str) -> str:
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        v_capitalized = v.capitalize()
        if v_capitalized not in valid_days:
            raise ValueError(f"Day must be one of {valid_days}, got {v}")
        return v_capitalized
    
    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Ensure time is in HH:MM 24-hour format."""
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"Time must be in HH:MM format (e.g., '14:00'), got {v}")
    
    def get_start_hour(self) -> int:
        """Extract hour from start_time."""
        return int(self.start_time.split(":")[0])
    
    def get_end_hour(self) -> int:
        """Extract hour from end_time."""
        return int(self.end_time.split(":")[0])
    
    def duration_minutes(self) -> int:
        """Calculate duration in minutes."""
        start_parts = self.start_time.split(":")
        end_parts = self.end_time.split(":")
        start_mins = int(start_parts[0]) * 60 + int(start_parts[1])
        end_mins = int(end_parts[0]) * 60 + int(end_parts[1])
        return end_mins - start_mins
    
    def overlaps_with(self, other: 'TimeSlot') -> bool:
        """Check if this slot overlaps with another on the same day."""
        if self.day != other.day:
            return False
        
        self_start = self.get_start_hour() * 60 + int(self.start_time.split(":")[1])
        self_end = self.get_end_hour() * 60 + int(self.end_time.split(":")[1])
        other_start = other.get_start_hour() * 60 + int(other.start_time.split(":")[1])
        other_end = other.get_end_hour() * 60 + int(other.end_time.split(":")[1])
        
        return not (self_end <= other_start or self_start >= other_end)
    
    def __str__(self) -> str:
        return f"{self.day} {self.start_time}-{self.end_time}"
