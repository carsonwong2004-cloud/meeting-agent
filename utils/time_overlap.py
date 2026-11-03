from typing import List, Tuple, Optional
from models import TimeSlot, Participant


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def check_time_overlap(slot1: TimeSlot, slot2: TimeSlot) -> Optional[Tuple[str, str]]:
    """
    Find overlapping time between two slots on the same day.
    
    Returns:
        Tuple of (start_time, end_time) if overlap exists, None otherwise
    """
    if slot1.day != slot2.day:
        return None
    
    start1 = time_to_minutes(slot1.start_time)
    end1 = time_to_minutes(slot1.end_time)
    start2 = time_to_minutes(slot2.start_time)
    end2 = time_to_minutes(slot2.end_time)
    
    # Find overlap
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    
    if overlap_start < overlap_end:
        return (minutes_to_time(overlap_start), minutes_to_time(overlap_end))
    
    return None


def find_common_slots(participants: List[Participant], min_duration_minutes: int = 60) -> List[TimeSlot]:
    """
    Find all time slots where ALL participants are available.
    
    Args:
        participants: List of participants with their availability
        min_duration_minutes: Minimum meeting duration required
        
    Returns:
        List of common time slots
    """
    if not participants:
        return []
    
    if len(participants) == 1:
        # Only one person, return their slots
        return participants[0].free_slots
    
    # Start with first person's slots
    common_slots = participants[0].free_slots.copy()
    
    # Intersect with each subsequent person
    for participant in participants[1:]:
        new_common_slots = []
        
        for common_slot in common_slots:
            for p_slot in participant.free_slots:
                overlap = check_time_overlap(common_slot, p_slot)
                if overlap:
                    # Create a new slot from the overlap
                    overlap_slot = TimeSlot(
                        day=common_slot.day,
                        start_time=overlap[0],
                        end_time=overlap[1]
                    )
                    
                    # Only keep if meets minimum duration
                    if overlap_slot.duration_minutes() >= min_duration_minutes:
                        new_common_slots.append(overlap_slot)
        
        common_slots = new_common_slots
        
        # Early exit if no common slots
        if not common_slots:
            break
    
    return common_slots
