#!/usr/bin/env python3
"""
TimeCamp MCP Server
A Model Context Protocol server for TimeCamp time tracking integration.
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx
from rapidfuzz import fuzz, process
from pydantic import ValidationError

# Import our models
from .models import (
    StartTimerRequest, CreateTimeEntryRequest,
    TimerResponse, StopTimerResponse, TimerStatusResponse,
    TimeEntryResponse, DailySummaryResponse, ProjectListResponse,
    DailySummaryEntry, ProjectInfo, SearchResponse, SearchResultItem
)

# Initialize FastMCP server
mcp = FastMCP("TimeCamp MCP Server")

# Cache configuration
CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # 5 minutes default

class SimpleCache:
    """Enhanced in-memory cache with TTL and ETag support"""
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float, str]] = {}  # value, expiry, etag
    
    def get(self, key: str, etag: Optional[str] = None) -> Tuple[Optional[Any], Optional[str], bool]:
        """Get value from cache if not expired.
        
        Returns:
            (value, etag, not_modified) tuple
            - value: The cached value or None
            - etag: The current ETag or None
            - not_modified: True if provided etag matches current etag
        """
        if key in self._cache:
            value, expiry, current_etag = self._cache[key]
            if datetime.now().timestamp() < expiry:
                # Check ETag match
                if etag and etag == current_etag:
                    return (None, current_etag, True)  # 304 Not Modified
                return (value, current_etag, False)
            else:
                del self._cache[key]
        return (None, None, False)
    
    def set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> str:
        """Set value in cache with TTL and generate ETag.
        
        Returns:
            Generated ETag for the cached value
        """
        expiry = datetime.now().timestamp() + ttl
        # Generate stable ETag using MD5 hash
        etag = f'"{hashlib.md5(str(value).encode()).hexdigest()}"'
        self._cache[key] = (value, expiry, etag)
        return etag
    
    def invalidate(self, key: str):
        """Invalidate a specific cache entry"""
        if key in self._cache:
            del self._cache[key]
    
    
    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()

# Global cache instance
cache = SimpleCache()

class TimeCampClient:
    """TimeCamp API client with error handling"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://www.timecamp.com/third_party/api"
        self.headers = {"Authorization": api_token}
    
    async def request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make API request with error handling"""
        url = f"{self.base_url}/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json() if response.text else {}
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ToolError("Invalid API token. Check TimeCamp settings") from e
                elif e.response.status_code == 404:
                    raise ToolError("Resource not found") from e
                elif e.response.status_code == 429:
                    raise ToolError("Rate limit exceeded. Wait 60 seconds") from e
                elif 500 <= e.response.status_code < 600:
                    raise ToolError("TimeCamp unavailable. Try again later") from e
                else:
                    raise ToolError(f"API error: {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise ToolError(f"Network error: {str(e)}") from e
            except Exception as e:
                raise ToolError(f"Unexpected error: {str(e)}") from e

def get_api_token() -> str:
    """Get API token from environment variable"""
    token = os.getenv('TIMECAMP_API_TOKEN')
    if not token:
        raise ToolError("TIMECAMP_API_TOKEN environment variable not set")
    return token

async def get_cached_projects(client: TimeCampClient) -> List[Dict]:
    """Get projects with caching"""
    cached_value, _, _ = cache.get('projects')
    if cached_value is not None:
        return cached_value
    
    projects = await client.request('GET', 'projects')
    # Convert dict response to list
    project_list = []
    for project_id, project_data in projects.items():
        if isinstance(project_data, dict):
            project_data['id'] = int(project_id)
            project_list.append(project_data)
    
    cache.set('projects', project_list)
    return project_list

async def get_cached_tasks(client: TimeCampClient) -> List[Dict]:
    """Get tasks with caching"""
    cached_value, _, _ = cache.get('tasks')
    if cached_value is not None:
        return cached_value
    
    tasks = await client.request('GET', 'tasks')
    # Convert dict response to list
    task_list = []
    for task_id, task_data in tasks.items():
        if isinstance(task_data, dict):
            task_data['id'] = int(task_id)
            task_list.append(task_data)
    
    cache.set('tasks', task_list)
    return task_list

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

# MCP Resources Implementation - Read-only operations

@mcp.resource("timecamp://projects")
async def get_projects_resource() -> ProjectListResponse:
    """Get all available projects (read-only resource)."""
    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    projects = await get_cached_projects(client)
    tasks = await get_cached_tasks(client)
    
    # Filter and format projects
    project_list = []
    for project in projects:
        if 'name' in project:
            # Count tasks for this project
            task_count = sum(1 for t in tasks if t.get('project_id') == project['id'])
            
            project_list.append(ProjectInfo(
                id=project['id'],
                name=project['name'],
                color=project.get('color', '#4CAF50'),
                tasks_count=task_count,
                archived=project.get('archived', '0') == '1'
            ))
    
    # Sort by name
    project_list.sort(key=lambda x: x.name)
    
    return ProjectListResponse(
        projects=project_list,
        total_count=len(project_list),
        include_archived=True  # Resources return all data
    )

@mcp.resource("timecamp://tasks")
async def get_tasks_resource() -> List[Dict[str, Any]]:
    """Get all available tasks (read-only resource)."""
    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    tasks = await get_cached_tasks(client)
    projects = await get_cached_projects(client)
    
    # Enrich tasks with project information
    enriched_tasks = []
    for task in tasks:
        if 'name' in task:
            project = next((p for p in projects if p['id'] == task.get('project_id')), None)
            enriched_task = {
                'id': task['id'],
                'name': task['name'],
                'project_id': task.get('project_id'),
                'project_name': project['name'] if project else 'No Project',
                'archived': task.get('archived', '0') == '1'
            }
            enriched_tasks.append(enriched_task)
    
    return enriched_tasks

@mcp.resource("timecamp://timer")
async def get_timer_resource() -> TimerStatusResponse:
    """Get current timer status (read-only resource)."""
    cache_key = "timer"
    cached_value, _, _ = cache.get(cache_key)
    if cached_value:
        return cached_value

    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    result = await client.request('GET', 'timer_running')
    
    if result and 'timer_id' in result:
        # Calculate elapsed time
        if 'started_at' in result:
            started = datetime.fromisoformat(result['started_at'].replace('Z', '+00:00'))
            elapsed = datetime.now() - started
            elapsed_str = format_duration(int(elapsed.total_seconds()))
            elapsed_seconds = int(elapsed.total_seconds())
        else:
            elapsed_str = "Unknown"
            elapsed_seconds = 0
        
        response = TimerStatusResponse(
            is_running=True,
            task_name=result.get('name', 'Unknown'),
            task_id=result.get('task_id'),
            timer_id=result.get('timer_id'),
            project_name=result.get('project_name', 'No Project'),
            elapsed_time=elapsed_str,
            elapsed_seconds=elapsed_seconds,
            start_time=result.get('started_at')
        )
    else:
        response = TimerStatusResponse(
            is_running=False,
            message="No timer is currently running"
        )
    
    # Cache for 60 seconds
    cache.set(cache_key, response, ttl=60)
    return response

@mcp.resource("timecamp://time-entries/{date}")
async def get_time_entries_resource(date: str) -> DailySummaryResponse:
    """Get time entries for a specific date (read-only resource)."""
    cache_key = f"time-entries/{date}"
    cached_value, _, _ = cache.get(cache_key)
    if cached_value:
        return cached_value

    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        raise ToolError("Invalid date format. Use YYYY-MM-DD") from e
    
    # Get entries for the date
    entries = await client.request('GET', f'time_entries?from={date}&to={date}')
    
    # Get current timer status if date is today
    timer_status = None
    if date == datetime.now().strftime("%Y-%m-%d"):
        timer_status = await get_timer_resource()
    
    # Process entries
    total_seconds = 0
    entry_dict = {}  # Use dict to group by task
    
    # Get tasks and projects for names
    tasks = await get_cached_tasks(client)
    projects = await get_cached_projects(client)
    
    for entry_id, entry_data in entries.items():
        if isinstance(entry_data, dict) and 'duration' in entry_data:
            duration = int(entry_data['duration'])
            total_seconds += duration
            
            # Get task and project names
            task_id = entry_data.get('task_id')
            task = next((t for t in tasks if t['id'] == task_id), None)
            task_name = task['name'] if task else 'Unknown'
            
            project_id = task.get('project_id') if task else None
            project = next((p for p in projects if p['id'] == project_id), None)
            project_name = project['name'] if project else 'No Project'
            
            # Group by task_id
            if task_id not in entry_dict:
                entry_dict[task_id] = {
                    'task_name': task_name,
                    'task_id': task_id,
                    'project_name': project_name,
                    'duration_seconds': 0,
                    'notes': set()  # Use set to collect unique notes
                }
            
            entry_dict[task_id]['duration_seconds'] += duration
            
            # Collect notes
            if entry_data.get('note'):
                entry_dict[task_id]['notes'].add(entry_data['note'])
    
    # Convert to list of DailySummaryEntry
    entry_list = []
    for task_data in entry_dict.values():
        entry_list.append(DailySummaryEntry(
            task_name=task_data['task_name'],
            task_id=task_data['task_id'],
            project_name=task_data['project_name'],
            duration=format_duration(task_data['duration_seconds']),
            duration_seconds=task_data['duration_seconds'],
            notes=list(task_data['notes'])  # Convert set to list
        ))
    
    # Sort by duration descending
    entry_list.sort(key=lambda x: entry_dict[x.task_id]['duration_seconds'], reverse=True)
    
    response = DailySummaryResponse(
        date=date,
        total_time=format_duration(total_seconds),
        total_seconds=total_seconds,
        entries=entry_list,
        entry_count=len(entry_list),
        is_timer_running=timer_status.is_running if timer_status else False,
        current_task=timer_status.task_name if timer_status and timer_status.is_running else None,
        current_task_id=timer_status.task_id if timer_status and timer_status.is_running else None
    )
    
    # Cache the response
    cache.set(cache_key, response)
    return response

@mcp.resource("timecamp://search/{q}")
async def search_resource(q: str) -> SearchResponse:
    """Fuzzy search for projects and tasks by name."""
    if not q:
        raise ToolError("Search query parameter 'q' cannot be empty.")

    api_token = get_api_token()
    client = TimeCampClient(api_token)

    projects = await get_cached_projects(client)
    tasks = await get_cached_tasks(client)

    choices = []
    # Add projects
    for project in projects:
        if 'name' in project and project.get('archived', '0') != '1':
            choices.append({
                'type': 'project',
                'id': project['id'],
                'name': project['name'],
                'search_text': project['name']
            })
    
    # Add tasks
    for task in tasks:
        if 'name' in task and task.get('archived', '0') != '1':
            project_name = next(
                (p['name'] for p in projects if p['id'] == task.get('project_id')),
                'No Project'
            )
            choices.append({
                'type': 'task',
                'id': task['id'],
                'name': task['name'],
                'project_name': project_name,
                'search_text': f"{task['name']} {project_name}"
            })

    if not choices:
        return SearchResponse(results=[], total_results=0, query=q)

    search_texts = [c['search_text'] for c in choices]
    matches = process.extract(
        q,
        search_texts,
        scorer=fuzz.WRatio,
        limit=10,
        score_cutoff=50
    )

    results = []
    for match_text, score, index in matches:
        choice = choices[index]
        result_item = SearchResultItem(
            type=choice['type'],
            id=choice['id'],
            name=choice['name'],
            match_score=score / 100.0,
            project_name=choice.get('project_name')
        )
        results.append(result_item)
    
    return SearchResponse(results=results, total_results=len(results), query=q)

# MCP Tools Implementation - State-changing operations only

@mcp.tool()
async def start_timer(task_id: int, note: Optional[str] = "") -> TimerResponse:
    """Start tracking time for a specific task."""
    # Validate input
    try:
        request = StartTimerRequest(task_id=task_id, note=note or "")
    except ValidationError as e:
        raise ToolError(str(e.errors()[0]['msg']) if e.errors() else str(e))
    
    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    # Check if timer already running
    try:
        current = await client.request('GET', 'timer_running')
        if current and 'timer_id' in current:
            task_name = current.get('name', 'Unknown task')
            raise ToolError(
                f"Timer already running for task '{task_name}' (ID: {current.get('timer_id')})"
            )
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # Continue if check fails - timer may not be running
        pass
    
    # Start timer
    data = {
        "task_id": request.task_id,
        "started_at": datetime.now().isoformat()
    }
    if request.note:
        data["note"] = request.note
    
    result = await client.request('POST', 'timer', data)
    
    # Get task name for response
    tasks = await get_cached_tasks(client)
    task_name = next((t['name'] for t in tasks if t['id'] == request.task_id), 'Unknown')
    
    # Invalidate timer and today's time entries caches
    cache.invalidate('timer')
    cache.invalidate(f'time-entries/{datetime.now().strftime("%Y-%m-%d")}')
    
    # Record state change
    state_tracker.record_change("timer_started", {
        "task_id": request.task_id,
        "task_name": task_name,
        "timer_id": result.get('timer_id', result.get('new_timer_id')),
        "started_at": data["started_at"]
    })
    
    return TimerResponse(
        message=f"Timer started for task '{task_name}'",
        timer_id=result.get('timer_id', result.get('new_timer_id')),
        task_id=request.task_id,
        task_name=task_name,
        started_at=data["started_at"]
    )

@mcp.tool()
async def stop_timer() -> StopTimerResponse:
    """Stop the currently running timer."""
    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    # Check if timer is running
    current = await client.request('GET', 'timer_running')
    if not current or 'timer_id' not in current:
        raise ToolError("No timer is currently running")
    
    # Stop timer
    data = {"action": "stop"}
    await client.request('PUT', 'timer', data)
    
    # Calculate duration if available
    if 'started_at' in current:
        started = datetime.fromisoformat(current['started_at'].replace('Z', '+00:00'))
        duration = datetime.now() - started
        duration_str = format_duration(int(duration.total_seconds()))
        duration_seconds = int(duration.total_seconds())
    else:
        duration_str = "Unknown duration"
        duration_seconds = 0
    
    # Invalidate timer and today's time entries caches
    cache.invalidate('timer')
    cache.invalidate(f'time-entries/{datetime.now().strftime("%Y-%m-%d")}')
    
    # Record state change
    state_tracker.record_change("timer_stopped", {
        "task_id": current.get('task_id'),
        "task_name": current.get('name', 'Unknown task'),
        "timer_id": current.get('timer_id'),
        "duration_seconds": duration_seconds,
        "duration": duration_str
    })
    
    return StopTimerResponse(
        message="Timer stopped",
        duration=duration_str,
        duration_seconds=duration_seconds,
        task_name=current.get('name', 'Unknown task'),
        task_id=current.get('task_id'),
        timer_id=current.get('timer_id')
    )



@mcp.tool()
async def create_time_entry(
    task_id: int,
    date: str,
    start_time: str,
    end_time: str,
    note: Optional[str] = ""
) -> TimeEntryResponse:
    """Manually create a time entry for past work."""
    # Validate input
    try:
        request = CreateTimeEntryRequest(
            task_id=task_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            note=note or ""
        )
    except ValidationError as e:
        # Convert Pydantic validation error to ToolError
        raise ToolError(str(e.errors()[0]['msg']) if e.errors() else str(e))
    
    api_token = get_api_token()
    client = TimeCampClient(api_token)
    
    # Parse times for duration calculation
    try:
        date_obj = datetime.strptime(request.date, "%Y-%m-%d")
        start_dt = datetime.strptime(f"{request.date} {request.start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{request.date} {request.end_time}", "%Y-%m-%d %H:%M")
    except ValueError as e:
        raise ToolError(f"Invalid date/time format: {str(e)}")
    
    duration = int((end_dt - start_dt).total_seconds())
    
    # Create entry
    data = {
        "task_id": request.task_id,
        "date": request.date,
        "start_time": request.start_time + ":00",
        "end_time": request.end_time + ":00",
        "duration": duration
    }
    if request.note:
        data["note"] = request.note
    
    result = await client.request('POST', 'time_entries', data)
    
    # Get task name for response
    tasks = await get_cached_tasks(client)
    task = next((t for t in tasks if t['id'] == request.task_id), None)
    task_name = task['name'] if task else 'Unknown'
    
    # Get project name
    projects = await get_cached_projects(client)
    project = next((p for p in projects if p['id'] == task.get('project_id')), None) if task else None
    project_name = project['name'] if project else 'No Project'
    
    # Invalidate time entries cache for the date
    cache.invalidate(f'time-entries/{request.date}')
    
    # Record state change
    state_tracker.record_change("time_entry_created", {
        "entry_id": result.get('entry_id', result.get('id')),
        "task_id": request.task_id,
        "task_name": task_name,
        "project_name": project_name,
        "date": request.date,
        "duration_seconds": duration,
        "duration": format_duration(duration)
    })
    
    return TimeEntryResponse(
        entry_id=result.get('entry_id', result.get('id')),
        task_id=request.task_id,
        task_name=task_name,
        project_name=project_name,
        date=request.date,
        start_time=request.start_time,
        end_time=request.end_time,
        duration=format_duration(duration),
        duration_seconds=duration,
        note=request.note
    )

# Resource Change Tracking
# Since FastMCP doesn't support real-time subscriptions, we'll track
# significant state changes that clients can poll via resources

class StateTracker:
    """Track significant state changes for client polling"""
    def __init__(self):
        self._changes: List[Dict[str, Any]] = []
        self._max_changes = 100
    
    def record_change(self, change_type: str, details: Dict[str, Any]):
        """Record a state change"""
        change = {
            "type": change_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self._changes.append(change)
        # Keep only recent changes
        if len(self._changes) > self._max_changes:
            self._changes = self._changes[-self._max_changes:]
    
    def get_changes_since(self, timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get changes since a timestamp"""
        if not timestamp:
            return self._changes
        
        return [c for c in self._changes 
                if datetime.fromisoformat(c["timestamp"]) > timestamp]
    
    def clear(self):
        """Clear all changes"""
        self._changes.clear()

