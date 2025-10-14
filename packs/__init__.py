import re
from importlib import import_module
from typing import Dict

KEYWORDS: Dict[str, str] = {
    r"spa|react|vue|svelte|front.end|vite": "spa_react",
    r"streamlit|gradio|dash|data.app": "streamlit",
    r"fastapi|flask|django|api|rest|backend": "fastapi",
    r"ml|training|pipeline|sklearn|pytorch|tensorflow": "ml_training",
    r"scraper|etl|batch|cron|pipeline": "data_pipeline",
    r"cli|click|argparse|typer|command.line": "python_cli",
    r"refactor|legacy|cleanup|modernise": "refactor",
    r"terraform|pulumi|infra|iac": "iac_terraform",
}

def classify(requirements: dict) -> str:
    flat = str(requirements).lower()
    for regex, pack in KEYWORDS.items():
        if re.search(regex, flat):
            return pack
    return "unknown"

def get_pack(name: str):
    return import_module(f"packs.{name}")