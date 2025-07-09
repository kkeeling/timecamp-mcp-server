# TimeCamp MCP Server

A Model Context Protocol (MCP) server that integrates TimeCamp time tracking directly into AI assistants like Claude, Cline, and Continue.

## Features

- ⏱️ **Real-time Timer Control** - Start, stop, and check timer status
- 📊 **Time Entry Management** - Create manual time entries for past work
- 🔍 **Smart Search** - Fuzzy search across projects and tasks
- 📈 **Reporting** - Daily summaries, weekly reports, and time tracking insights
- 🚀 **Intelligent Caching** - Fast response times with built-in cache management
- 📝 **Rich Prompts** - Pre-built prompts for standup reports and analytics

## Quick Start

### Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or [pipx](https://github.com/pypa/pipx) for running directly from GitHub
- TimeCamp account with API access
- MCP-compatible client (Claude Desktop, Cline, Continue, etc.)

### Configuration

**Get your TimeCamp API token**:
- Log into [TimeCamp](https://www.timecamp.com)
- Navigate to **Profile → API Access**
- Copy your API token

## Client Configuration

Configure your MCP client to run the TimeCamp server directly from GitHub. The `uvx` command will automatically install and run the server on first use:

### Claude Desktop

Add to `~/.claude/claude_desktop_config.json` (macOS/Linux) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "timecamp": {
      "command": "uvx",
      "args": ["timecamp-mcp-server"],
      "env": {
        "TIMECAMP_API_TOKEN": "YOUR_API_TOKEN_HERE"
      }
    }
  }
}
```

**Alternative using uv tool:**
```json
{
  "mcpServers": {
    "timecamp": {
      "command": "uv",
      "args": ["tool", "run", "--from", "git+https://github.com/yourusername/timecamp-mcp-server", "timecamp-mcp-server"],
      "env": {
        "TIMECAMP_API_TOKEN": "YOUR_API_TOKEN_HERE"
      }
    }
  }
}
```

### VS Code (Cline, Continue, etc.)

For VS Code extensions that support MCP, add to your settings:

```json
{
  "cline.mcp.servers": {
    "timecamp": {
      "command": "uvx",
      "args": ["timecamp-mcp-server"],
      "env": {
        "TIMECAMP_API_TOKEN": "YOUR_API_TOKEN_HERE"
      }
    }
  }
}
```

### Manual Installation (Optional)

If you prefer to install the server locally first:

1. **Using pipx** (recommended for isolated environment):
   ```bash
   pipx install git+https://github.com/yourusername/timecamp-mcp-server.git
   ```

2. **Using uv tool**:
   ```bash
   uv tool install git+https://github.com/yourusername/timecamp-mcp-server.git
   ```

3. **Using pip**:
   ```bash
   pip install git+https://github.com/yourusername/timecamp-mcp-server.git
   ```

After installation, configure your MCP client with the simpler command:

```json
{
  "mcpServers": {
    "timecamp": {
      "command": "timecamp-mcp-server",
      "env": {
        "TIMECAMP_API_TOKEN": "YOUR_API_TOKEN_HERE"
      }
    }
  }
}
```

## Resources

Resources provide read-only access to TimeCamp data:

### `timecamp://projects`
Lists all available projects with task counts and status.

**Example response**:
```json
{
  "projects": [
    {
      "id": 12345,
      "name": "Website Development",
      "color": "#4CAF50",
      "tasks_count": 15,
      "archived": false
    }
  ],
  "total_count": 8,
  "include_archived": true
}
```

### `timecamp://tasks`
Lists all tasks with their associated projects.

**Example response**:
```json
[
  {
    "id": 67890,
    "name": "Frontend Development",
    "project_id": 12345,
    "project_name": "Website Development",
    "archived": false
  }
]
```

### `timecamp://timer`
Shows current timer status.

**Example response**:
```json
{
  "is_running": true,
  "task_name": "Code Review",
  "task_id": 67890,
  "timer_id": 11111,
  "project_name": "Website Development",
  "elapsed_time": "1h 23m",
  "elapsed_seconds": 4980,
  "start_time": "2024-01-15T10:30:00Z"
}
```

