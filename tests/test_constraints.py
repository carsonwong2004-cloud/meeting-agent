import pytest
from models import TimeSlot, Participant
from utils.constraints import parse_constraint, apply_constraints


class TestParseConstraint:
    """Test constraint parsing."""
    
    def test_after_pm(self):
        constraint = parse_constraint("must be after 6pm")
        assert constraint == {"type": "after", "hour": 18}
    
    def test_after_am(self):
        constraint = parse_constraint("must be after 10am")
        assert constraint == {"type": "after", "hour": 10}
    
    def test_before_pm(self):
        constraint = parse_constraint("must be before 5pm")
        assert constraint == {"type": "before", "hour": 17}
    
    def test_before_am(self):
        constraint = parse_constraint("must be before 11am")
        assert constraint == {"type": "before", "hour": 11}
    
    def test_no_mornings(self):
        constraint = parse_constraint("no mornings please")
        assert constraint == {"type": "after", "hour": 12}
    
    def test_afternoon_only(self):
        constraint = parse_constraint("afternoon only")
        assert constraint == {"type": "after", "hour": 12}
    
    def test_empty_constraint(self):
        constraint = parse_constraint("")
        assert constraint == {}
    
    def test_none_constraint(self):
        constraint = parse_constraint(None)
        assert constraint == {}


class TestApplyConstraints:
    """Test constraint application to slots."""
    
    def test_after_constraint_filters(self):
        slots = [
            TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),  # 2pm - OK
            TimeSlot(day="Monday", start_time="17:00", end_time="19:00"),  # 5pm - FILTER
            TimeSlot(day="Monday", start_time="19:00", end_time="21:00"),  # 7pm - OK
        ]
        
        participants = [
            Participant(name="Alice", constraints="must be after 6pm")
        ]
        
        filtered = apply_constraints(slots, participants)
        assert len(filtered) == 1
        assert filtered[0].start_time == "19:00"
    
    def test_before_constraint_filters(self):
        slots = [
            TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),  # ends 4pm - OK
            TimeSlot(day="Monday", start_time="16:00", end_time="18:00"),  # ends 6pm - FILTER
        ]
        
        participants = [
            Participant(name="Bob", constraints="must be before 5pm")
        ]
        
        filtered = apply_constraints(slots, participants)
        assert len(filtered) == 1
        assert filtered[0].start_time == "14:00"
    
    def test_multiple_participants_constraints(self):
        slots = [
            TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),  # 2pm-4pm
            TimeSlot(day="Monday", start_time="18:00", end_time="20:00"),  # 6pm-8pm
        ]
        
        participants = [
            Participant(name="Alice", constraints="must be after 5pm"),
            Participant(name="Bob", constraints="must be before 7pm")
        ]
        
        # Only 6pm-8pm satisfies both (after 5pm, but... wait, it ends at 8pm)
        # Actually Bob's constraint "before 7pm" means END before 7pm
        # So 6pm-8pm should be filtered out
        filtered = apply_constraints(slots, participants)
        assert len(filtered) == 0  # Conflicting constraints
    
    def test_no_constraints(self):
        slots = [
            TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),
            TimeSlot(day="Monday", start_time="18:00", end_time="20:00"),
        ]
        
        participants = [
            Participant(name="Alice"),
            Participant(name="Bob")
        ]
        
        filtered = apply_constraints(slots, participants)
        assert len(filtered) == 2  # All slots pass
