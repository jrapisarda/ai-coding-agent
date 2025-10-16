from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class ProspectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    organization: Optional[str] = Field(None, max_length=200)
    score: Optional[int] = Field(None, ge=0, le=100)
    prospect_metadata: Optional[Dict[str, Any]] = None

class ProspectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    organization: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    prospect_metadata: Optional[Dict[str, Any]] = None

class ProspectResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    organization: Optional[str]
    status: str
    score: int
    prospect_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True