# Global state tracker
state_tracker = StateTracker()

@mcp.resource("timecamp://changes")
async def get_state_changes_resource() -> Dict[str, Any]:
    """Get recent state changes (pseudo-subscription).
    
    This resource allows clients to poll for recent state changes
    like timer starts/stops and time entry creation.
    """
    return {
        "changes": state_tracker.get_changes_since(),
        "timestamp": datetime.now().isoformat()
    }

# MCP Prompts Implementation

@mcp.prompt()
async def daily_standup_prompt(date: Optional[str] = None) -> str:
    """Generate a daily standup report from time entries.
    
    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Get time entries for the date
        entries = await get_time_entries_resource.fn(date)
        
        if not entries.entries:
            return f"No time entries recorded for {date}."
        
        # Format the standup
        standup_lines = [
            f"Daily Standup for {date}",
            "=" * 30,
            f"Total time tracked: {entries.total_time}",
            "",
            "What I worked on:"
        ]
        
        for entry in entries.entries:
            line = f"• {entry.task_name} ({entry.project_name}): {entry.duration}"
            if entry.notes:
                line += f" - {'; '.join(entry.notes)}"
            standup_lines.append(line)
        
        if entries.is_timer_running:
            standup_lines.extend([
                "",
                f"Currently working on: {entries.current_task}"
            ])
        
        return "\n".join(standup_lines)
        
    except Exception as e:
        return f"Error generating standup: {str(e)}"

@mcp.prompt()
async def weekly_report_prompt(start_date: Optional[str] = None) -> str:
    """Generate a weekly time report.
    
    Args:
        start_date: Start date of the week in YYYY-MM-DD format. 
                   Defaults to current week's Monday.
    """
    if not start_date:
        # Get current week's Monday
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        start_date = start.strftime("%Y-%m-%d")
    
    try:
        api_token = get_api_token()
        client = TimeCampClient(api_token)
        
        # Calculate week dates
        start = datetime.strptime(start_date, "%Y-%m-%d")
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        
        # Collect data for the week
        week_data = {}
        total_seconds = 0
        project_totals = {}
        task_totals = {}
        
        for date in dates:
            try:
                entries = await get_time_entries_resource.fn(date)
                if entries.entries:
                    week_data[date] = entries
                    total_seconds += entries.total_seconds
                    
                    # Aggregate by project and task
                    for entry in entries.entries:
                        # Project totals
                        if entry.project_name not in project_totals:
                            project_totals[entry.project_name] = 0
                        project_totals[entry.project_name] += entry.duration_seconds
                        
                        # Task totals
                        task_key = f"{entry.task_name} ({entry.project_name})"
                        if task_key not in task_totals:
                            task_totals[task_key] = 0
                        task_totals[task_key] += entry.duration_seconds
            except Exception as e:
                # Log the error but continue processing other days
                # This ensures partial data is returned rather than complete failure
                logging.error(f"Error fetching time entries for {date} in weekly report: {e}")
                continue
        
        # Format the report
        report_lines = [
            f"Weekly Time Report",
            f"Week of {start_date}",
            "=" * 40,
            f"Total time tracked: {format_duration(total_seconds)}",
            "",
            "Time by Day:"
        ]
        
        # Daily breakdown
        for date, entries in sorted(week_data.items()):
            day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            report_lines.append(f"• {day_name} ({date}): {entries.total_time}")
        
        # Project breakdown
        if project_totals:
            report_lines.extend([
                "",
                "Time by Project:"
            ])
            for project, seconds in sorted(project_totals.items(), 
                                         key=lambda x: x[1], reverse=True):
                report_lines.append(f"• {project}: {format_duration(seconds)}")
        
        # Top tasks
        if task_totals:
            report_lines.extend([
                "",
                "Top 5 Tasks:"
            ])
            top_tasks = sorted(task_totals.items(), 
                             key=lambda x: x[1], reverse=True)[:5]
            for task, seconds in top_tasks:
                report_lines.append(f"• {task}: {format_duration(seconds)}")
        
        return "\n".join(report_lines)
        
    except Exception as e:
        return f"Error generating weekly report: {str(e)}"

@mcp.prompt()
async def time_tracking_insights_prompt() -> str:
    """Generate insights about time tracking patterns and suggestions."""
    try:
        # Get today's and yesterday's data for comparison
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        
        today_entries = await get_time_entries_resource.fn(today_str)
        yesterday_entries = await get_time_entries_resource.fn(yesterday_str)
        
        # Get current timer status
        timer_status = await get_timer_resource.fn()
        
        insights = [
            "Time Tracking Insights",
            "=" * 30,
            ""
        ]
        
        # Today's progress
        if today_entries.total_seconds > 0:
            insights.append(f"Today's tracked time: {today_entries.total_time}")
            insights.append(f"Tasks worked on: {len(today_entries.entries)}")
        else:
            insights.append("No time tracked today yet.")
        
        # Timer status
        if timer_status.is_running:
            insights.extend([
                "",
                f"Timer is running: {timer_status.task_name}",
                f"Elapsed time: {timer_status.elapsed_time}"
            ])
        else:
            insights.extend([
                "",
                "No timer currently running.",
                "💡 Tip: Start tracking your time to maintain accurate records."
            ])
        
        # Comparison with yesterday
        if yesterday_entries.total_seconds > 0:
            insights.extend([
                "",
                f"Yesterday's total: {yesterday_entries.total_time}",
                f"Tasks completed: {len(yesterday_entries.entries)}"
            ])
            
            if today_entries.total_seconds < yesterday_entries.total_seconds * 0.5:
                insights.append("📊 You're tracking less time than yesterday.")
        
        # Suggestions
        insights.extend([
            "",
            "Suggestions:",
            "• Review untracked time gaps",
            "• Set reminders to start/stop timers",
            "• Use descriptive notes for better reporting"
        ])
        
        return "\n".join(insights)
        
    except Exception as e:
        return f"Error generating insights: {str(e)}"

