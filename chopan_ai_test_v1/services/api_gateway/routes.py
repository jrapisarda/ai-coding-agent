from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
import httpx
import os
from ..shared.config import config

router = APIRouter()

SERVICE_URLS = {
    "content": os.getenv("CONTENT_SERVICE_URL", "http://localhost:8001"),
    "email": os.getenv("EMAIL_SERVICE_URL", "http://localhost:8002"),
    "social": os.getenv("SOCIAL_SERVICE_URL", "http://localhost:8003"),
    "prospect": os.getenv("PROSPECT_SERVICE_URL", "http://localhost:8004"),
}

async def proxy_request(service_name: str, path: str, method: str = "GET", **kwargs):
    """Proxy request to microservice"""
    if service_name not in SERVICE_URLS:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    service_url = SERVICE_URLS[service_name]
    url = f"{service_url}{path}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method, url, **kwargs)
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")

@router.get("/content")
async def list_content():
    return await proxy_request("content", "/content")

@router.post("/content")
async def create_content(content_data: dict):
    return await proxy_request("content", "/content", method="POST", json=content_data)

@router.get("/content/{content_id}")
async def get_content(content_id: str):
    return await proxy_request("content", f"/content/{content_id}")

@router.get("/email/campaigns")
async def list_email_campaigns():
    return await proxy_request("email", "/campaigns")

@router.post("/email/campaigns")
async def create_email_campaign(campaign_data: dict):
    return await proxy_request("email", "/campaigns", method="POST", json=campaign_data)

@router.post("/email/campaigns/{campaign_id}/send")
async def send_email_campaign(campaign_id: str):
    return await proxy_request("email", f"/campaigns/{campaign_id}/send", method="POST")

@router.get("/social/posts")
async def list_social_posts():
    return await proxy_request("social", "/posts")

@router.post("/social/posts")
async def create_social_post(post_data: dict):
    return await proxy_request("social", "/posts", method="POST", json=post_data)

@router.post("/social/posts/{post_id}/publish")
async def publish_social_post(post_id: str):
    return await proxy_request("social", f"/posts/{post_id}/publish", method="POST")

@router.get("/prospects")
async def list_prospects():
    return await proxy_request("prospect", "/prospects")

@router.post("/prospects/discover")
async def discover_prospects(query_data: dict):
    return await proxy_request("prospect", "/discover", method="POST", json=query_data)

@router.get("/prospects/{prospect_id}")
async def get_prospect(prospect_id: str):
    return await proxy_request("prospect", f"/prospects/{prospect_id}")

@router.post("/snapshots")
async def create_snapshot():
    return await proxy_request("content", "/snapshots", method="POST")

@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str):
    return await proxy_request("content", f"/snapshots/{snapshot_id}/restore", method="POST")