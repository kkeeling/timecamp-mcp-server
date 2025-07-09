#!/usr/bin/env python3
"""
Pydantic models for TimeCamp MCP Server
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# Request Models
class StartTimerRequest(BaseModel):
    """Request model for starting a timer"""
    task_id: int = Field(..., gt=0, description="Task ID to start timer for")
    note: Optional[str] = Field(default="", max_length=1000, description="Optional note for the timer")


class CreateTimeEntryRequest(BaseModel):
    """Request model for creating a manual time entry"""
    task_id: int = Field(..., gt=0, description="Task ID for the time entry")
    date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}$', description="Start time in HH:MM format")
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}$', description="End time in HH:MM format")
    note: Optional[str] = Field(default="", max_length=1000, description="Optional note for the entry")
    
    @field_validator('end_time')
    @classmethod
    def validate_end_after_start(cls, v, info):
        """Ensure end time is after start time"""
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('End time must be after start time')
        return v


class SearchRequest(BaseModel):
    """Request model for searching projects and tasks"""
    query: str = Field(..., min_length=1, max_length=200, description="Search query")


# Response Models
class TimerResponse(BaseModel):
    """Response model for timer operations"""
    message: str
    timer_id: int
    task_id: int
    task_name: str
    started_at: Optional[str] = None
    project_name: Optional[str] = None


class StopTimerResponse(BaseModel):
    """Response model for stopping timer"""
    message: str
    duration: str
    duration_seconds: int
    task_name: str
    task_id: Optional[int] = None
    timer_id: Optional[int] = None


class TimerStatusResponse(BaseModel):
    """Response model for timer status"""
    is_running: bool
    message: Optional[str] = None
    task_name: Optional[str] = None
    task_id: Optional[int] = None
    timer_id: Optional[int] = None
    project_name: Optional[str] = None
    elapsed_time: Optional[str] = None
    elapsed_seconds: Optional[int] = None
    start_time: Optional[str] = None


class SearchResultItem(BaseModel):
    """Individual search result"""
    type: str = Field(..., pattern='^(project|task)$')
    id: int
    name: str
    match_score: float = Field(..., ge=0.0, le=1.0)
    project_name: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search results"""
    results: List[SearchResultItem]
    total_results: int
    query: str


class TimeEntryResponse(BaseModel):
    """Response model for time entry creation"""
    entry_id: int
    task_id: int
    task_name: str
    project_name: str
    date: str
    start_time: str
    end_time: str
    duration: str
    duration_seconds: int
    note: str


class DailySummaryEntry(BaseModel):
    """Individual entry in daily summary"""
    task_name: str
    task_id: int
    project_name: str
    duration: str
    duration_seconds: int
    notes: List[str] = Field(default_factory=list)


class DailySummaryResponse(BaseModel):
    """Response model for daily summary"""
    date: str
    total_time: str
    total_seconds: int
    entries: List[DailySummaryEntry]
    entry_count: int
    is_timer_running: bool
    current_task: Optional[str] = None
    current_task_id: Optional[int] = None


class ProjectInfo(BaseModel):
    """Individual project information"""
    id: int
    name: str
    color: str = Field(default="#4CAF50")
    tasks_count: int = Field(ge=0)
    archived: bool = Field(default=False)


class ProjectListResponse(BaseModel):
    """Response model for project list"""
    projects: List[ProjectInfo]
    total_count: int
    include_archived: bool


# TimeCamp API Models
class TimeCampProject(BaseModel):
    """TimeCamp project data model"""
    id: int
    name: str
    color: Optional[str] = None
    archived: Optional[str] = None
    
    @property
    def is_archived(self) -> bool:
        return self.archived == '1'


class TimeCampTask(BaseModel):
    """TimeCamp task data model"""
    id: int
    name: str
    project_id: Optional[int] = None
    archived: Optional[str] = None
    
    @property
    def is_archived(self) -> bool:
        return self.archived == '1'


class TimeCampTimeEntry(BaseModel):
    """TimeCamp time entry data model"""
    id: Optional[int] = None
    task_id: int
    date: str
    start_time: str
    end_time: str
    duration: int
    note: Optional[str] = None


class TimeCampTimer(BaseModel):
    """TimeCamp timer data model"""
    timer_id: Optional[int] = None
    task_id: Optional[int] = None
    name: Optional[str] = None
    project_name: Optional[str] = None
    started_at: Optional[str] = None