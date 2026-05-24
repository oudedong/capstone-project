import asyncio
from pathlib import Path
import os
from schedule_db import run_extraction

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.path.join(BASE_DIR, 'workspace', 'data', 'schedule_test.db')
SESSION_FILE = Path("/home/oudedong/capstone-agent/.gemini/session.json")
async def run():
    await run_extraction(DB_PATH, SESSION_FILE)
asyncio.run(run())