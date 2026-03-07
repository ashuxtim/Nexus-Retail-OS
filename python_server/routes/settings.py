# FILE: python_server/routes/settings.py
# Settings endpoints: POST /settings, GET /settings

import os
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from core import state
from core.startup import load_settings, initialize_ai
from core.key_store import save_keys as save_encrypted_keys
from scripts.backend_logging import get_logger

router = APIRouter()
logger = get_logger("NexusAI_Backend")


class SettingsModel(BaseModel):
    google_api_key: str
    groq_api_key: str


@router.post("/settings")
async def update_settings(settings: SettingsModel, background_tasks: BackgroundTasks):
    """
    Receive API keys from Electron and store in memory (os.environ) ONLY.
    Keys are NOT written to disk - they come from encrypted DB on startup.
    """
    # Inject into process environment (RAM only)
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
        logger.info("✅ GROQ API Key received and loaded into memory")

    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
        logger.info("✅ Google API Key received and loaded into memory")

    # Persist keys to encrypted file (survives process restarts)
    keys_to_save = {}
    if settings.groq_api_key:
        keys_to_save["GROQ_API_KEY"] = settings.groq_api_key
    if settings.google_api_key:
        keys_to_save["GOOGLE_API_KEY"] = settings.google_api_key
    if keys_to_save:
        save_encrypted_keys(keys_to_save, state.BASE_DIR)

    # Reinitialize AI with new keys
    background_tasks.add_task(initialize_ai)

    return {
        "status": "updated",
        "message": "Keys loaded into memory. AI initializing...",
    }


@router.get("/settings")
async def get_settings():
    return load_settings()
