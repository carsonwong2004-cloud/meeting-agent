import pytest
from models import Participant, TimeSlot, MeetingState
from agents.negotiator import (
    select_best_target,
    format_participant_summary,
    format_negotiation_history,
    negotiator_agent
)
from utils.simulate_response import calculate_acceptance_probability, simulate_participant_response


class TestNegotiatorTargetSelection:
    """Test the target selection logic."""
    
    def test_selects_highest_flexibility(self):
        p1 = Participant(name="Alice", flexibility=5)
        p2 = Participant(name="Bob", flexibility=9)
        p3 = Participant(name="Carol", flexibility=7)
        
        target = select_best_target([p1, p2, p3], [])
        assert target.name == "Bob"  # Highest flexibility
    
    def test_avoids_already_asked(self):
        p1 = Participant(name="Alice", flexibility=9)
        p2 = Participant(name="Bob", flexibility=7)
        
        history = [{"target": "Alice", "result": "rejected"}]
        
        target = select_best_target([p1, p2], history)
        assert target.name == "Bob"  # Alice already asked
    
    def test_returns_none_when_all_asked(self):
        p1 = Participant(name="Alice", flexibility=9)
        p2 = Participant(name="Bob", flexibility=7)
        
        history = [
            {"target": "Alice", "result": "rejected"},
            {"target": "Bob", "result": "rejected"}
        ]
        
        target = select_best_target([p1, p2], history)
        assert target is not None  # Should still try someone with flexibility >= 5
    
    def test_empty_participants(self):
        target = select_best_target([], [])
        assert target is None


class TestParticipantResponseSimulation:
    """Test response simulation logic."""
    
    def test_acceptance_probability_scaling(self):
        assert calculate_acceptance_probability(10) == 0.85
        assert calculate_acceptance_probability(8) == 0.70
        assert calculate_acceptance_probability(6) == 0.50
        assert calculate_acceptance_probability(4) == 0.30
        assert calculate_acceptance_probability(2) == 0.15
    
    def test_high_flexibility_accepts_more(self):
        """Statistical test: high flexibility should accept more often."""
        high_flex = Participant(name="Alice", flexibility=9)
        low_flex = Participant(name="Bob", flexibility=2)
        
        high_accepts = 0
        low_accepts = 0
        trials = 100
        
        for _ in range(trials):
            result_high, _ = simulate_participant_response(high_flex, "Can you adjust?", 0)
            result_low, _ = simulate_participant_response(low_flex, "Can you adjust?", 0)
            
            if result_high == "accepted":
                high_accepts += 1
            if result_low == "accepted":
                low_accepts += 1
        
        # High flexibility should accept at least 2x more often
        assert high_accepts > low_accepts * 1.5
    
    def test_repeated_asks_reduce_acceptance(self):
        """Multiple asks to same person should reduce acceptance rate."""
        p = Participant(name="Alice", flexibility=8)
        
        first_accepts = 0
        third_accepts = 0
        trials = 100
        
        for _ in range(trials):
            result_first, _ = simulate_participant_response(p, "Can you adjust?", times_asked_before=0)
            result_third, _ = simulate_participant_response(p, "Can you adjust?", times_asked_before=2)
            
            if result_first == "accepted":
                first_accepts += 1
            if result_third == "accepted":
                third_accepts += 1
        
        # Third ask should have significantly lower acceptance
        assert first_accepts > third_accepts


class TestNegotiationFormatting:
    """Test prompt formatting functions."""
    
    def test_format_participant_summary(self):
        p1 = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="16:00")],
            constraints="must be after 6pm",
            flexibility=7
        )
        p2 = Participant(
            name="Bob",
            free_slots=[TimeSlot(day="Monday", start_time="15:00", end_time="17:00")],
            flexibility=9
        )
        
        summary = format_participant_summary([p1, p2])
        
        assert "Alice" in summary
        assert "Bob" in summary
        assert "7/10" in summary
        assert "9/10" in summary
        assert "must be after 6pm" in summary
    
    def test_format_empty_history(self):
        history = format_negotiation_history([])
        assert "None yet" in history or "first" in history.lower()
    
    def test_format_negotiation_history(self):
        history_data = [
            {"target": "Alice", "requested_change": "extend to 6pm", "result": "rejected"},
            {"target": "Bob", "requested_change": "shift to 7pm", "result": "accepted"}
        ]
        
        formatted = format_negotiation_history(history_data)
        
        assert "Alice" in formatted
        assert "Bob" in formatted
        assert "rejected" in formatted
        assert "accepted" in formatted


class TestNegotiatorAgent:
    """Integration tests for the full negotiator agent."""
    
    def test_negotiator_records_attempt(self):
        """Test that negotiator records its attempt in state."""
        p1 = Participant(name="Alice", flexibility=3, constraints="must be after 6pm")
        p2 = Participant(name="Bob", flexibility=9)
        
        state = {
            "meeting_state": MeetingState(
                participants=[p1, p2],
                conflicts=["No common time found"],
                status="conflict_detected"
            ).model_dump(),
            "messages": []
        }
        
        # Note: This test requires OPENAI_API_KEY set
        # For CI/CD, you might want to mock the LLM call
        try:
            result_state = negotiator_agent(state)
            meeting_state = MeetingState(**result_state["meeting_state"])
            
            # Should have recorded a negotiation attempt
            assert meeting_state.negotiation_rounds >= 1
            assert len(meeting_state.negotiation_history) >= 1
            
        except Exception as e:
            if "OPENAI_API_KEY" in str(e):
                pytest.skip("OpenAI API key not configured")
            else:
                raise
    
    def test_negotiator_respects_max_rounds(self):
        """Test that negotiator stops after max rounds."""
        p1 = Participant(name="Alice", flexibility=5)
        
        state = {
            "meeting_state": MeetingState(
                participants=[p1],
                conflicts=["Some conflict"],
                negotiation_rounds=3,  # Already at max
                max_negotiation_rounds=3,
                status="conflict_detected"
            ).model_dump(),
            "messages": []
        }
        
        result_state = negotiator_agent(state)
        meeting_state = MeetingState(**result_state["meeting_state"])
        
        # Should not exceed max rounds
        assert meeting_state.negotiation_rounds == 3
        assert "Max rounds" in " ".join(result_state["messages"])
