from typing import List, Optional
from models import TimeSlot, Participant
import re


def parse_constraint(constraint_text: str) -> dict:
    """
    Parse constraint text into structured format.

    Supported patterns:
        "must be after 6pm"       → {"type": "after",    "hour": 18}
        "must be before 3pm"      → {"type": "before",   "hour": 15}
        "no mornings"             → {"type": "after",    "hour": 12}
        "need at least 2 hours"   → {"type": "duration", "minutes": 120}
        "at least 90 minutes"     → {"type": "duration", "minutes": 90}
    """
    if not constraint_text:
        return {}

    text = constraint_text.lower()

    # Pattern: "after X pm/am"
    after_match = re.search(r'after\s+(\d+)\s*(pm|am)', text)
    if after_match:
        hour = int(after_match.group(1))
        period = after_match.group(2)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return {"type": "after", "hour": hour}

    # Pattern: "before X pm/am"
    before_match = re.search(r'before\s+(\d+)\s*(pm|am)', text)
    if before_match:
        hour = int(before_match.group(1))
        period = before_match.group(2)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return {"type": "before", "hour": hour}

    # Pattern: "need X hours" / "at least X hours" / "minimum X hour"
    duration_hour_match = re.search(
        r'(?:need|at least|minimum|min\.?)\s+(\d+(?:\.\d+)?)\s*hour', text
    )
    if duration_hour_match:
        hours = float(duration_hour_match.group(1))
        return {"type": "duration", "minutes": int(hours * 60)}

    # Pattern: "need X minutes" / "at least X minutes"
    duration_min_match = re.search(
        r'(?:need|at least|minimum|min\.?)\s+(\d+)\s*min', text
    )
    if duration_min_match:
        return {"type": "duration", "minutes": int(duration_min_match.group(1))}

    # Common phrases
    if "no morning" in text or "afternoon only" in text or "evenings only" in text:
        return {"type": "after", "hour": 12}

    if "morning only" in text:
        return {"type": "before", "hour": 12}

    return {}


def get_required_duration(participants: List[Participant]) -> int:
    """
    Extract the minimum meeting duration from participant constraints.
    Returns the strictest (longest) duration requirement, defaulting to 60 min.
    """
    required = 60  # Default: 1 hour

    for p in participants:
        constraints = p.constraints if isinstance(p.constraints, list) else (
            [p.constraints] if p.constraints else []
        )
        for c in constraints:
            parsed = parse_constraint(c)
            if parsed.get("type") == "duration":
                required = max(required, parsed["minutes"])

    return required


def apply_constraints(slots: List[TimeSlot], participants: List[Participant]) -> List[TimeSlot]:
    """
    Filter slots based on all participants' constraints.

    Handles:
    - "after X pm/am"   → slot must start at or after X
    - "before X pm/am"  → slot must end at or before X
    - "need X hours"    → slot duration must be >= X minutes
    - str or list[str] constraints on the Participant model
    """
    filtered_slots = []

    for slot in slots:
        valid = True

        for participant in participants:
            # Normalize constraints to a list
            raw = participant.constraints
            if raw is None:
                constraint_list = []
            elif isinstance(raw, str):
                constraint_list = [raw] if raw.strip() else []
            else:
                constraint_list = list(raw)

            for constraint_text in constraint_list:
                constraint = parse_constraint(constraint_text)

                if constraint.get("type") == "after":
                    required_hour = constraint["hour"]
                    if slot.get_start_hour() < required_hour:
                        valid = False
                        break

                elif constraint.get("type") == "before":
                    required_hour = constraint["hour"]
                    if slot.get_end_hour() > required_hour:
                        valid = False
                        break

                elif constraint.get("type") == "duration":
                    required_minutes = constraint["minutes"]
                    if slot.duration_minutes() < required_minutes:
                        valid = False
                        break

            if not valid:
                break

        if valid:
            filtered_slots.append(slot)

    return filtered_slots