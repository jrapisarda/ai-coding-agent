from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Content(Base):
    __tablename__ = "content"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    brief = Column(Text, nullable=False)
    content = Column(Text)
    language = Column(String, default="en")
    status = Column(String, default="draft")
    author_id = Column(String, ForeignKey("users.id"))
    reviewer_id = Column(String, ForeignKey("users.id"))
    scheduled_for = Column(DateTime)
    content_metadata = Column(JSON)  # Changed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class EmailCampaign(Base):
    __tablename__ = "email_campaigns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    from_email = Column(String, nullable=False)
    status = Column(String, default="draft")
    recipient_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    campaign_metadata = Column(JSON)  # Changed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    scheduled_for = Column(DateTime)

class SocialPost(Base):
    __tablename__ = "social_posts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content = Column(Text, nullable=False)
    platform = Column(String, nullable=False)
    status = Column(String, default="draft")
    scheduled_for = Column(DateTime)
    posted_at = Column(DateTime)
    engagement_data = Column(JSON)
    post_metadata = Column(JSON)  # Changed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Prospect(Base):
    __tablename__ = "prospects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String)
    organization = Column(String)
    status = Column(String, default="new")
    score = Column(Integer, default=0)
    prospect_metadata = Column(JSON)  # Changed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())