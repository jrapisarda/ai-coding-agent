from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from contextlib import asynccontextmanager

from .routes import router
from .auth import get_current_user
from .rate_limiter import RateLimiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

app = FastAPI(
    title="Chopan AI Outreach Assistant API Gateway",
    version="1.0.0",
    description="Microservices gateway for outreach and storytelling assistant",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
rate_limiter = RateLimiter()

@app.middleware("http")
async def add_rate_limiting(request: Request, call_next):
    client_ip = request.client.host
    if not await rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"}
        )
    response = await call_next(request)
    return response

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", os.urandom(16).hex())
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/")
async def root():
    return {
        "message": "Chopan AI Outreach Assistant API Gateway",
        "version": "1.0.0",
        "services": ["content", "email", "social", "prospect", "worker"]
    }

app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )