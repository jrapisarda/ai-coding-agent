import pytest
import json
from server.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_scrape_fantasy_data_endpoint():
    response = client.get("/api/scrape-fantasy-data")
    assert response.status_code == 200
    data = response.json()
    assert "players" in data
    assert len(data["players"]) > 0
    
    player = data["players"][0]
    assert "id" in player
    assert "player_name" in player
    assert "team" in player
    assert "position" in player
    assert "power_score" in player
    assert "sleeper_rating" in player

def test_cors_headers():
    response = client.get("/api/scrape-fantasy-data")
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_player_data_structure():
    response = client.get("/api/scrape-fantasy-data")
    data = response.json()
    
    for player in data["players"]:
        assert isinstance(player["id"], int)
        assert isinstance(player["player_name"], str)
        assert isinstance(player["team"], str)
        assert isinstance(player["position"], str)
        assert isinstance(player["power_score"], (int, float))
        assert isinstance(player["sleeper_rating"], (int, float))
        assert player["position"] in ["QB", "RB", "WR", "TE"]

def test_sleeper_player_identification():
    response = client.get("/api/scrape-fantasy-data")
    data = response.json()
    
    sleeper_players = [p for p in data["players"] if p["sleeper_rating"] > 7.5]
    assert len(sleeper_players) >= 1
    
    for sleeper in sleeper_players:
        assert sleeper["sleeper_rating"] > 7.5
        assert sleeper["power_score"] > 70

if __name__ == "__main__":
    pytest.main([__file__])