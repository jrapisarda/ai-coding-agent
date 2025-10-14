from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/scrape-fantasy-data")
async def scrape_fantasy_data():
    await asyncio.sleep(1)
    return {
        "players": [
            {
                "id": 1,
                "player_name": "Christian McCaffrey",
                "team": "SF",
                "position": "RB",
                "power_score": 94.2,
                "sleeper_rating": 3.2,
                "matchup_difficulty": "Favorable",
                "risk_level": "Low"
            },
            {
                "id": 2,
                "player_name": "Jaylen Warren",
                "team": "PIT",
                "position": "RB",
                "power_score": 78.5,
                "sleeper_rating": 8.9,
                "matchup_difficulty": "Neutral",
                "risk_level": "Medium"
            }
        ]
    }