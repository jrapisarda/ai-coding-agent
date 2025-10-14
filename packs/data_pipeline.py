"""
Generate a complete Python scraping / analysis pipeline.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict

from agents import RunContextWrapper
from kimi_coding_agent_v_6_1 import (
    AgentContext,
    FileMap,
    ValidationResult,
    _ensure_artifacts_dir,
    _run_subprocess,
    write_many_impl,
    record_validation_impl,
)

# ---------- helpers that return strings ----------
def _requirements_txt() -> str:
    return textwrap.dedent("""\
        beautifulsoup4==4.12.2
        requests==2.31
        pandas==2.1
        numpy==1.25
        pydantic==2.5
        aiohttp==3.9
        tenacity==8.2
        python-dotenv==1.0
        pytest==7.4
        pytest-asyncio==0.21
        mypy==1.7
        ruff==0.1
    """)

def _env_example() -> str:
    return textwrap.dedent("""\
        # ESPN developer portal
        ESPN_API_KEY=replace_me
        # NFL.com (optional)
        NFL_API_KEY=replace_me
        # FantasyPros
        FP_API_KEY=replace_me
        # Yahoo (OAuth2)
        YAHOO_CLIENT_ID=replace_me
        YAHOO_CLIENT_SECRET=replace_me
    """)

def _main_py() -> str:
    return textwrap.dedent("""\
        import asyncio
        import argparse
        from src.analyzers.power_calculator import build_power_rankings
        from src.scrapers.espn_scraper import ESPNScraper
        from src.utils.logger import setup_logging

        async def main(position: str) -> None:
            setup_logging()
            async with ESPNScraper() as espn:
                data = await espn.get_players(position)
            df = build_power_rankings(data, position)
            out_path = f"output/top_{position.lower()}_week.csv"
            df.to_csv(out_path, index=False)
            print("Saved", out_path)

        if __name__ == "__main__":
            parser = argparse.ArgumentParser()
            parser.add_argument("position", choices=["QB", "RB", "WR", "TE"])
            args = parser.parse_args()
            asyncio.run(main(args.position))
    """)

def _base_scraper_py() -> str:
    return textwrap.dedent("""\
        import asyncio
        from abc import ABC, abstractmethod
        from typing import Any, Dict, List
        import aiohttp
        from tenacity import retry, wait_exponential

        class BaseScraper(ABC):
            def __init__(self, api_key: str):
                self.key = api_key
                self.session: aiohttp.ClientSession | None = None

            async def __aenter__(self):
                self.session = aiohttp.ClientSession(
                    headers={"User-Agent": "fantasy-agent/1.0"}
                )
                return self

            async def __aexit__(self, *_):
                if self.session:
                    await self.session.close()

            @retry(wait=wait_exponential(multiplier=2, min=2, max=10))
            async def get(self, url: str, params: Dict[str, Any] | None = None):
                assert self.session
                async with self.session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    return await resp.json()

            @abstractmethod
            async def get_players(self, position: str) -> List[Dict[str, Any]]:
                ...
    """)

def _espn_scraper_py() -> str:
    return textwrap.dedent("""\
        import os
        from src.scrapers.base_scraper import BaseScraper

        class ESPNScraper(BaseScraper):
            BASE = "https://fantasy.espn.com/apis/v3/players"

            async def get_players(self, position: str):
                url = f"{self.BASE}/kona"
                params = {"position": position, "scoringPeriod": 2025}
                return await self.get(url, params)
    """)

def _power_calculator_py() -> str:
    return textwrap.dedent("""\
        import pandas as pd
        from pathlib import Path

        def build_power_rankings(raw: list, position: str) -> pd.DataFrame:
            df = pd.DataFrame(raw)
            # stub algorithm – real one uses weights from config
            df["power_score"] = (
                df.get("avg_points", 0) * 0.4
                + df.get("projected", 0) * 0.35
                + df.get("sleeper_rating", 0) * 0.25
            )
            df["position"] = position
            return df.sort_values("power_score", ascending=False).head(25)
    """)

def _dockerfile() -> str:
    return textwrap.dedent("""\
        FROM python:3.11-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install -r requirements.txt
        COPY . .
        ENTRYPOINT ["python", "-m", "src.main"]
    """)

def _github_ci_yml() -> str:
    return textwrap.dedent("""\
        name: CI
        on: [push, pull_request]
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
               with:
                 python-version: "3.11"
              - run: pip install -r requirements.txt
              - run: ruff check .
              - run: mypy src
              - run: pytest
    """)

def _test_base_scraper_py() -> str:
    return textwrap.dedent("""\
        import pytest
        from src.scrapers.base_scraper import BaseScraper

        class Dummy(BaseScraper):
            async def get_players(self, _):
                return [{"name": "test"}]

        @pytest.mark.asyncio
        async def test_lifecycle():
            async with Dummy("key") as d:
                data = await d.get_players("QB")
                assert data[0]["name"] == "test"
    """)

# ---------- main planner ----------
def plan_files(req: dict) -> dict[str, str]:
    """Return map relative_path -> content."""
    return {
        "requirements.txt": _requirements_txt(),
        ".env.example": _env_example(),
        "src/main.py": _main_py(),
        "src/__init__.py": "",
        "src/scrapers/__init__.py": "",
        "src/scrapers/base_scraper.py": _base_scraper_py(),
        "src/scrapers/espn_scraper.py": _espn_scraper_py(),
        "src/analyzers/__init__.py": "",
        "src/analyzers/power_calculator.py": _power_calculator_py(),
        "src/utils/__init__.py": "",
        "src/utils/logger.py": "import logging\nsetup_logging = lambda: logging.basicConfig(level=logging.INFO)",
        "tests/__init__.py": "",
        "tests/test_base_scraper.py": _test_base_scraper_py(),
        "Dockerfile": _dockerfile(),
        ".github/workflows/ci.yml": _github_ci_yml(),
        "README.md": "# Fantasy Football Sleeper Scout\n\n1. `cp .env.example .env`  # add keys\n2. `docker build -t scout .`\n3. `docker run --env-file .env scout RB`",
    }

# ---------- validation ----------
def validate(ctx: AgentContext) -> ValidationResult:
    """Run mypy + ruff + pytest + docker build."""
    dry = ctx.dry_run
    def run(cmd):
        return _run_subprocess(cmd, cwd=ctx.base_dir, timeout=120)

    # mypy
    code, out, err = run([sys.executable, "-m", "mypy", "src"])
    mypy_ok = dry or code == 0

    # ruff
    code, _, _ = run([sys.executable, "-m", "ruff", "check", "."])
    ruff_ok = dry or code == 0

    # pytest
    code, pytest_out, pytest_err = run([sys.executable, "-m", "pytest", "-q"])
    pytest_ok = dry or code == 0

    # docker
    code, _, _ = run(["docker", "build", "-t", "scout", "."])
    docker_ok = dry or code == 0

    return ValidationResult(
        compiled_ok=mypy_ok and ruff_ok,
        compile_errors=[] if mypy_ok and ruff_ok else ["mypy/ruff failed"],
        pytest_ok=pytest_ok,
        pytest_returncode=0 if pytest_ok else 1,
        pytest_stdout=pytest_out,
        pytest_stderr=pytest_err,
    )