### `timecamp://time-entries/{date}`
Retrieves time entries for a specific date (format: YYYY-MM-DD).

**Example**: `timecamp://time-entries/2024-01-15`

**Example response**:
```json
{
  "date": "2024-01-15",
  "total_time": "6h 45m",
  "total_seconds": 24300,
  "entries": [
    {
      "task_name": "Code Review",
      "task_id": 67890,
      "project_name": "Website Development",
      "duration": "2h 30m",
      "duration_seconds": 9000,
      "notes": ["Reviewed PR #123", "Fixed merge conflicts"]
    }
  ],
  "entry_count": 4,
  "is_timer_running": true,
  "current_task": "Documentation",
  "current_task_id": 67891
}
```

### `timecamp://changes`
Tracks recent state changes (timer starts/stops, entries created).

**Example response**:
```json
{
  "changes": [
    {
      "type": "timer_started",
      "timestamp": "2024-01-15T14:30:00Z",
      "details": {
        "task_id": 67890,
        "task_name": "Code Review",
        "timer_id": 11111
      }
    }
  ],
  "timestamp": "2024-01-15T14:35:00Z"
}
```

### `timecamp://search/{query}`
Fuzzy search for projects and tasks by name.

**Example**: `timecamp://search/frontend`

**Response**:
```json
{
  "results": [
    {
      "type": "task",
      "id": 67890,
      "name": "Frontend Development",
      "match_score": 0.95,
      "project_name": "Website Development"
    },
    {
      "type": "project",
      "id": 12345,
      "name": "Frontend Redesign",
      "match_score": 0.85
    }
  ],
  "total_results": 2,
  "query": "frontend"
}
```

## Tools

Tools allow you to perform actions in TimeCamp:

### `start_timer`
Starts a timer for a specific task.

**Parameters**:
- `task_id` (required): The ID of the task to track
- `note` (optional): A note to attach to the timer

**Example**:
```json
{
  "task_id": 67890,
  "note": "Working on authentication feature"
}
```

**Response**:
```json
{
  "message": "Timer started for task 'Frontend Development'",
  "timer_id": 11111,
  "task_id": 67890,
  "task_name": "Frontend Development",
  "started_at": "2024-01-15T10:30:00Z",
  "project_name": "Website Development"
}
```

### `stop_timer`
Stops the currently running timer.

**Parameters**: None

**Response**:
```json
{
  "message": "Timer stopped",
  "duration": "2h 15m",
  "duration_seconds": 8100,
  "task_name": "Frontend Development",
  "task_id": 67890,
  "timer_id": 11111
}
```

### `create_time_entry`
Creates a manual time entry for past work.

**Parameters**:
- `task_id` (required): The task ID
- `date` (required): Date in YYYY-MM-DD format
- `start_time` (required): Start time in HH:MM format
- `end_time` (required): End time in HH:MM format
- `note` (optional): Description of work done

**Example**:
```json
{
  "task_id": 67890,
  "date": "2024-01-14",
  "start_time": "14:00",
  "end_time": "16:30",
  "note": "Implemented user authentication"
}
```

**Response**:
```json
{
  "entry_id": 99999,
  "task_id": 67890,
  "task_name": "Frontend Development",
  "project_name": "Website Development",
  "date": "2024-01-14",
  "start_time": "14:00",
  "end_time": "16:30",
  "duration": "2h 30m",
  "duration_seconds": 9000,
  "note": "Implemented user authentication"
}
```

## Prompts

Pre-built prompts for common time tracking workflows:

### `daily_standup_prompt`
Generates a daily standup report from time entries.

**Parameters**:
- `date` (optional): Date in YYYY-MM-DD format (defaults to today)

**Example output**:
```
Daily Standup for 2024-01-15
==============================
Total time tracked: 6h 45m

What I worked on:
• Frontend Development (Website Development): 2h 30m - Implemented auth flow; Fixed responsive issues
• Code Review (Website Development): 1h 45m - Reviewed PR #123
• Documentation (API Project): 1h 30m - Updated API docs
• Team Meeting (Internal): 1h 0m

Currently working on: Documentation
```

### `weekly_report_prompt`
Generates a comprehensive weekly time report.

