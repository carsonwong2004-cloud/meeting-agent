import pytest
from datetime import datetime
from models import TimeSlot, Participant, MeetingState


class TestTimeSlot:
    """Test TimeSlot model validation and methods."""
    
    def test_valid_timeslot(self):
        slot = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        assert slot.day == "Monday"
        assert slot.start_time == "14:00"
        assert slot.end_time == "16:00"
    
    def test_day_capitalization(self):
        slot = TimeSlot(day="monday", start_time="14:00", end_time="16:00")
        assert slot.day == "Monday"  # Should auto-capitalize
    
    def test_invalid_day(self):
        with pytest.raises(ValueError, match="Day must be one of"):
            TimeSlot(day="Moonday", start_time="14:00", end_time="16:00")
    
    def test_invalid_time_format(self):
        with pytest.raises(ValueError, match="Time must be in HH:MM format"):
            TimeSlot(day="Monday", start_time="2pm", end_time="16:00")
    
    def test_duration_calculation(self):
        slot = TimeSlot(day="Monday", start_time="14:00", end_time="16:30")
        assert slot.duration_minutes() == 150  # 2.5 hours
    
    def test_get_start_hour(self):
        slot = TimeSlot(day="Monday", start_time="14:30", end_time="16:00")
        assert slot.get_start_hour() == 14
    
    def test_overlaps_with_same_day(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Monday", start_time="15:00", end_time="17:00")
        assert slot1.overlaps_with(slot2) == True
    
    def test_no_overlap_different_days(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Tuesday", start_time="14:00", end_time="16:00")
        assert slot1.overlaps_with(slot2) == False
    
    def test_no_overlap_same_day(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Monday", start_time="16:00", end_time="18:00")
        assert slot1.overlaps_with(slot2) == False


class TestParticipant:
    """Test Participant model."""
    
    def test_valid_participant(self):
        p = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="16:00")],
            constraints="must be after 6pm",
            flexibility=7
        )
        assert p.name == "Alice"
        assert len(p.free_slots) == 1
        assert p.has_constraint() == True
        assert p.is_flexible() == True
    
    def test_default_flexibility(self):
        p = Participant(name="Bob")
        assert p.flexibility == 5
    
    def test_flexibility_bounds(self):
        with pytest.raises(ValueError):
            Participant(name="Alice", flexibility=11)
        
        with pytest.raises(ValueError):
            Participant(name="Bob", flexibility=0)
    
    def test_is_available_on_day(self):
        p = Participant(
            name="Alice",
            free_slots=[
                TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),
                TimeSlot(day="Wednesday", start_time="10:00", end_time="12:00")
            ]
        )
        assert p.is_available_on_day("Monday") == True
        assert p.is_available_on_day("Tuesday") == False
        assert p.is_available_on_day("wednesday") == True  # Case insensitive
    
    def test_get_slots_on_day(self):
        p = Participant(
            name="Alice",
            free_slots=[
                TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),
                TimeSlot(day="Monday", start_time="18:00", end_time="20:00"),
                TimeSlot(day="Tuesday", start_time="10:00", end_time="12:00")
            ]
        )
        monday_slots = p.get_slots_on_day("Monday")
        assert len(monday_slots) == 2
        assert all(slot.day == "Monday" for slot in monday_slots)


class TestMeetingState:
    """Test MeetingState model."""
    
    def test_initial_state(self):
        state = MeetingState(raw_input="test input")
        assert state.raw_input == "test input"
        assert state.status == "initialized"
        assert len(state.participants) == 0
        assert state.negotiation_rounds == 0
    
    def test_add_conflict(self):
        state = MeetingState()
        state.add_conflict("No common days")
        assert len(state.conflicts) == 1
        assert state.has_conflicts() == True
    
    def test_can_negotiate(self):
        state = MeetingState()
        assert state.can_negotiate() == True
        
        state.negotiation_rounds = 3
        assert state.can_negotiate() == False
    
    def test_record_negotiation(self):
        state = MeetingState()
        state.record_negotiation("Alice", "Can you do 6pm?", "accepted")
        
        assert state.negotiation_rounds == 1
        assert len(state.negotiation_history) == 1
        assert state.negotiation_history[0]["target"] == "Alice"
        assert state.negotiation_history[0]["result"] == "accepted"
    
    def test_get_participant(self):
        p1 = Participant(name="Alice")
        p2 = Participant(name="Bob")
        state = MeetingState(participants=[p1, p2])
        
        found = state.get_participant("alice")  # Case insensitive
        assert found is not None
        assert found.name == "Alice"
        
        not_found = state.get_participant("Charlie")
        assert not_found is None
