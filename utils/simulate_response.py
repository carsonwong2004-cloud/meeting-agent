import random
import json
import os
from models import Participant


def load_response_templates() -> dict:
    """Load response templates from JSON."""
    template_path = os.path.join("data", "response_templates.json")
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def simulate_participant_response(
    participant: Participant,
    negotiation_message: str,
    times_asked_before: int = 0
) -> tuple[str, str]:
    """
    Simulate a participant's response to a negotiation request.
    
    Args:
        participant: The participant being asked
        negotiation_message: The request message
        times_asked_before: How many times they've been asked already
        
    Returns:
        Tuple of (result: "accepted"/"rejected"/"counter", response_message: str)
    """
    templates = load_response_templates()
    
    # Calculate acceptance probability based on flexibility_score
    base_prob = calculate_acceptance_probability(participant.flexibility_score)
    
    # Reduce probability for repeated asks
    repeated_ask_penalty = 0.3 * times_asked_before
    acceptance_prob = max(0.1, base_prob - repeated_ask_penalty)
    
    # Decide outcome
    roll = random.random()
    
    if roll < acceptance_prob:
        # Accept
        result = "accepted"
        response = random.choice(templates["acceptance_templates"])
        
        # Add enthusiasm for highly flexible people
        if participant.flexibility_score >= 8:
            response = response + " Happy to help coordinate!"
    
    elif roll < acceptance_prob + 0.15:  # Small chance of counter-offer
        result = "counter_offer"
        response = random.choice(templates["counter_offer_templates"])
        # In a real system, would suggest an actual alternative time
        response = response.replace("{alternative_time}", "Wednesday 3pm")
        response = response.replace("{requested_time}", "the suggested time")
    
    else:
        # Reject
        result = "rejected"
        response = random.choice(templates["rejection_templates"])
        
        # Add reason for low-flexibility people
        if participant.flexibility_score <= 4:
            reason = random.choice(templates["rejection_reasons"])
            response = response + f" I have a {reason}."
    
    return result, response


def calculate_acceptance_probability(flexibility_score: int) -> float:
    """
    Calculate base acceptance probability from flexibility score.
    
    Flexibility scale:
    - 10: 85% acceptance
    - 8-9: 70% acceptance
    - 6-7: 50% acceptance
    - 4-5: 30% acceptance
    - 1-3: 15% acceptance
    """
    if flexibility_score >= 9:
        return 0.85
    elif flexibility_score >= 8:
        return 0.70
    elif flexibility_score >= 6:
        return 0.50
    elif flexibility_score >= 4:
        return 0.30
    else:
        return 0.15


def update_participant_availability(
    participant: Participant,
    requested_change: str
) -> Participant:
    """
    Update a participant's availability after they accept a change.
    
    This is a simplified version - real implementation would parse
    the requested_change and modify free_slots accordingly.
    
    Args:
        participant: The participant who accepted
        requested_change: Description of what they agreed to
        
    Returns:
        Updated participant object
    """
    # For Phase 2, we'll just mark that they accepted
    # Phase 3 could implement actual schedule modification
    
    # TODO: Parse requested_change like "extend Monday to 6:30pm"
    # and actually modify participant.free_slots
    
    return participant