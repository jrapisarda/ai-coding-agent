from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uvicorn
from datetime import datetime
from typing import List, Optional

from ..shared.database import get_db, init_db
from ..shared.models import Content
from .openai_client import OpenAIClient
from .models import ContentCreate, ContentResponse, ContentUpdate

app = FastAPI(
    title="Content Service",
    version="1.0.0",
    description="Content generation and management service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = OpenAIClient()

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "content"}

@app.get("/content", response_model=List[ContentResponse])
async def list_content(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Content)
    if status:
        query = query.where(Content.status == status)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    content_items = result.scalars().all()
    return content_items

@app.post("/content", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    db: AsyncSession = Depends(get_db)
):
    # Generate content using OpenAI
    generated_content = await openai_client.generate_content(
        title=content_data.title,
        brief=content_data.brief,
        language=content_data.language
    )
    
    # Create content record
    content = Content(
        title=content_data.title,
        brief=content_data.brief,
        content=generated_content,
        language=content_data.language,
        status="draft",
        author_id=content_data.author_id,
        content_metadata=content_data.content_metadata or {}
    )
    
    db.add(content)
    await db.commit()
    await db.refresh(content)
    
    return content

@app.get("/content/{content_id}", response_model=ContentResponse)
async def get_content(content_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    return content

@app.put("/content/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: str,
    content_update: ContentUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Update fields
    for field, value in content_update.dict(exclude_unset=True).items():
        setattr(content, field, value)
    
    content.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(content)
    
    return content

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)