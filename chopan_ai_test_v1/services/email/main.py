from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uvicorn
from datetime import datetime
from typing import List, Optional

from ..shared.database import get_db, init_db
from ..shared.models import EmailCampaign
from .models import EmailCampaignCreate, EmailCampaignResponse, EmailCampaignUpdate

app = FastAPI(
    title="Email Service",
    version="1.0.0",
    description="Email campaign management service"
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
    return {"status": "healthy", "service": "email"}

@app.get("/campaigns", response_model=List[EmailCampaignResponse])
async def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(EmailCampaign)
    if status:
        query = query.where(EmailCampaign.status == status)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    return campaigns

@app.post("/campaigns", response_model=EmailCampaignResponse)
async def create_campaign(
    campaign_data: EmailCampaignCreate,
    db: AsyncSession = Depends(get_db)
):
    campaign = EmailCampaign(
        name=campaign_data.name,
        subject=campaign_data.subject,
        content=campaign_data.content,
        from_email=campaign_data.from_email,
        status="draft",
        metadata=campaign_data.metadata or {}
    )
    
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    
    return campaign

@app.get("/campaigns/{campaign_id}", response_model=EmailCampaignResponse)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailCampaign).where(EmailCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    return campaign

@app.put("/campaigns/{campaign_id}", response_model=EmailCampaignResponse)
async def update_campaign(
    campaign_id: str,
    campaign_update: EmailCampaignUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(EmailCampaign).where(EmailCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Update fields
    for field, value in campaign_update.dict(exclude_unset=True).items():
        setattr(campaign, field, value)
    
    campaign.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)
    
    return campaign

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)