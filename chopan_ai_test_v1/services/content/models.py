from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    brief: str = Field(..., min_length=10, max_length=1000)
    language: str = Field(default="en", regex="^[a-z]{2}$")
    author_id: str
    content_metadata: Optional[Dict[str, Any]] = None

class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    brief: Optional[str] = Field(None, min_length=10, max_length=1000)
    content: Optional[str] = None
    language: Optional[str] = Field(None, regex="^[a-z]{2}$")
    status: Optional[str] = None
    reviewer_id: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    content_metadata: Optional[Dict[str, Any]] = None

class ContentResponse(BaseModel):
    id: str
    title: str
    brief: str
    content: Optional[str]
    language: str
    status: str
    author_id: str
    reviewer_id: Optional[str]
    scheduled_for: Optional[datetime]
    content_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True