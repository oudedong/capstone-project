import unittest
import os
import sqlite3
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))

from schedule_db.db import (
    init_db, insert_origin_url, get_origin_urls, 
    insert_redirected_urls, get_unprocessed_redirected_urls,
    add_target_url_to_redirected_urls
)

class TestDatabaseLogic(unittest.TestCase):
    def setUp(self):
        self.db_path = 'workspace/tests/test_schedule.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_init_db(self):
        self.assertTrue(os.path.exists(self.db_path))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='origin_urls'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    def test_origin_urls(self):
        url = "https://example.com"
        summary = "Test summary"
        insert_origin_url(self.db_path, url, summary)
        origins = get_origin_urls(self.db_path)
        self.assertEqual(len(origins), 1)
        self.assertEqual(origins[0]['url'], url)
        self.assertEqual(origins[0]['summary'], summary)

    def test_unprocessed_redirected_urls(self):
        # Insert redirected URL without target_url
        insert_redirected_urls(self.db_path, "https://old.com")
        
        # Test get_unprocessed_redirected_urls (should use IS NULL)
        unprocessed = get_unprocessed_redirected_urls(self.db_path)
        self.assertEqual(len(unprocessed), 1)
        self.assertEqual(unprocessed[0]['redirected_url'], "https://old.com")
        self.assertIsNone(unprocessed[0]['target_url'])

        # Update with target_url
        add_target_url_to_redirected_urls(self.db_path, "https://old.com", "https://new.com")
        
        # Should now be processed
        unprocessed_after = get_unprocessed_redirected_urls(self.db_path)
        self.assertEqual(len(unprocessed_after), 0)

if __name__ == '__main__':
    unittest.main()
