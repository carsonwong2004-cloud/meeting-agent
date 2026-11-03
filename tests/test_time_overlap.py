import pytest
from models import TimeSlot, Participant
from utils.time_overlap import (
    time_to_minutes,
    minutes_to_time,
    check_time_overlap,
    find_common_slots
)


class TestTimeConversion:
    """Test time conversion utilities."""
    
    def test_time_to_minutes(self):
        assert time_to_minutes("00:00") == 0
        assert time_to_minutes("12:00") == 720
        assert time_to_minutes("14:30") == 870
        assert time_to_minutes("23:59") == 1439
    
    def test_minutes_to_time(self):
        assert minutes_to_time(0) == "00:00"
        assert minutes_to_time(720) == "12:00"
        assert minutes_to_time(870) == "14:30"
        assert minutes_to_time(1439) == "23:59"
    
    def test_roundtrip(self):
        times = ["00:00", "08:30", "14:45", "23:59"]
        for t in times:
            assert minutes_to_time(time_to_minutes(t)) == t


class TestCheckTimeOverlap:
    """Test time overlap detection."""
    
    def test_full_overlap(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        overlap = check_time_overlap(slot1, slot2)
        assert overlap == ("14:00", "16:00")
    
    def test_partial_overlap(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Monday", start_time="15:00", end_time="17:00")
        overlap = check_time_overlap(slot1, slot2)
        assert overlap == ("15:00", "16:00")
    
    def test_no_overlap_same_day(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Monday", start_time="16:00", end_time="18:00")
        overlap = check_time_overlap(slot1, slot2)
        assert overlap is None
    
    def test_no_overlap_different_days(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="16:00")
        slot2 = TimeSlot(day="Tuesday", start_time="14:00", end_time="16:00")
        overlap = check_time_overlap(slot1, slot2)
        assert overlap is None
    
    def test_one_contains_other(self):
        slot1 = TimeSlot(day="Monday", start_time="14:00", end_time="18:00")
        slot2 = TimeSlot(day="Monday", start_time="15:00", end_time="16:00")
        overlap = check_time_overlap(slot1, slot2)
        assert overlap == ("15:00", "16:00")


class TestFindCommonSlots:
    """Test finding common availability."""
    
    def test_two_people_simple_overlap(self):
        p1 = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="16:00")]
        )
        p2 = Participant(
            name="Bob",
            free_slots=[TimeSlot(day="Monday", start_time="15:00", end_time="17:00")]
        )
        
        common = find_common_slots([p1, p2])
        assert len(common) == 1
        assert common[0].start_time == "15:00"
        assert common[0].end_time == "16:00"
    
    def test_two_people_no_overlap(self):
        p1 = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="16:00")]
        )
        p2 = Participant(
            name="Bob",
            free_slots=[TimeSlot(day="Tuesday", start_time="14:00", end_time="16:00")]
        )
        
        common = find_common_slots([p1, p2])
        assert len(common) == 0
    
    def test_three_people_overlap(self):
        p1 = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="18:00")]
        )
        p2 = Participant(
            name="Bob",
            free_slots=[TimeSlot(day="Monday", start_time="15:00", end_time="17:00")]
        )
        p3 = Participant(
            name="Carol",
            free_slots=[TimeSlot(day="Monday", start_time="16:00", end_time="19:00")]
        )
        
        common = find_common_slots([p1, p2, p3])
        assert len(common) == 1
        assert common[0].start_time == "16:00"
        assert common[0].end_time == "17:00"
    
    def test_minimum_duration_filter(self):
        p1 = Participant(
            name="Alice",
            free_slots=[TimeSlot(day="Monday", start_time="14:00", end_time="15:00")]
        )
        p2 = Participant(
            name="Bob",
            free_slots=[TimeSlot(day="Monday", start_time="14:30", end_time="16:00")]
        )
        
        # 30-minute overlap, should be filtered out (min 60 mins)
        common = find_common_slots([p1, p2], min_duration_minutes=60)
        assert len(common) == 0
        
        # Allow 30-minute meetings
        common = find_common_slots([p1, p2], min_duration_minutes=30)
        assert len(common) == 1
    
    def test_single_participant(self):
        p1 = Participant(
            name="Alice",
            free_slots=[
                TimeSlot(day="Monday", start_time="14:00", end_time="16:00"),
                TimeSlot(day="Tuesday", start_time="10:00", end_time="12:00")
            ]
        )
        
        common = find_common_slots([p1])
        assert len(common) == 2  # Returns all slots for single person
    
    def test_empty_participants(self):
        common = find_common_slots([])
        assert len(common) == 0
