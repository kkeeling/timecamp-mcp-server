#!/usr/bin/env python3
"""
TimeCamp MCP Server
A Model Context Protocol server for TimeCamp time tracking integration.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import asyncio

from fastmcp import FastMCP
import httpx
from rapidfuzz import fuzz, process

# Initialize FastMCP server
mcp = FastMCP("TimeCamp MCP Server")

# Cache configuration
CACHE_TTL = 300  # 5 minutes in seconds

class SimpleCache:
    """Simple in-memory cache with TTL"""
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now().timestamp() < expiry:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = CACHE_TTL):
        """Set value in cache with TTL"""
        expiry = datetime.now().timestamp() + ttl
        self._cache[key] = (value, expiry)
    
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
                    raise Exception("Invalid API token. Check TimeCamp settings")
                elif e.response.status_code == 404:
                    raise Exception("Resource not found")
                elif e.response.status_code == 429:
                    raise Exception("Rate limit exceeded. Wait 60 seconds")
                elif 500 <= e.response.status_code < 600:
                    raise Exception("TimeCamp unavailable. Try again later")
                else:
                    raise Exception(f"API error: {e.response.status_code}")
            except httpx.RequestError as e:
                raise Exception(f"Network error: {str(e)}")
            except Exception as e:
                raise Exception(f"Unexpected error: {str(e)}")

def get_api_token() -> Optional[str]:
    """Get API token from MCP context"""
    context = mcp.get_context()
    return context.get('api_token') if context else None

async def get_cached_projects(client: TimeCampClient) -> List[Dict]:
    """Get projects with caching"""
    cached = cache.get('projects')
    if cached is not None:
        return cached
    
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
    cached = cache.get('tasks')
    if cached is not None:
        return cached
    
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

# MCP Tools Implementation

@mcp.tool()
async def start_timer(task_id: int, note: Optional[str] = "") -> Dict[str, Any]:
    """Start tracking time for a specific task."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    # Check if timer already running
    try:
        current = await client.request('GET', 'timer_running')
        if current and 'timer_id' in current:
            task_name = current.get('name', 'Unknown task')
            return {
                "success": False,
                "error": f"Timer already running for task '{task_name}'",
                "current_timer_id": current.get('timer_id')
            }
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # Continue if check fails - timer may not be running
        pass
    
    # Start timer
    try:
        data = {
            "task_id": task_id,
            "started_at": datetime.now().isoformat()
        }
        if note:
            data["note"] = note
        
        result = await client.request('POST', 'timer', data)
        
        # Get task name for response
        tasks = await get_cached_tasks(client)
        task_name = next((t['name'] for t in tasks if t['id'] == task_id), 'Unknown')
        
        return {
            "success": True,
            "message": f"Timer started for task '{task_name}'",
            "timer_id": result.get('timer_id', result.get('new_timer_id'))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def stop_timer() -> Dict[str, Any]:
    """Stop the currently running timer."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    # Check if timer is running
    try:
        current = await client.request('GET', 'timer_running')
        if not current or 'timer_id' not in current:
            return {"success": False, "error": "No timer is currently running"}
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return {"success": False, "error": f"Failed to check timer status: {str(e)}"}
    
    # Stop timer
    try:
        data = {"action": "stop"}
        await client.request('PUT', 'timer', data)
        
        # Calculate duration if available
        if 'started_at' in current:
            started = datetime.fromisoformat(current['started_at'].replace('Z', '+00:00'))
            duration = datetime.now() - started
            duration_str = format_duration(int(duration.total_seconds()))
        else:
            duration_str = "Unknown duration"
        
        return {
            "success": True,
            "message": "Timer stopped",
            "duration": duration_str,
            "task_name": current.get('name', 'Unknown task')
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_timer_status() -> Dict[str, Any]:
    """Check if a timer is currently running and get details."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    try:
        result = await client.request('GET', 'timer_running')
        
        if result and 'timer_id' in result:
            # Calculate elapsed time
            if 'started_at' in result:
                started = datetime.fromisoformat(result['started_at'].replace('Z', '+00:00'))
                elapsed = datetime.now() - started
                elapsed_str = format_duration(int(elapsed.total_seconds()))
            else:
                elapsed_str = "Unknown"
            
            return {
                "is_running": True,
                "task_name": result.get('name', 'Unknown'),
                "task_id": result.get('task_id'),
                "project_name": result.get('project_name', 'Unknown'),
                "elapsed_time": elapsed_str,
                "start_time": result.get('started_at')
            }
        else:
            return {
                "is_running": False,
                "message": "No timer is currently running"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def search_projects_and_tasks(query: str) -> Dict[str, Any]:
    """Fuzzy search for projects and tasks by name."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    try:
        # Get all projects and tasks
        projects = await get_cached_projects(client)
        tasks = await get_cached_tasks(client)
        
        # Prepare choices for fuzzy matching
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
        
        # Perform fuzzy search
        if not choices:
            return {"results": [], "total_results": 0}
        
        # Extract top 10 matches
        search_texts = [c['search_text'] for c in choices]
        matches = process.extract(
            query,
            search_texts,
            scorer=fuzz.WRatio,
            limit=10,
            score_cutoff=50
        )
        
        results = []
        for match_text, score, index in matches:
            choice = choices[index]
            result = {
                'type': choice['type'],
                'id': choice['id'],
                'name': choice['name'],
                'match_score': score / 100.0  # Normalize to 0-1
            }
            if choice['type'] == 'task':
                result['project_name'] = choice.get('project_name', 'No Project')
            results.append(result)
        
        return {
            "results": results,
            "total_results": len(results)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_time_entry(
    task_id: int,
    date: str,
    start_time: str,
    end_time: str,
    note: Optional[str] = ""
) -> Dict[str, Any]:
    """Manually create a time entry for past work."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    try:
        # Parse and validate times
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
        
        if end_dt <= start_dt:
            return {"success": False, "error": "End time must be after start time"}
        
        duration = int((end_dt - start_dt).total_seconds())
        
        # Create entry
        data = {
            "task_id": task_id,
            "date": date,
            "start_time": start_time + ":00",
            "end_time": end_time + ":00",
            "duration": duration
        }
        if note:
            data["note"] = note
        
        result = await client.request('POST', 'time_entries', data)
        
        # Get task name for response
        tasks = await get_cached_tasks(client)
        task = next((t for t in tasks if t['id'] == task_id), None)
        task_name = task['name'] if task else 'Unknown'
        
        # Get project name
        projects = await get_cached_projects(client)
        project = next((p for p in projects if p['id'] == task.get('project_id')), None) if task else None
        project_name = project['name'] if project else 'Unknown'
        
        return {
            "success": True,
            "entry_id": result.get('entry_id', result.get('id')),
            "duration": format_duration(duration),
            "task_name": task_name,
            "project_name": project_name
        }
    except ValueError as e:
        return {"success": False, "error": f"Invalid date/time format: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_today_summary() -> Dict[str, Any]:
    """Get summary of today's tracked time."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get today's entries
        entries = await client.request('GET', f'time_entries?from={today}&to={today}')
        
        # Get current timer status
        timer_status = await get_timer_status()
        
        # Process entries
        total_seconds = 0
        entry_list = []
        
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
                project_name = project['name'] if project else 'Unknown'
                
                # Collect notes
                notes = []
                if entry_data.get('note'):
                    notes.append(entry_data['note'])
                
                # Check if this task already exists in our list
                existing = next((e for e in entry_list if e['task_name'] == task_name), None)
                if existing:
                    existing['duration_seconds'] += duration
                    existing['duration'] = format_duration(existing['duration_seconds'])
                    if notes:
                        # Use set to ensure unique notes
                        existing['notes'] = list(set(existing['notes'] + notes))
                else:
                    entry_list.append({
                        'task_name': task_name,
                        'project_name': project_name,
                        'duration': format_duration(duration),
                        'duration_seconds': duration,
                        'notes': notes
                    })
        
        # Sort by duration descending
        entry_list.sort(key=lambda x: x['duration_seconds'], reverse=True)
        
        # Remove duration_seconds from output
        for entry in entry_list:
            del entry['duration_seconds']
        
        return {
            "date": today,
            "total_time": format_duration(total_seconds),
            "entries": entry_list,
            "is_timer_running": timer_status.get('is_running', False),
            "current_task": timer_status.get('task_name') if timer_status.get('is_running') else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def list_projects(include_archived: bool = False) -> Dict[str, Any]:
    """Get all available projects."""
    api_token = get_api_token()
    if not api_token:
        return {"success": False, "error": "No API token provided"}
    
    client = TimeCampClient(api_token)
    
    try:
        projects = await get_cached_projects(client)
        
        # Filter and format projects
        project_list = []
        for project in projects:
            if 'name' in project:
                # Skip archived if not requested
                if not include_archived and project.get('archived', '0') == '1':
                    continue
                
                # Count tasks for this project
                tasks = await get_cached_tasks(client)
                task_count = sum(1 for t in tasks if t.get('project_id') == project['id'])
                
                project_list.append({
                    'id': project['id'],
                    'name': project['name'],
                    'color': project.get('color', '#4CAF50'),
                    'tasks_count': task_count
                })
        
        # Sort by name
        project_list.sort(key=lambda x: x['name'])
        
        return {
            "projects": project_list,
            "total_count": len(project_list)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# Resource handler for authentication
@mcp.resource("timecamp://auth/{api_token}")
async def handle_auth(api_token: str) -> str:
    """Handle authentication resource."""
    # Store API token in context
    mcp.set_context({'api_token': api_token})
    
    # Test the token
    client = TimeCampClient(api_token)
    try:
        # Try to get user info
        await client.request('GET', 'me')
        return f"Authenticated with TimeCamp successfully"
    except Exception as e:
        return f"Authentication failed: {str(e)}"

if __name__ == "__main__":
    # Run the server
    import sys
    if '--help' in sys.argv:
        print("TimeCamp MCP Server")
        print("===================")
        print()
        print("Usage: python server.py")
        print()
        print("Configure in Claude Desktop by adding to config:")
        print('{')
        print('  "mcp_servers": {')
        print('    "timecamp": {')
        print('      "command": "python",')
        print('      "args": ["/path/to/server.py"],')
        print('      "resources": ["timecamp://auth/YOUR_API_TOKEN"]')
        print('    }')
        print('  }')
        print('}')
    else:
        mcp.run()
