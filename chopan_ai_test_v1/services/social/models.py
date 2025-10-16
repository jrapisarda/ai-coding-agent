from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class SocialPostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    platform: str = Field(..., regex="^(twitter|linkedin|facebook|instagram)$")
    scheduled_for: Optional[datetime] = None
    post_metadata: Optional[Dict[str, Any]] = None

class SocialPostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=1000)
    platform: Optional[str] = Field(None, regex="^(twitter|linkedin|facebook|instagram)$")
    status: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    engagement_data: Optional[Dict[str, Any]] = None
    post_metadata: Optional[Dict[str, Any]] = None

class SocialPostResponse(BaseModel):
    id: str
    content: str
    platform: str
    status: str
    scheduled_for: Optional[datetime]
    posted_at: Optional[datetime]
    engagement_data: Optional[Dict[str, Any]]
    post_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True