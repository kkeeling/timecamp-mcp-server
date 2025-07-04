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

class TestSimpleCache:
    """Test the caching functionality"""
    
    def test_cache_set_and_get(self):
        cache = SimpleCache()
        cache.set("test_key", "test_value", ttl=5)
        assert cache.get("test_key") == "test_value"
    
    def test_cache_expiry(self):
        cache = SimpleCache()
        cache.set("test_key", "test_value", ttl=0)
        # Sleep briefly to ensure expiry
        import time
        time.sleep(0.1)
        assert cache.get("test_key") is None
    
    def test_cache_clear(self):
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

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
            
            with pytest.raises(Exception) as exc_info:
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
            
            with pytest.raises(Exception) as exc_info:
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
                    
                    assert result['success'] is True
                    assert "Timer started" in result['message']
                    assert result['timer_id'] == 123
    
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
                
                result = await start_timer_fn(456, "New work")
                
                assert result['success'] is False
                assert "Timer already running" in result['error']
                assert result['current_timer_id'] == 999
    
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
                
                assert result['success'] is True
                assert "Timer stopped" in result['message']
                assert result['task_name'] == 'Test Task'
    
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
                
                result = await stop_timer_fn()
                
                assert result['success'] is False
                assert "No timer is currently running" in result['error']
    
    @pytest.mark.asyncio
    async def test_get_timer_status_running(self):
        """Test get timer status when timer is running"""
        from server import get_timer_status
        
        # Access the underlying function from the FunctionTool
        get_timer_status_fn = get_timer_status.fn if hasattr(get_timer_status, 'fn') else get_timer_status
        
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
                
                result = await get_timer_status_fn()
                
                assert result['is_running'] is True
                assert result['task_name'] == 'Test Task'
                assert result['task_id'] == 456
                assert result['project_name'] == 'Test Project'
                assert '1h 30m' in result['elapsed_time']
    
    @pytest.mark.asyncio
    async def test_search_projects_and_tasks(self):
        """Test fuzzy search functionality"""
        from server import search_projects_and_tasks
        
        # Access the underlying function from the FunctionTool
        search_projects_and_tasks_fn = search_projects_and_tasks.fn if hasattr(search_projects_and_tasks, 'fn') else search_projects_and_tasks
        
        with patch('server.get_api_token', return_value='test_token'):
            with patch('server.get_cached_projects', return_value=[
                {'id': 1, 'name': 'Web Development', 'archived': '0'},
                {'id': 2, 'name': 'Mobile App', 'archived': '0'}
            ]):
                with patch('server.get_cached_tasks', return_value=[
                    {'id': 100, 'name': 'User Authentication', 'project_id': 1, 'archived': '0'},
                    {'id': 101, 'name': 'Database Design', 'project_id': 1, 'archived': '0'},
                    {'id': 102, 'name': 'UI Design', 'project_id': 2, 'archived': '0'}
                ]):
                    # Try searching for "authentication" to get a better match
                    result = await search_projects_and_tasks_fn("authentication")
                    
                    assert 'results' in result
                    assert len(result['results']) > 0
                    # Should find "User Authentication" as top result when searching for full word
                    assert result['results'][0]['name'] == 'User Authentication'
                    assert result['results'][0]['type'] == 'task'
    
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
                        
                        assert result['success'] is True
                        assert result['entry_id'] == 999
                        assert result['duration'] == '2h 30m'
                        assert result['task_name'] == 'Test Task'
    
    @pytest.mark.asyncio
    async def test_create_time_entry_invalid_time(self):
        """Test creating time entry with invalid times"""
        from server import create_time_entry
        
        # Access the underlying function from the FunctionTool
        create_time_entry_fn = create_time_entry.fn if hasattr(create_time_entry, 'fn') else create_time_entry
        
        with patch('server.get_api_token', return_value='test_token'):
            result = await create_time_entry_fn(
                456, "2025-01-03", "16:00", "14:00", "Note"
            )
            
            assert result['success'] is False
            assert "End time must be after start time" in result['error']
    
    @pytest.mark.asyncio
    async def test_get_today_summary(self):
        """Test getting today's summary"""
        from server import get_today_summary
        
        # Access the underlying function from the FunctionTool
        get_today_summary_fn = get_today_summary.fn if hasattr(get_today_summary, 'fn') else get_today_summary
        
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
                
                # Create a proper async mock for get_timer_status
                mock_get_timer_status = AsyncMock(return_value={'is_running': False})
                # Patch the function at module level
                with patch.object(sys.modules['server'], 'get_timer_status', mock_get_timer_status):
                    with patch('server.get_cached_tasks', return_value=[
                        {'id': 100, 'name': 'Development', 'project_id': 1},
                        {'id': 101, 'name': 'Testing', 'project_id': 1}
                    ]):
                        with patch('server.get_cached_projects', return_value=[
                            {'id': 1, 'name': 'Main Project'}
                        ]):
                            result = await get_today_summary_fn()
                            
                            # Check if it's an error response
                            if 'success' in result and not result['success']:
                                print(f"Error in get_today_summary: {result}")
                            
                            assert 'total_time' in result, f"Result structure: {result}"
                            assert result['total_time'] == '3h 30m'  # 3600 + 7200 + 1800
                            assert len(result['entries']) == 2
                            assert result['is_timer_running'] is False
    
    @pytest.mark.asyncio
    async def test_list_projects(self):
        """Test listing projects"""
        from server import list_projects
        
        # Access the underlying function from the FunctionTool
        list_projects_fn = list_projects.fn if hasattr(list_projects, 'fn') else list_projects
        
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
                    # Test without archived
                    result = await list_projects_fn(include_archived=False)
                    
                    assert len(result['projects']) == 2
                    assert result['total_count'] == 2
                    assert result['projects'][0]['tasks_count'] == 2
                    assert result['projects'][1]['tasks_count'] == 1
                    
                    # Test with archived
                    result = await list_projects_fn(include_archived=True)
                    assert len(result['projects']) == 3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])