# TimeCamp MCP Server Implementation Specification

## Overview
Implementation of a Model Context Protocol (MCP) server for TimeCamp integration, enabling AI assistants to interact with TimeCamp's time tracking system through natural language commands.

## Objective
Create a working MCP server with 7 MVP tools that covers 80% of daily developer time tracking needs, following the "build simple things first" principle.

## MVP Tools (7 Essential)

### 1. start_timer
- **Description**: Start tracking time for a specific task/project
- **Parameters**: 
  - `task_id` (required): TimeCamp task ID
  - `note` (optional): Description of work
- **API Endpoint**: `POST /timer`
- **Success Response**: Timer ID, task name, start time
- **Error Cases**: Timer already running, invalid task ID

### 2. stop_timer
- **Description**: Stop the currently running timer
- **Parameters**: None
- **API Endpoint**: `PUT /timer` with `{"action": "stop"}`
- **Success Response**: Duration, task name
- **Error Cases**: No timer running

### 3. get_timer_status
- **Description**: Check if timer is running and get details
- **Parameters**: None
- **API Endpoint**: `GET /timer_running`
- **Success Response**: Running status, elapsed time, task info
- **Error Cases**: None (returns running: false if no timer)

### 4. search_projects_and_tasks
- **Description**: Fuzzy search for projects and tasks by name
- **Parameters**: 
  - `query` (required): Search term
- **Implementation**: Client-side fuzzy matching over cached data
- **Success Response**: Matched items with scores
- **Error Cases**: No matches found

### 5. create_time_entry
- **Description**: Manually create time entry for past work
- **Parameters**:
  - `task_id` (required): TimeCamp task ID
  - `date` (required): YYYY-MM-DD format
  - `start_time` (required): HH:MM format
  - `end_time` (required): HH:MM format
  - `note` (optional): Description
- **API Endpoint**: `POST /time_entries`
- **Success Response**: Entry ID, duration, task name
- **Error Cases**: Invalid times, task not found

### 6. get_today_summary
- **Description**: Get summary of today's tracked time
- **Parameters**: None
- **API Endpoint**: `GET /time_entries?from={today}&to={today}`
- **Success Response**: Total time, entries list, current timer status
- **Error Cases**: None (returns empty if no entries)

### 7. list_projects
- **Description**: Get all available projects
- **Parameters**:
  - `include_archived` (optional, default: false)
- **API Endpoint**: `GET /projects`
- **Success Response**: Projects list with IDs, names, task counts
- **Error Cases**: None (returns empty if no projects)

## Technical Architecture

### Framework
- **FastMCP**: Decorator-based MCP framework for Python
- **Python 3.9+**: Modern Python features and type hints

### Dependencies
```
fastmcp>=0.1.0
httpx>=0.24.0
rapidfuzz>=3.0.0
python-dotenv>=1.0.0
```

### Authentication
- Stateless design - API token passed via resource blocks
- Resource URI format: `timecamp://auth/{api_token}`
- Token held only in memory for request duration
- Never logged or persisted

### Caching Strategy
- Projects: 5-minute TTL
- Tasks: 5-minute TTL  
- Timer status: Never cached (always fresh)
- Time entries: 1-minute TTL

### Error Handling
Map TimeCamp HTTP status codes to user-friendly messages:
- 401 → "Invalid API token. Check TimeCamp settings"
- 404 → "Task/project not found"
- 429 → "Rate limit exceeded. Wait 60 seconds"
- 500 → "TimeCamp unavailable. Try again later"

### Search Implementation
- Use rapidfuzz library for fuzzy matching
- Score threshold: 0.5 (50% match minimum)
- Return top 10 matches sorted by score
- Search both project and task names

## File Structure
```
timecamp-mcp-server/
├── server.py           # Main MCP server implementation
├── requirements.txt    # Python dependencies
├── README.md          # Setup and usage instructions
├── .env.example       # Environment variable template
└── .gitignore         # Git ignore file
```

## Implementation Steps

### Step 1: Basic Server Setup
1. Create `server.py` with FastMCP initialization
2. Implement authentication resource handler
3. Add health check tool for testing

### Step 2: Core Timer Tools
1. Implement `start_timer` with error handling
2. Implement `stop_timer` with duration calculation
3. Implement `get_timer_status` for current state

### Step 3: Data Retrieval Tools
1. Implement `list_projects` with caching
2. Implement `get_today_summary` with aggregation
3. Add cache management utilities

### Step 4: Advanced Features
1. Implement `search_projects_and_tasks` with fuzzy matching
2. Implement `create_time_entry` with validation
3. Add comprehensive error handling

### Step 5: Testing & Documentation
1. Test all tools with Claude Desktop
2. Create README with setup instructions
3. Add example usage patterns

## Success Criteria
- All 7 MVP tools working correctly
- Response time <500ms for all operations
- Clear error messages for common issues
- Successful integration with Claude Desktop
- Simple setup process (<5 minutes)

## Future Enhancements (Phase 2)
- Additional tools: update/delete entries, weekly reports
- Advanced caching with Redis
- Webhook support for real-time updates
- Team collaboration features
- Billing and invoice integration