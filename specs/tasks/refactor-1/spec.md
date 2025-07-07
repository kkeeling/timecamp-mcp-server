# TimeCamp MCP Server Refactoring Plan (No Backward Compatibility)

## Overview
A clean refactoring plan that fully aligns with MCP architecture standards without backward compatibility constraints.

## Phase 1: Authentication & Error Handling (Week 1)
**Priority: Critical | Complexity: Low**

### 1.1 Clean Authentication
- Remove resource-based authentication pattern entirely
- Use environment variable only: `TIMECAMP_API_TOKEN`
- Update authentication flow:
  ```python
  def get_api_token():
      token = os.getenv('TIMECAMP_API_TOKEN')
      if not token:
          raise MCPError(
              code="AUTH_MISSING",
              message="TIMECAMP_API_TOKEN environment variable not set"
          )
      return token
  ```

### 1.2 Proper MCP Error Handling
- Replace all dict error returns with MCP exceptions
- Implement error schema:
  ```python
  from fastmcp.exceptions import McpError
  
  # Use MCP standard error codes
  # - INVALID_PARAMS
  # - INTERNAL_ERROR
  # - METHOD_NOT_FOUND
  ```
- Remove success/error dict pattern completely

**Success Criteria**: 
- Clean environment-based auth only
- All errors use MCP exception pattern
- No legacy error formats

## Phase 2: Type Safety & Validation (Week 1-2)
**Priority: High | Complexity: Medium**

### 2.1 Pydantic Models
- Define request/response models for all operations:
  ```python
  from pydantic import BaseModel, Field
  
  class StartTimerRequest(BaseModel):
      task_id: int = Field(..., gt=0)
      note: Optional[str] = Field(default="", max_length=1000)
  
  class TimerResponse(BaseModel):
      timer_id: int
      task_name: str
      started_at: datetime
  ```

### 2.2 Strict Validation
- Validate all inputs with Pydantic
- Use FastMCP's built-in validation
- Return typed responses only

**Success Criteria**:
- 100% type coverage
- No unvalidated inputs
- Predictable response schemas

## Phase 3: Proper Resource/Tool Separation (Week 2-3)
**Priority: High | Complexity: High**

### 3.1 Resources (Read-Only)
Implement proper MCP resources:
```python
@mcp.resource("timecamp://projects")
async def get_projects() -> List[Project]:
    """List all projects"""

@mcp.resource("timecamp://tasks")
async def get_tasks() -> List[Task]:
    """List all tasks"""

@mcp.resource("timecamp://time-entries/{date}")
async def get_time_entries(date: str) -> List[TimeEntry]:
    """Get time entries for date"""

@mcp.resource("timecamp://timer")
async def get_timer_status() -> TimerStatus:
    """Current timer status"""
```

### 3.2 Tools (Actions Only)
Keep only state-changing operations as tools:
```python
@mcp.tool()
async def start_timer(request: StartTimerRequest) -> TimerResponse:
    """Start time tracking"""

@mcp.tool()
async def stop_timer() -> StopTimerResponse:
    """Stop current timer"""

@mcp.tool()
async def create_time_entry(request: CreateEntryRequest) -> EntryResponse:
    """Create manual time entry"""
```

### 3.3 Remove Tool-Based Reads
- Delete `list_projects` tool
- Delete `get_today_summary` tool
- Delete `get_timer_status` tool
- Delete `search_projects_and_tasks` tool
- Replace with resource access + client-side filtering

**Success Criteria**:
- Clear resource/tool separation
- No read operations in tools
- Resources return cacheable data

## Phase 4: Enhanced MCP Features (Week 3-4)
**Priority: Medium | Complexity: Medium**

### 4.1 Resource Subscriptions
- Implement change notifications for timer status
- Add subscription support for active entries

### 4.2 Proper Caching
- Add ETags to resource responses
- Implement If-None-Match support
- Cache invalidation on mutations

### 4.3 Prompts
Add prompt templates for common workflows:
```python
@mcp.prompt()
async def daily_standup_prompt() -> str:
    """Generate daily standup from time entries"""

@mcp.prompt()
async def weekly_report_prompt() -> str:
    """Generate weekly time report"""
```

## Implementation Guidelines

### File Structure
```
timecamp-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py          # Main MCP server
│   ├── models.py          # Pydantic models
│   ├── resources.py       # Resource handlers
│   ├── tools.py          # Tool handlers
│   ├── client.py         # TimeCamp API client
│   └── cache.py          # Caching logic
├── tests/
│   ├── test_resources.py
│   ├── test_tools.py
│   └── test_integration.py
├── requirements.txt
├── README.md
└── .env.example
```

### Configuration
```bash
# .env.example
TIMECAMP_API_TOKEN=your_token_here
CACHE_TTL=300
LOG_LEVEL=INFO
```

### Testing Strategy
- Unit tests for each component
- Integration tests with mock TimeCamp API
- No legacy compatibility tests needed

## Success Metrics
- Full MCP architectural compliance
- 100% type safety
- Clear separation of concerns
- <200ms response time for cached resources
- Clean, maintainable codebase

## Timeline Summary
- **Week 1**: Authentication, Error Handling, Start Type Safety
- **Week 2**: Complete Type Safety, Begin Resource/Tool Separation
- **Week 3**: Complete Resource/Tool Separation, Enhanced Features
- **Week 4**: Testing, Documentation, Polish

This plan creates a clean, modern MCP server that fully embraces the protocol's design principles without any legacy baggage.