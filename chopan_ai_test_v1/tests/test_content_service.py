import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.content.main import app
from services.shared.models import Base

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "content"

def test_create_content():
    """Test content creation"""
    content_data = {
        "title": "Test Content",
        "brief": "This is a test content brief",
        "language": "en",
        "author_id": "test-user-123",
        "metadata": {"test": "data"}
    }
    
    response = client.post("/content", json=content_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == content_data["title"]
    assert data["brief"] == content_data["brief"]
    assert data["status"] == "draft"
    assert "id" in data

def test_list_content():
    """Test listing content"""
    response = client.get("/content")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_content():
    """Test getting specific content"""
    # First create content
    content_data = {
        "title": "Test Content 2",
        "brief": "Another test content brief",
        "language": "en",
        "author_id": "test-user-456"
    }
    
    create_response = client.post("/content", json=content_data)
    content_id = create_response.json()["id"]
    
    # Now get it
    response = client.get(f"/content/{content_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == content_id
    assert data["title"] == content_data["title"]

def test_update_content():
    """Test updating content"""
    # First create content
    content_data = {
        "title": "Test Content 3",
        "brief": "Test brief for update",
        "language": "en",
        "author_id": "test-user-789"
    }
    
    create_response = client.post("/content", json=content_data)
    content_id = create_response.json()["id"]
    
    # Update it
    update_data = {
        "title": "Updated Title",
        "status": "review"
    }
    
    response = client.put(f"/content/{content_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == update_data["title"]
    assert data["status"] == update_data["status"]