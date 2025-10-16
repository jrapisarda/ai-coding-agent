from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class EmailCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=10)
    from_email: EmailStr
    campaign_metadata: Optional[Dict[str, Any]] = None

class EmailCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    from_email: Optional[EmailStr] = None
    status: Optional[str] = None
    recipient_count: Optional[int] = Field(None, ge=0)
    sent_count: Optional[int] = Field(None, ge=0)
    campaign_metadata: Optional[Dict[str, Any]] = None

class EmailCampaignResponse(BaseModel):
    id: str
    name: str
    subject: str
    content: str
    from_email: str
    status: str
    recipient_count: int
    sent_count: int
    campaign_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    scheduled_for: Optional[datetime]
    
    class Config:
        from_attributes = True