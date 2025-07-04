# TimeCamp MCP Server

A Model Context Protocol (MCP) server for TimeCamp time tracking integration.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Get your TimeCamp API token**:
   - Log into TimeCamp
   - Go to Profile → API Access
   - Copy your API token

3. **Configure Claude Desktop**:
   Add to `~/.claude/config.json`:
   ```json
   {
     "mcp_servers": {
       "timecamp": {
         "command": "python",
         "args": ["/path/to/timecamp-mcp-server/server.py"],
         "resources": ["timecamp://auth/YOUR_API_TOKEN_HERE"]
       }
     }
   }
   ```

4. **Test the connection**:
   In Claude Desktop, type: "Check TimeCamp connection"

## Available Commands

- **Start timer**: "Start timer for task 12345"
- **Stop timer**: "Stop the timer"
- **Check status**: "What's my current timer status?"
- **Search**: "Find project web development"
- **Create entry**: "Log 2 hours for task 12345 yesterday from 2pm to 4pm"
- **Today's summary**: "Show me today's time tracking"
- **List projects**: "Show all projects"

## Tools

1. `start_timer` - Start tracking time for a task
2. `stop_timer` - Stop the current timer
3. `get_timer_status` - Check if timer is running
4. `search_projects_and_tasks` - Fuzzy search for projects/tasks
5. `create_time_entry` - Manual time entry for past work
6. `get_today_summary` - Summary of today's tracked time
7. `list_projects` - List all available projects

## Troubleshooting

- **"No API token"**: Check the `resources` block in config
- **"Invalid API token"**: Verify token in TimeCamp settings
- **"Module not found"**: Install dependencies with `pip install -r requirements.txt`
