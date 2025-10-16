import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all main modules can be imported"""
    try:
        from services.shared.models import User, Content, EmailCampaign, SocialPost, Prospect
        from services.shared.config import load_config
        assert True
    except ImportError as e:
        assert False, f"Failed to import shared modules: {e}"

def test_models_creation():
    """Test that model classes can be instantiated"""
    try:
        from services.shared.models import User, Content, EmailCampaign, SocialPost, Prospect
        
        # Test User model
        user = User(email="test@example.com", name="Test User", role="user")
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        
        # Test Content model
        content = Content(title="Test Content", brief="Test brief", author_id="test-user")
        assert content.title == "Test Content"
        assert content.brief == "Test brief"
        
        # Test EmailCampaign model
        campaign = EmailCampaign(name="Test Campaign", subject="Test Subject", content="Test content", from_email="test@example.com")
        assert campaign.name == "Test Campaign"
        assert campaign.subject == "Test Subject"
        
        # Test SocialPost model
        post = SocialPost(content="Test post content", platform="twitter")
        assert post.content == "Test post content"
        assert post.platform == "twitter"
        
        # Test Prospect model
        prospect = Prospect(name="Test Prospect", email="prospect@example.com", organization="Test Corp")
        assert prospect.name == "Test Prospect"
        assert prospect.email == "prospect@example.com"
        
    except Exception as e:
        assert False, f"Failed to create model instances: {e}"

def test_config_loading():
    """Test that configuration can be loaded"""
    try:
        from services.shared.config import load_config
        config = load_config()
        assert isinstance(config, dict)
        assert "database" in config
        assert "redis" in config
        assert "openai" in config
    except Exception as e:
        assert False, f"Failed to load configuration: {e}"