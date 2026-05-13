
import asyncio
import json
import os
import sys

# Add scripts/new to path
sys.path.append('/home/oudedong/capstone-agent/scripts/new')

from browser_crawler import get_page
from my_db import insert_page_content, _get, sqlite3

DB_PATH = '/home/oudedong/capstone-agent/workspace/data/schedule.db'

async def process_urls():
    # 1. Find URLs that don't have content in page_contents
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url FROM page_urls WHERE id NOT IN (SELECT url_id FROM page_contents);")
    rows = cursor.fetchall()
    conn.close()

    print(f"Found {len(rows)} URLs to crawl.")

    for url_id, url in rows:
        print(f"Crawling ID {url_id}: {url}")
        try:
            result_json = await get_page(url)
            if result_json.startswith("페이지 로드 실패"):
                print(f"Failed to crawl {url}: {result_json}")
                continue
            
            result = json.loads(result_json)
            content = result.get('content', '')
            
            if content:
                res = insert_page_content(DB_PATH, url_id, content)
                print(f"Saved content for ID {url_id}: {res}")
            else:
                print(f"No content extracted for ID {url_id}")
        except Exception as e:
            print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    asyncio.run(process_urls())
