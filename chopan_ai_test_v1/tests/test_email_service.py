import pytest
from fastapi.testclient import TestClient
from services.email.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "email"

def test_create_campaign():
    """Test email campaign creation"""
    campaign_data = {
        "name": "Test Campaign",
        "subject": "Test Subject",
        "content": "This is a test email campaign content",
        "from_email": "test@example.com",
        "metadata": {"test": "data"}
    }
    
    response = client.post("/campaigns", json=campaign_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == campaign_data["name"]
    assert data["subject"] == campaign_data["subject"]
    assert data["status"] == "draft"
    assert "id" in data

def test_list_campaigns():
    """Test listing email campaigns"""
    response = client.get("/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_campaign():
    """Test getting specific campaign"""
    # First create a campaign
    campaign_data = {
        "name": "Test Campaign 2",
        "subject": "Test Subject 2",
        "content": "Another test email campaign content",
        "from_email": "test2@example.com"
    }
    
    create_response = client.post("/campaigns", json=campaign_data)
    campaign_id = create_response.json()["id"]
    
    # Now get it
    response = client.get(f"/campaigns/{campaign_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == campaign_id
    assert data["name"] == campaign_data["name"]

def test_update_campaign():
    """Test updating campaign"""
    # First create a campaign
    campaign_data = {
        "name": "Test Campaign 3",
        "subject": "Test Subject 3",
        "content": "Test campaign content for update",
        "from_email": "test3@example.com"
    }
    
    create_response = client.post("/campaigns", json=campaign_data)
    campaign_id = create_response.json()["id"]
    
    # Update it
    update_data = {
        "name": "Updated Campaign Name",
        "status": "scheduled"
    }
    
    response = client.put(f"/campaigns/{campaign_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["status"] == update_data["status"]