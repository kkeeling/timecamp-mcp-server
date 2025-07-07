#!/usr/bin/env python3
"""
Unit tests for TimeCamp MCP Server
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json
import sys

# Import our server components
from server import (
    SimpleCache, TimeCampClient, format_duration,
    get_cached_projects, get_cached_tasks
)
from fastmcp.exceptions import McpError, ToolError
from models import (
    DailySummaryResponse, DailySummaryEntry, TimerStatusResponse
)

class TestSimpleCache:
    """Test the caching functionality"""
    
    def test_cache_set_and_get(self):
        cache = SimpleCache()
        etag = cache.set("test_key", "test_value", ttl=5)
        value, returned_etag, not_modified = cache.get("test_key")
        assert value == "test_value"
        assert returned_etag == etag
        assert not_modified is False
    
    def test_cache_expiry(self):
        cache = SimpleCache()
        cache.set("test_key", "test_value", ttl=0)
        # Sleep briefly to ensure expiry
        import time
        time.sleep(0.1)
        value, etag, not_modified = cache.get("test_key")
        assert value is None
        assert etag is None
        assert not_modified is False
    
    def test_cache_clear(self):
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        value1, _, _ = cache.get("key1")
        value2, _, _ = cache.get("key2")
        assert value1 is None
        assert value2 is None
    
    def test_cache_etag_support(self):
        cache = SimpleCache()
        etag = cache.set("test_key", "test_value")
        
        # Test with matching ETag (304 Not Modified)
        value, returned_etag, not_modified = cache.get("test_key", etag)
        assert value is None  # No value returned for 304
        assert returned_etag == etag
        assert not_modified is True
        
        # Test with different ETag
        value, returned_etag, not_modified = cache.get("test_key", "different-etag")
        assert value == "test_value"
        assert returned_etag == etag
        assert not_modified is False
    
    def test_cache_invalidation(self):
        cache = SimpleCache()
        cache.set("test_key", "test_value")
        cache.set("other_key", "other_value")
        
        # Test specific invalidation
        cache.invalidate("test_key")
        value1, _, _ = cache.get("test_key")
        value2, _, _ = cache.get("other_key")
        assert value1 is None
        assert value2 == "other_value"
        

class TestTimeCampClient:
    """Test the API client"""
    
    @pytest.mark.asyncio
    async def test_successful_request(self):
        client = TimeCampClient("test_token")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"success": true}'
            mock_response.json.return_value = {"success": True}
            mock_response.raise_for_status = Mock()
            
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await client.request('GET', 'test_endpoint')
            assert result == {"success": True}
    
    @pytest.mark.asyncio
    async def test_401_error(self):
        client = TimeCampClient("invalid_token")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            # Create proper HTTPStatusError
            import httpx
            error = httpx.HTTPStatusError("401 error", request=Mock(), response=mock_response)
            mock_response.raise_for_status.side_effect = error
            
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with pytest.raises(ToolError) as exc_info:
                await client.request('GET', 'test_endpoint')
            assert "Invalid API token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_429_error(self):
        client = TimeCampClient("test_token")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 429
            # Create proper HTTPStatusError
            import httpx
            error = httpx.HTTPStatusError("429 error", request=Mock(), response=mock_response)
            mock_response.raise_for_status.side_effect = error
            
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with pytest.raises(ToolError) as exc_info:
                await client.request('GET', 'test_endpoint')
            assert "Rate limit exceeded" in str(exc_info.value)

class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_format_duration(self):
        assert format_duration(0) == "0m"
        assert format_duration(60) == "1m"
        assert format_duration(90) == "1m"
        assert format_duration(3600) == "1h 0m"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(7320) == "2h 2m"
    
    @pytest.mark.asyncio
    async def test_get_cached_projects(self):
        # Mock client
        mock_client = AsyncMock()
        mock_client.request.return_value = {
            "1": {"name": "Project 1", "color": "#FF0000"},
            "2": {"name": "Project 2", "color": "#00FF00"}
        }
        
        # First call should hit API
        projects = await get_cached_projects(mock_client)
        assert len(projects) == 2
        assert projects[0]['id'] == 1
        assert projects[0]['name'] == "Project 1"
        
        # Verify API was called
        mock_client.request.assert_called_once_with('GET', 'projects')
    
    @pytest.mark.asyncio
    async def test_get_cached_tasks(self):
        # Mock client
        mock_client = AsyncMock()
        mock_client.request.return_value = {
            "100": {"name": "Task 1", "project_id": 1},
            "101": {"name": "Task 2", "project_id": 1}
        }
        
        # First call should hit API
        tasks = await get_cached_tasks(mock_client)
        assert len(tasks) == 2
        assert tasks[0]['id'] == 100
        assert tasks[0]['name'] == "Task 1"
        
        # Verify API was called
        mock_client.request.assert_called_once_with('GET', 'tasks')

class TestFuzzySearch:
    """Test fuzzy search functionality"""
    
    def test_rapidfuzz_import(self):
        """Ensure rapidfuzz is properly imported"""
        from rapidfuzz import fuzz, process
        assert fuzz is not None
        assert process is not None
    
    def test_fuzzy_matching(self):
        """Test basic fuzzy matching"""
        from rapidfuzz import fuzz
        
        # Exact match
        assert fuzz.ratio("hello", "hello") == 100.0
        
        # Close match
        score = fuzz.ratio("hello", "helo")
        assert score > 80
        
        # Poor match
        score = fuzz.ratio("hello", "world")
        assert score < 50

class TestMCPTools:
    """Test the MCP tool functions"""
    
    @pytest.mark.asyncio
    async def test_start_timer_success(self):
        """Test successful timer start"""
        from server import start_timer
        
        # Access the underlying function from the FunctionTool
        start_timer_fn = start_timer.fn if hasattr(start_timer, 'fn') else start_timer
        
        # Mock get_api_token
        with patch('server.get_api_token', return_value='test_token'):
            # Mock TimeCampClient
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock timer check - no timer running
                mock_client.request.side_effect = [
                    {},  # No timer running
                    {'timer_id': 123, 'new_timer_id': 123}  # Start timer response
                ]
                
                # Mock get_cached_tasks
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 456, 'name': 'Test Task', 'project_id': 1}
                ]):
                    result = await start_timer_fn(456, "Working on feature")
                    
                    assert "Timer started" in result.message
                    assert result.timer_id == 123
                    assert result.task_id == 456
                    assert result.task_name == 'Test Task'
    
    @pytest.mark.asyncio
    async def test_start_timer_already_running(self):
        """Test timer start when timer already running"""
        from server import start_timer
        
        # Access the underlying function from the FunctionTool
        start_timer_fn = start_timer.fn if hasattr(start_timer, 'fn') else start_timer
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock timer check - timer already running
                mock_client.request.return_value = {
                    'timer_id': 999,
                    'name': 'Existing Task'
                }
                
                with pytest.raises(ToolError) as exc_info:
                    await start_timer_fn(456, "New work")
                
                assert "Timer already running" in str(exc_info.value)
                assert "999" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_stop_timer_success(self):
        """Test successful timer stop"""
        from server import stop_timer
        
        # Access the underlying function from the FunctionTool
        stop_timer_fn = stop_timer.fn if hasattr(stop_timer, 'fn') else stop_timer
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock timer check and stop
                mock_client.request.side_effect = [
                    {  # Timer is running
                        'timer_id': 123,
                        'name': 'Test Task',
                        'started_at': datetime.now().isoformat()
                    },
                    {}  # Stop response
                ]
                
                result = await stop_timer_fn()
                
                assert "Timer stopped" in result.message
                assert result.task_name == 'Test Task'
                assert result.duration is not None
                assert result.timer_id is not None
    
    @pytest.mark.asyncio
    async def test_stop_timer_not_running(self):
        """Test stop timer when no timer running"""
        from server import stop_timer
        
        # Access the underlying function from the FunctionTool
        stop_timer_fn = stop_timer.fn if hasattr(stop_timer, 'fn') else stop_timer
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock timer check - no timer running
                mock_client.request.return_value = {}
                
                with pytest.raises(ToolError) as exc_info:
                    await stop_timer_fn()
                
                assert "No timer is currently running" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_timer_resource(self):
        """Test timer resource"""
        from server import get_timer_resource
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                start_time = datetime.now() - timedelta(hours=1, minutes=30)
                mock_client.request.return_value = {
                    'timer_id': 123,
                    'name': 'Test Task',
                    'task_id': 456,
                    'project_name': 'Test Project',
                    'started_at': start_time.isoformat()
                }
                
                result = await get_timer_resource.fn()
                
                assert result.is_running is True
                assert result.task_name == 'Test Task'
                assert result.task_id == 456
                assert result.project_name == 'Test Project'
                assert '1h 30m' in result.elapsed_time
    
    
    @pytest.mark.asyncio
    async def test_create_time_entry_success(self):
        """Test creating manual time entry"""
        from server import create_time_entry
        
        # Access the underlying function from the FunctionTool
        create_time_entry_fn = create_time_entry.fn if hasattr(create_time_entry, 'fn') else create_time_entry
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                mock_client.request.return_value = {'entry_id': 999, 'id': 999}
                
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 456, 'name': 'Test Task', 'project_id': 1}
                ]):
                    with patch('server.get_cached_projects', return_value=[
                        {'id': 1, 'name': 'Test Project'}
                    ]):
                        result = await create_time_entry_fn(
                            456, "2025-01-03", "14:00", "16:30", "Fixed bugs"
                        )
                        
                        assert result.entry_id == 999
                        assert result.duration == '2h 30m'
                        assert result.task_name == 'Test Task'
                        assert result.project_name == 'Test Project'
                        assert result.task_id == 456
    
    @pytest.mark.asyncio
    async def test_create_time_entry_invalid_time(self):
        """Test creating time entry with invalid times"""
        from server import create_time_entry
        
        # Access the underlying function from the FunctionTool
        create_time_entry_fn = create_time_entry.fn if hasattr(create_time_entry, 'fn') else create_time_entry
        
        with patch('server.get_api_token', return_value='test_token'):
            with pytest.raises(ToolError) as exc_info:
                await create_time_entry_fn(
                    456, "2025-01-03", "16:00", "14:00", "Note"
                )
            
            assert "End time must be after start time" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_time_entries_resource(self):
        """Test time entries resource"""
        from server import get_time_entries_resource
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.TimeCampClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock today's entries
                mock_client.request.return_value = {
                    '1': {'duration': 3600, 'task_id': 100, 'note': 'Morning work'},
                    '2': {'duration': 7200, 'task_id': 100, 'note': 'Afternoon work'},
                    '3': {'duration': 1800, 'task_id': 101, 'note': ''}
                }
                
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 100, 'name': 'Development', 'project_id': 1},
                    {'id': 101, 'name': 'Testing', 'project_id': 1}
                ]):
                    with patch('server.get_cached_projects', return_value=[
                        {'id': 1, 'name': 'Main Project'}
                    ]):
                        # Test for a specific date (not today to avoid timer check)
                        result = await get_time_entries_resource.fn("2025-01-01")
                        
                        assert result.total_time == '3h 30m'  # 3600 + 7200 + 1800
                        assert len(result.entries) == 2
                        assert result.is_timer_running is False
    
    @pytest.mark.asyncio
    async def test_projects_resource(self):
        """Test projects resource"""
        from server import get_projects_resource
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.get_cached_projects', return_value=[
                {'id': 1, 'name': 'Project A', 'archived': '0', 'color': '#FF0000'},
                {'id': 2, 'name': 'Project B', 'archived': '0', 'color': '#00FF00'},
                {'id': 3, 'name': 'Archived Project', 'archived': '1', 'color': '#0000FF'}
            ]):
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 100, 'project_id': 1},
                    {'id': 101, 'project_id': 1},
                    {'id': 102, 'project_id': 2}
                ]):
                    result = await get_projects_resource.fn()
                    
                    # Resources return all projects including archived
                    assert len(result.projects) == 3
                    assert result.total_count == 3
                    
                    # Projects are sorted by name: Archived Project, Project A, Project B
                    assert result.projects[0].name == 'Archived Project'
                    assert result.projects[0].tasks_count == 0
                    assert result.projects[0].archived is True
                    
                    assert result.projects[1].name == 'Project A'
                    assert result.projects[1].tasks_count == 2
                    
                    assert result.projects[2].name == 'Project B'
                    assert result.projects[2].tasks_count == 1
    
    @pytest.mark.asyncio
    async def test_tasks_resource(self):
        """Test tasks resource"""
        from server import get_tasks_resource
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.get_cached_tasks', return_value=[
                {'id': 100, 'name': 'Task 1', 'project_id': 1, 'archived': '0'},
                {'id': 101, 'name': 'Task 2', 'project_id': 1, 'archived': '0'},
                {'id': 102, 'name': 'Archived Task', 'project_id': 2, 'archived': '1'}
            ]):
                with patch('server.get_cached_projects', return_value=[
                    {'id': 1, 'name': 'Project A'},
                    {'id': 2, 'name': 'Project B'}
                ]):
                    result = await get_tasks_resource.fn()
                    
                    # All tasks including archived
                    assert len(result) == 3
                    
                    # Check enriched data
                    assert result[0]['id'] == 100
                    assert result[0]['name'] == 'Task 1'
                    assert result[0]['project_name'] == 'Project A'
                    assert result[0]['archived'] is False
                    
                    assert result[2]['archived'] is True
    
    @pytest.mark.asyncio
    async def test_search_resource(self):
        """Test search resource"""
        from server import search_resource
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.get_cached_projects', return_value=[
                {'id': 1, 'name': 'Web Development', 'archived': '0'},
                {'id': 2, 'name': 'Mobile App', 'archived': '0'},
                {'id': 3, 'name': 'Archived Project', 'archived': '1'}
            ]):
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 100, 'name': 'Frontend Development', 'project_id': 1, 'archived': '0'},
                    {'id': 101, 'name': 'Backend API', 'project_id': 1, 'archived': '0'},
                    {'id': 102, 'name': 'Mobile UI', 'project_id': 2, 'archived': '0'}
                ]):
                    # Test search for "Frontend" which should find a task
                    result = await search_resource.fn("Frontend")
                    
                    assert result.total_results > 0
                    assert result.query == "Frontend"
                    
                    # Should find the Frontend Development task
                    found_items = [(r.type, r.name) for r in result.results]
                    assert ('task', 'Frontend Development') in found_items
                    
                    # Test search for "Web" which should find a project
                    result = await search_resource.fn("Web")
                    assert result.total_results > 0
                    found_items = [(r.type, r.name) for r in result.results]
                    assert ('project', 'Web Development') in found_items
                    
                    # Should not include archived items
                    result = await search_resource.fn("Archived")
                    assert result.total_results == 0  # Archived items are filtered out

class TestMCPPrompts:
    """Test the MCP prompt functions"""
    
    @pytest.mark.asyncio
    async def test_daily_standup_prompt(self):
        """Test daily standup prompt generation"""
        from server import daily_standup_prompt, get_time_entries_resource
        
        # Mock the resource function
        mock_entries = DailySummaryResponse(
            date="2025-01-07",
            total_time="4h 30m",
            total_seconds=16200,
            entries=[
                DailySummaryEntry(
                    task_name="Development",
                    task_id=100,
                    project_name="Project A",
                    duration="3h 0m",
                    duration_seconds=10800,
                    notes=["Fixed bug", "Added feature"]
                ),
                DailySummaryEntry(
                    task_name="Testing",
                    task_id=101,
                    project_name="Project A",
                    duration="1h 30m",
                    duration_seconds=5400,
                    notes=[]
                )
            ],
            entry_count=2,
            is_timer_running=True,
            current_task="Code Review",
            current_task_id=102
        )
        
        with patch.object(get_time_entries_resource, 'fn', return_value=mock_entries):
            result = await daily_standup_prompt.fn("2025-01-07")
            
            assert "Daily Standup for 2025-01-07" in result
            assert "Total time tracked: 4h 30m" in result
            assert "Development (Project A): 3h 0m - Fixed bug; Added feature" in result
            assert "Testing (Project A): 1h 30m" in result
            assert "Currently working on: Code Review" in result
    
    @pytest.mark.asyncio
    async def test_weekly_report_prompt(self):
        """Test weekly report prompt generation"""
        from server import weekly_report_prompt, get_time_entries_resource
        
        # Mock entries for multiple days
        def mock_get_entries(date):
            if date == "2025-01-06":  # Monday
                return DailySummaryResponse(
                    date=date,
                    total_time="8h 0m",
                    total_seconds=28800,
                    entries=[
                        DailySummaryEntry(
                            task_name="Development",
                            task_id=100,
                            project_name="Project A",
                            duration="8h 0m",
                            duration_seconds=28800,
                            notes=[]
                        )
                    ],
                    entry_count=1,
                    is_timer_running=False
                )
            elif date == "2025-01-07":  # Tuesday
                return DailySummaryResponse(
                    date=date,
                    total_time="6h 0m",
                    total_seconds=21600,
                    entries=[
                        DailySummaryEntry(
                            task_name="Testing",
                            task_id=101,
                            project_name="Project B",
                            duration="6h 0m",
                            duration_seconds=21600,
                            notes=[]
                        )
                    ],
                    entry_count=1,
                    is_timer_running=False
                )
            else:
                return DailySummaryResponse(
                    date=date,
                    total_time="0m",
                    total_seconds=0,
                    entries=[],
                    entry_count=0,
                    is_timer_running=False
                )
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch.object(get_time_entries_resource, 'fn', side_effect=mock_get_entries):
                result = await weekly_report_prompt.fn("2025-01-06")
            
            assert "Weekly Time Report" in result
            assert "Week of 2025-01-06" in result
            assert "Total time tracked: 14h 0m" in result  # 8 + 6 hours
            assert "Monday (2025-01-06): 8h 0m" in result
            assert "Tuesday (2025-01-07): 6h 0m" in result
            assert "Project A: 8h 0m" in result
            assert "Project B: 6h 0m" in result
    
    @pytest.mark.asyncio
    async def test_time_tracking_insights_prompt(self):
        """Test time tracking insights prompt"""
        from server import time_tracking_insights_prompt, get_time_entries_resource, get_timer_resource
        
        # Mock today's entries
        today_entries = DailySummaryResponse(
            date="2025-01-07",
            total_time="2h 0m",
            total_seconds=7200,
            entries=[
                DailySummaryEntry(
                    task_name="Morning work",
                    task_id=100,
                    project_name="Project A",
                    duration="2h 0m",
                    duration_seconds=7200,
                    notes=[]
                )
            ],
            entry_count=1,
            is_timer_running=False
        )
        
        # Mock yesterday's entries  
        yesterday_entries = DailySummaryResponse(
            date="2025-01-06",
            total_time="8h 0m",
            total_seconds=28800,
            entries=[],
            entry_count=3,
            is_timer_running=False
        )
        
        # Mock timer status
        timer_status = TimerStatusResponse(
            is_running=False,
            message="No timer running"
        )
        
        def mock_get_entries(date):
            if "2025-01-07" in date:
                return today_entries
            else:
                return yesterday_entries
        
        # Mock datetime.now() to return a fixed date
        with patch('server.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 7, 10, 0, 0)
            mock_datetime.strptime = datetime.strptime  # Keep strptime working
            
            with patch.object(get_time_entries_resource, 'fn', side_effect=mock_get_entries):
                with patch.object(get_timer_resource, 'fn', return_value=timer_status):
                    result = await time_tracking_insights_prompt.fn()
                
                assert "Time Tracking Insights" in result
                assert "Today's tracked time: 2h 0m" in result
                assert "No timer currently running" in result
                assert "Yesterday's total: 8h 0m" in result
                assert "You're tracking less time than yesterday" in result

class TestStateTracking:
    """Test state change tracking functionality"""
    
    @pytest.mark.asyncio
    async def test_state_changes_resource(self):
        """Test state changes resource"""
        from server import get_state_changes_resource, state_tracker
        
        # Clear any existing changes
        state_tracker.clear()
        
        # Record some changes
        state_tracker.record_change("timer_started", {
            "task_id": 100,
            "task_name": "Test Task",
            "timer_id": 999
        })
        
        state_tracker.record_change("timer_stopped", {
            "task_id": 100,
            "duration_seconds": 3600
        })
        
        # Get changes via resource
        result = await get_state_changes_resource.fn()
        
        assert "changes" in result
        assert "timestamp" in result
        assert len(result["changes"]) == 2
        
        # Check first change
        assert result["changes"][0]["type"] == "timer_started"
        assert result["changes"][0]["details"]["task_id"] == 100
        
        # Check second change
        assert result["changes"][1]["type"] == "timer_stopped"
        assert result["changes"][1]["details"]["duration_seconds"] == 3600
    
    def test_state_tracker_max_changes(self):
        """Test that state tracker limits stored changes"""
        from server import StateTracker
        
        tracker = StateTracker()
        tracker._max_changes = 5  # Set a small limit for testing
        
        # Add more changes than the limit
        for i in range(10):
            tracker.record_change("test_change", {"index": i})
        
        changes = tracker.get_changes_since()
        assert len(changes) == 5
        assert changes[0]["details"]["index"] == 5  # Oldest retained
        assert changes[4]["details"]["index"] == 9  # Newest
    
    def test_state_tracker_filter_by_timestamp(self):
        """Test filtering changes by timestamp"""
        from server import StateTracker
        import time
        
        tracker = StateTracker()
        
        # Record a change
        tracker.record_change("old_change", {"data": "old"})
        time.sleep(0.1)
        
        # Get current time
        filter_time = datetime.now()
        time.sleep(0.1)
        
        # Record newer changes
        tracker.record_change("new_change", {"data": "new"})
        
        # Get only new changes
        new_changes = tracker.get_changes_since(filter_time)
        assert len(new_changes) == 1
        assert new_changes[0]["type"] == "new_change"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])