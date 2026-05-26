import asyncio
from pathlib import Path
import os
from schedule_db import run_extraction

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.path.join(BASE_DIR, 'workspace', 'data', 'schedule.db')
SESSION_FILE = os.path.join(BASE_DIR, 'workspace', 'data', 'session.json')
async def run():
    await run_extraction(DB_PATH, SESSION_FILE)
asyncio.run(run())