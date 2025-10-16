from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    role: str = "user"

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None