from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uvicorn
from datetime import datetime
from typing import List, Optional

from ..shared.database import get_db, init_db
from ..shared.models import Prospect
from .models import ProspectCreate, ProspectResponse, ProspectUpdate

app = FastAPI(
    title="Prospect Discovery Service",
    version="1.0.0",
    description="Prospect discovery and scoring service"
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
    return {"status": "healthy", "service": "prospect"}

@app.get("/prospects", response_model=List[ProspectResponse])
async def list_prospects(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Prospect)
    if status:
        query = query.where(Prospect.status == status)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    return prospects

@app.post("/prospects", response_model=ProspectResponse)
async def create_prospect(
    prospect_data: ProspectCreate,
    db: AsyncSession = Depends(get_db)
):
    prospect = Prospect(
        name=prospect_data.name,
        email=prospect_data.email,
        organization=prospect_data.organization,
        status="new",
        score=prospect_data.score or 0,
        metadata=prospect_data.metadata or {}
    )
    
    db.add(prospect)
    await db.commit()
    await db.refresh(prospect)
    
    return prospect

@app.get("/prospects/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(prospect_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prospect not found"
        )
    
    return prospect

@app.put("/prospects/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: str,
    prospect_update: ProspectUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prospect not found"
        )
    
    # Update fields
    for field, value in prospect_update.dict(exclude_unset=True).items():
        setattr(prospect, field, value)
    
    prospect.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(prospect)
    
    return prospect

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)