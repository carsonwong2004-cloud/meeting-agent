from typing import Dict, Any, List
from models import MeetingState, Participant, TimeSlot
from utils import find_common_slots, apply_constraints


def identify_conflicts(participants: List[Participant], common_slots: List[TimeSlot]) -> List[str]:
    """
    Identify and describe why no common slots exist.
    
    Returns:
        List of human-readable conflict descriptions
    """
    conflicts = []
    
    if len(participants) < 2:
        return conflicts
    
    # Check if anyone has no availability
    for p in participants:
        if not p.free_slots:
            conflicts.append(f"{p.name} has not provided any available time slots")
    
    if conflicts:
        return conflicts
    
    # Check day-level conflicts
    days_available = {}
    for p in participants:
        days = set(slot.day for slot in p.free_slots)
        days_available[p.name] = days
    
    # Find if there's any common day
    common_days = set.intersection(*[days for days in days_available.values()])
    
    if not common_days:
        conflicts.append(
            f"No common days: " + 
            ", ".join([f"{name} is only free on {'/'.join(days)}" 
                      for name, days in days_available.items()])
        )
    
    # Check constraint conflicts
    for p in participants:
        if p.constraints:
            # Check if constraint is too restrictive
            constrained_slots = apply_constraints(p.free_slots, [p])
            if not constrained_slots:
                conflicts.append(
                    f"{p.name}'s constraint '{p.constraints}' eliminates all their available slots"
                )
    
    # Check time overlap issues
    if common_days and not common_slots:
        conflicts.append(
            "Participants have overlapping days but no overlapping time blocks"
        )
        
        # Give specific examples
        for day in list(common_days)[:2]:  # Show up to 2 days
            day_info = []
            for p in participants:
                p_slots = [s for s in p.free_slots if s.day == day]
                if p_slots:
                    times = [f"{s.start_time}-{s.end_time}" for s in p_slots]
                    day_info.append(f"{p.name}: {', '.join(times)}")
            
            if day_info:
                conflicts.append(f"  Example ({day}): {'; '.join(day_info)}")
    
    return conflicts


def conflict_checker_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check for scheduling conflicts and find common available slots.
    
    Args:
        state: Contains meeting_state with participants
        
    Returns:
        Updated state with candidate_slots or conflicts
    """
    meeting_state = MeetingState(**state["meeting_state"])
    messages = state.get("messages", [])
    
    participants = meeting_state.participants
    
    if not participants:
        messages.append("❌ Conflict Checker: No participants to check")
        meeting_state.status = "failed"
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state
    
    # Step 1: Find common slots (ignoring constraints first)
    common_slots = find_common_slots(participants, min_duration_minutes=60)
    
    messages.append(f"🔍 Conflict Checker: Found {len(common_slots)} overlapping time blocks")
    
    # Step 2: Apply constraints
    if common_slots:
        filtered_slots = apply_constraints(common_slots, participants)
        meeting_state.candidate_slots = filtered_slots
        
        if filtered_slots:
            messages.append(f"✅ Conflict Checker: {len(filtered_slots)} slots satisfy all constraints")
            for slot in filtered_slots[:3]:  # Show top 3
                messages.append(f"   • {slot}")
            meeting_state.status = "checked"
        else:
            messages.append("⚠️ Conflict Checker: Overlaps exist but constraints eliminate all options")
            conflicts = identify_conflicts(participants, common_slots)
            meeting_state.conflicts = conflicts
            for conflict in conflicts:
                messages.append(f"   • {conflict}")
            meeting_state.status = "conflict_detected"
    else:
        messages.append("⚠️ Conflict Checker: No overlapping time blocks found")
        conflicts = identify_conflicts(participants, common_slots)
        meeting_state.conflicts = conflicts
        for conflict in conflicts:
            messages.append(f"   • {conflict}")
        meeting_state.status = "conflict_detected"
    
    state["meeting_state"] = meeting_state.model_dump()
    state["messages"] = messages
    
    return state
