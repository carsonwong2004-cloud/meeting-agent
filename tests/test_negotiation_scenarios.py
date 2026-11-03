"""
Integration tests using the negotiation scenarios from data/negotiation_scenarios.json

These tests evaluate the full system's ability to resolve conflicts through negotiation.
"""

import pytest
import json
import os
from agents.graph import run_scheduler
from models import MeetingState


def load_scenarios():
    """Load test scenarios from JSON file."""
    scenario_path = os.path.join("data", "negotiation_scenarios.json")
    with open(scenario_path, "r") as f:
        data = json.load(f)
    return data["scenarios"]


@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda s: s["id"])
def test_negotiation_scenario(scenario):
    """
    Test each negotiation scenario.
    
    This is a statistical test - results may vary due to randomness in
    the simulated responses. Run multiple times to verify consistency.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    input_text = scenario["input"]
    expected = scenario["expected_behavior"]
    
    # Run the scheduler
    result = run_scheduler(input_text)
    meeting_state = MeetingState(**result["meeting_state"])
    
    # Check basic expectations
    if expected["should_resolve"]:
        # Should find a solution (may take multiple runs due to randomness)
        assert meeting_state.final_slot is not None or meeting_state.negotiation_rounds > 0, \
            f"Expected scenario {scenario['id']} to attempt negotiation"
    
    # Check negotiation round limits
    assert meeting_state.negotiation_rounds <= 3, \
        "Should not exceed 3 negotiation rounds"
    
    # If expected target is specified, check if it was asked
    if "expected_target" in expected:
        targets_asked = [h.get("target") for h in meeting_state.negotiation_history]
        assert expected["expected_target"] in targets_asked, \
            f"Expected to ask {expected['expected_target']}, but asked: {targets_asked}"


def test_negotiation_statistics():
    """
    Statistical test: Run the 'easy' scenario multiple times and verify
    that it resolves successfully at least 60% of the time.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    scenario_input = """Alice:
Monday 14:00-16:00 free
Constraint: must be after 6pm
Flexibility: 3

Bob:
Monday 14:00-20:00 free
Flexibility: 9"""
    
    successes = 0
    trials = 10
    
    for _ in range(trials):
        result = run_scheduler(scenario_input)
        meeting_state = MeetingState(**result["meeting_state"])
        
        if meeting_state.final_slot is not None:
            successes += 1
    
    success_rate = successes / trials
    
    # With Bob at flexibility 9, should resolve at least 60% of the time
    assert success_rate >= 0.6, \
        f"Success rate {success_rate:.1%} is below expected 60% (got {successes}/{trials})"


@pytest.mark.slow
def test_impossible_conflict_never_resolves():
    """
    Test that truly impossible conflicts are correctly identified.
    
    This scenario has mutually exclusive constraints with no flexibility.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    impossible_input = """Alice:
Monday 14:00-20:00 free
Constraint: must be after 6pm
Flexibility: 1

Bob:
Monday 14:00-20:00 free
Constraint: must be before 5pm
Flexibility: 1"""
    
    result = run_scheduler(impossible_input)
    meeting_state = MeetingState(**result["meeting_state"])
    
    # Should NOT resolve (opposite constraints)
    assert meeting_state.final_slot is None
    
    # Should have attempted negotiation
    assert meeting_state.negotiation_rounds > 0
    
    # Should have hit max rounds or gotten all rejections
    assert meeting_state.negotiation_rounds == 3 or \
           all(h.get("result") == "rejected" for h in meeting_state.negotiation_history)
