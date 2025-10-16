from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uvicorn
from datetime import datetime
from typing import List, Optional

from ..shared.database import get_db, init_db
from ..shared.models import SocialPost
from .models import SocialPostCreate, SocialPostResponse, SocialPostUpdate

app = FastAPI(
    title="Social Media Service",
    version="1.0.0",
    description="Social media posting and management service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "social"}

@app.get("/posts", response_model=List[SocialPostResponse])
async def list_posts(
    skip: int = 0,
    limit: int = 100,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(SocialPost)
    if platform:
        query = query.where(SocialPost.platform == platform)
    if status:
        query = query.where(SocialPost.status == status)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    posts = result.scalars().all()
    return posts

@app.post("/posts", response_model=SocialPostResponse)
async def create_post(
    post_data: SocialPostCreate,
    db: AsyncSession = Depends(get_db)
):
    post = SocialPost(
        content=post_data.content,
        platform=post_data.platform,
        status="draft",
        scheduled_for=post_data.scheduled_for,
        metadata=post_data.metadata or {}
    )
    
    db.add(post)
    await db.commit()
    await db.refresh(post)
    
    return post

@app.get("/posts/{post_id}", response_model=SocialPostResponse)
async def get_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    return post

@app.put("/posts/{post_id}", response_model=SocialPostResponse)
async def update_post(
    post_id: str,
    post_update: SocialPostUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Update fields
    for field, value in post_update.dict(exclude_unset=True).items():
        setattr(post, field, value)
    
    post.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(post)
    
    return post

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)