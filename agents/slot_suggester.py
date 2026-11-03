from typing import Dict, Any, List, Tuple
from models import MeetingState, TimeSlot, Participant


def rank_slots(slots: List[TimeSlot], participants: List[Participant]) -> List[Tuple[TimeSlot, float]]:
    """
    Rank slots by desirability score.
    
    Scoring factors:
    - Prefer later in the day (after work/class hours)
    - Prefer weekdays over weekends
    - Prefer slots in the middle of the week
    
    Returns:
        List of (slot, score) tuples, sorted by score descending
    """
    scored_slots = []
    
    day_preference = {
        "Monday": 0.8,
        "Tuesday": 1.0,
        "Wednesday": 1.0,
        "Thursday": 0.9,
        "Friday": 0.7,
        "Saturday": 0.5,
        "Sunday": 0.4
    }
    
    for slot in slots:
        score = 0.0
        
        # Day preference (weekday better than weekend)
        score += day_preference.get(slot.day, 0.5) * 10
        
        # Time preference (prefer 2pm-8pm range)
        start_hour = slot.get_start_hour()
        if 14 <= start_hour <= 20:  # 2pm - 8pm
            score += 10
        elif 10 <= start_hour < 14:  # 10am - 2pm
            score += 7
        elif 20 < start_hour <= 22:  # 8pm - 10pm
            score += 5
        else:  # Early morning or very late
            score += 2
        
        # Duration bonus (longer slots are better, up to 2 hours)
        duration = slot.duration_minutes()
        if duration >= 120:
            score += 5
        elif duration >= 90:
            score += 3
        else:
            score += 1
        
        scored_slots.append((slot, score))
    
    # Sort by score descending
    scored_slots.sort(key=lambda x: x[1], reverse=True)
    
    return scored_slots


def slot_suggester_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rank and suggest the best meeting slots.
    
    Args:
        state: Contains meeting_state with candidate_slots
        
    Returns:
        Updated state with ranked suggestions
    """
    meeting_state = MeetingState(**state["meeting_state"])
    messages = state.get("messages", [])
    
    candidate_slots = meeting_state.candidate_slots
    participants = meeting_state.participants
    
    if not candidate_slots:
        messages.append("❌ Slot Suggester: No candidate slots to rank")
        meeting_state.status = "failed"
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state
    
    # Rank slots
    ranked_slots = rank_slots(candidate_slots, participants)
    
    # Pick top 3
    top_slots = ranked_slots[:3]
    
    messages.append(f"🎯 Slot Suggester: Ranked {len(candidate_slots)} candidates, suggesting top 3:")
    
    for i, (slot, score) in enumerate(top_slots, 1):
        messages.append(f"   {i}. {slot} (score: {score:.1f})")
    
    # Set the best slot as final recommendation
    if top_slots:
        best_slot = top_slots[0][0]
        meeting_state.final_slot = best_slot
        meeting_state.status = "resolved"
        messages.append(f"✅ Recommending: {best_slot}")
    
    state["meeting_state"] = meeting_state.model_dump()
    state["messages"] = messages
    
    return state
