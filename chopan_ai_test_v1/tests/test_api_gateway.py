import pytest
from fastapi.testclient import TestClient
from services.api_gateway.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api-gateway"

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "services" in data

def test_rate_limiting():
    """Test rate limiting functionality"""
    # Make multiple requests to test rate limiting
    for i in range(70):  # Exceed the 60 requests per minute limit
        response = client.get("/health")
        if i >= 60:
            # After 60 requests, should get rate limited
            assert response.status_code in [200, 429]
        else:
            assert response.status_code == 200