**Parameters**:
- `start_date` (optional): Start date in YYYY-MM-DD format (defaults to current week's Monday)

**Example output**:
```
Weekly Time Report
Week of 2024-01-08
========================================
Total time tracked: 35h 20m

Time by Day:
• Monday (2024-01-08): 7h 15m
• Tuesday (2024-01-09): 6h 45m
• Wednesday (2024-01-10): 7h 30m
• Thursday (2024-01-11): 8h 0m
• Friday (2024-01-12): 5h 50m

Time by Project:
• Website Development: 22h 15m
• API Project: 8h 30m
• Internal: 4h 35m

Top 5 Tasks:
• Frontend Development (Website Development): 12h 30m
• Backend API (API Project): 6h 45m
• Code Review (Website Development): 5h 15m
• Documentation (API Project): 3h 30m
• Team Meeting (Internal): 2h 45m
```

### `time_tracking_insights_prompt`
Provides insights and suggestions for better time tracking.

**Parameters**: None

**Example output**:
```
Time Tracking Insights
==============================

Today's tracked time: 4h 30m
Tasks worked on: 3

Timer is running: Documentation
Elapsed time: 45m

Yesterday's total: 7h 15m
Tasks completed: 5
📊 You're tracking less time than yesterday.

Suggestions:
• Review untracked time gaps
• Set reminders to start/stop timers
• Use descriptive notes for better reporting
```

## Usage Examples

### Start tracking time
```
"Start timer for task 67890 with note 'Working on login feature'"
"Begin tracking Frontend Development task"
"Start working on task ID 12345"
```

### Stop tracking
```
"Stop the timer"
"Stop tracking time"
"End current timer"
```

### Check status
```
"What's my current timer status?"
"Am I tracking time right now?"
"Show current timer"
```

### Create time entries
```
"Log 2 hours for task 67890 yesterday from 2pm to 4pm"
"Create time entry for Frontend Development on 2024-01-14 from 09:00 to 11:30"
"Add manual entry for task 12345"
```

### View summaries
```
"Show me today's time tracking"
"What did I work on today?"
"Generate my daily standup"
"Create weekly report for last week"
"Show time tracking insights"
```

## Advanced Features

### Intelligent Caching
- 5-minute TTL cache for projects and tasks
- Automatic cache invalidation on state changes
- ETag support for efficient resource updates

### Error Handling
- Graceful handling of API errors
- Clear error messages for common issues
- Rate limit detection and warnings

### State Tracking
- Monitors timer starts/stops
- Tracks time entry creation
- Provides change history via `timecamp://changes` resource

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TIMECAMP_API_TOKEN` | Your TimeCamp API token | Yes |

## Troubleshooting

### "TIMECAMP_API_TOKEN environment variable not set"
Ensure the API token is properly configured in your MCP client's configuration file.

### "Invalid API token"
1. Verify your token in TimeCamp: **Profile → API Access**
2. Check for extra spaces or characters in the token
3. Ensure the token hasn't been regenerated

### "Rate limit exceeded"
TimeCamp API has rate limits. Wait 60 seconds before retrying.

### "Module not found"
Install all dependencies:
```bash
pip install -r requirements.txt
```

### Timer not starting
1. Verify the task ID exists
2. Check if a timer is already running (stop it first)
3. Ensure the task isn't archived

## Development

### Setup for Development
```bash
# Clone the repository
git clone https://github.com/yourusername/timecamp-mcp-server.git
cd timecamp-mcp-server

# Install in editable mode
pip install -e .

# Run tests
pytest
```

### Running locally
```bash
# After installation
timecamp-mcp-server

# Or run as Python module
python -m timecamp_mcp_server
```

### Debug mode
```bash
timecamp-mcp-server --help
```

### Dependencies
- `fastmcp` - MCP server framework
- `httpx` - Async HTTP client
- `pydantic` - Data validation
- `rapidfuzz` - Fuzzy string matching
- `python-dotenv` - Environment variable management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Support

- **TimeCamp API Documentation**: [https://developer.timecamp.com/](https://developer.timecamp.com/)
- **MCP Documentation**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/timecamp-mcp-server/issues)