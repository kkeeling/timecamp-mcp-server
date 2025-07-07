#!/usr/bin/env python3
"""
Test Pydantic validation for TimeCamp MCP Server
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from models import (
    StartTimerRequest, CreateTimeEntryRequest, SearchRequest, ListProjectsRequest,
    TimerResponse, StopTimerResponse, TimerStatusResponse, SearchResponse,
    TimeEntryResponse, DailySummaryResponse, ProjectListResponse,
    SearchResultItem, DailySummaryEntry, ProjectInfo
)


class TestRequestValidation:
    """Test request model validation"""
    
    def test_start_timer_request_valid(self):
        """Test valid StartTimerRequest"""
        request = StartTimerRequest(task_id=123, note="Working on feature")
        assert request.task_id == 123
        assert request.note == "Working on feature"
        
        # Test with empty note
        request = StartTimerRequest(task_id=456, note="")
        assert request.task_id == 456
        assert request.note == ""
    
    def test_start_timer_request_invalid(self):
        """Test invalid StartTimerRequest"""
        # Invalid task_id (must be positive)
        with pytest.raises(ValidationError) as exc_info:
            StartTimerRequest(task_id=0, note="Test")
        assert "greater than 0" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            StartTimerRequest(task_id=-1, note="Test")
        assert "greater than 0" in str(exc_info.value)
        
        # Note too long
        with pytest.raises(ValidationError) as exc_info:
            StartTimerRequest(task_id=123, note="x" * 1001)
        assert "at most 1000 characters" in str(exc_info.value)
    
    def test_create_time_entry_request_valid(self):
        """Test valid CreateTimeEntryRequest"""
        request = CreateTimeEntryRequest(
            task_id=123,
            date="2025-01-03",
            start_time="14:00",
            end_time="16:30",
            note="Worked on API"
        )
        assert request.task_id == 123
        assert request.date == "2025-01-03"
        assert request.start_time == "14:00"
        assert request.end_time == "16:30"
        assert request.note == "Worked on API"
    
    def test_create_time_entry_request_invalid(self):
        """Test invalid CreateTimeEntryRequest"""
        # Invalid date format
        with pytest.raises(ValidationError) as exc_info:
            CreateTimeEntryRequest(
                task_id=123,
                date="01/03/2025",  # Wrong format
                start_time="14:00",
                end_time="16:30"
            )
        assert "String should match pattern" in str(exc_info.value)
        
        # Invalid time format
        with pytest.raises(ValidationError) as exc_info:
            CreateTimeEntryRequest(
                task_id=123,
                date="2025-01-03",
                start_time="2:00 PM",  # Wrong format
                end_time="16:30"
            )
        assert "String should match pattern" in str(exc_info.value)
        
        # End time before start time
        with pytest.raises(ValidationError) as exc_info:
            CreateTimeEntryRequest(
                task_id=123,
                date="2025-01-03",
                start_time="16:00",
                end_time="14:00"  # Before start
            )
        assert "End time must be after start time" in str(exc_info.value)
    
    def test_search_request_valid(self):
        """Test valid SearchRequest"""
        request = SearchRequest(query="project management")
        assert request.query == "project management"
    
    def test_search_request_invalid(self):
        """Test invalid SearchRequest"""
        # Empty query
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="")
        assert "at least 1 character" in str(exc_info.value)
        
        # Query too long
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="x" * 201)
        assert "at most 200 characters" in str(exc_info.value)


class TestResponseValidation:
    """Test response model validation"""
    
    def test_timer_response(self):
        """Test TimerResponse model"""
        response = TimerResponse(
            message="Timer started",
            timer_id=123,
            task_id=456,
            task_name="Development",
            started_at="2025-01-03T14:00:00"
        )
        assert response.timer_id == 123
        assert response.task_id == 456
        assert response.task_name == "Development"
    
    def test_search_result_item(self):
        """Test SearchResultItem validation"""
        # Valid project
        item = SearchResultItem(
            type="project",
            id=123,
            name="Web Development",
            match_score=0.95
        )
        assert item.type == "project"
        assert item.match_score == 0.95
        
        # Valid task with project
        item = SearchResultItem(
            type="task",
            id=456,
            name="User Authentication",
            match_score=0.8,
            project_name="Web Development"
        )
        assert item.type == "task"
        assert item.project_name == "Web Development"
        
        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            SearchResultItem(
                type="invalid",
                id=123,
                name="Test",
                match_score=0.5
            )
        assert "String should match pattern" in str(exc_info.value)
        
        # Invalid match score
        with pytest.raises(ValidationError) as exc_info:
            SearchResultItem(
                type="project",
                id=123,
                name="Test",
                match_score=1.5  # Must be 0-1
            )
        assert "less than or equal to 1" in str(exc_info.value)
    
    def test_daily_summary_entry(self):
        """Test DailySummaryEntry model"""
        entry = DailySummaryEntry(
            task_name="Development",
            task_id=123,
            project_name="Web App",
            duration="2h 30m",
            notes=["Fixed bug", "Updated API"]
        )
        assert entry.task_id == 123
        assert len(entry.notes) == 2
        
        # Empty notes list
        entry = DailySummaryEntry(
            task_name="Testing",
            task_id=456,
            project_name="Mobile App",
            duration="1h 0m"
        )
        assert entry.notes == []
    
    def test_project_info(self):
        """Test ProjectInfo model"""
        project = ProjectInfo(
            id=123,
            name="Web Development",
            color="#FF5733",
            tasks_count=15,
            archived=False
        )
        assert project.id == 123
        assert project.color == "#FF5733"
        assert project.tasks_count == 15
        assert project.archived is False
        
        # Default values
        project = ProjectInfo(
            id=456,
            name="Mobile App",
            tasks_count=0
        )
        assert project.color == "#4CAF50"  # Default
        assert project.archived is False  # Default
        
        # Invalid tasks count
        with pytest.raises(ValidationError) as exc_info:
            ProjectInfo(
                id=123,
                name="Test",
                tasks_count=-1  # Must be >= 0
            )
        assert "greater than or equal to 0" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])