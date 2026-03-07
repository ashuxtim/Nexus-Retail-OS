# FILE: python_server/routes/media.py
# Media endpoints: POST /scan_receipt, POST /transcribe

import asyncio
from fastapi import APIRouter, UploadFile, File

from core.startup import load_settings
from ai_engine.vision import scan_receipt_engine
from ai_engine.voice import transcribe_audio_engine
from scripts.backend_logging import get_logger

router = APIRouter()
logger = get_logger("NexusAI_Backend")


@router.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Delegate to AI Engine Vision Module with API Key Injection"""
    logger.info("Scanning Receipt...")

    # 1. Get the content
    content = await file.read()

    # 2. Load the key using settings logic
    settings = load_settings()
    api_key = settings.get("GROQ_API_KEY")

    # 3. Pass both to the engine
    return await scan_receipt_engine(content, api_key=api_key)


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Delegate to AI Engine Voice Module with API Key Injection"""
    content = await file.read()

    # 1. Load the key explicitly
    settings = load_settings()
    api_key = settings.get("GROQ_API_KEY")

    if not api_key:
        logger.error("Attempted transcription but GROQ_API_KEY is missing in config.")

    # 2. Pass it to the engine (offload sync work from event loop)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: transcribe_audio_engine(content, file.filename, api_key=api_key)
    )
