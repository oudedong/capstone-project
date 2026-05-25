import unittest
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))

from my_scrapper import get_clean_url

class TestScrapperLogic(unittest.TestCase):
    def test_get_clean_url(self):
        # Basic URL
        self.assertEqual(get_clean_url("https://example.com/page?query=123"), "https://example.com/page")
        
        # LMS Login URL with many params
        lms_url = "https://lms.korea.ac.kr/login.php?auto_login=true&return_url=abc&cvs_lgn=true"
        self.assertEqual(get_clean_url(lms_url), "https://lms.korea.ac.kr/login.php")
        
        # URL without params
        self.assertEqual(get_clean_url("https://software.korea.ac.kr/main"), "https://software.korea.ac.kr/main")

        # URL with hash (anchor)
        # Note: urlparse behavior treats # as part of the fragment, which netloc/path doesn't include in our get_clean_url
        self.assertEqual(get_clean_url("https://example.com/page#section"), "https://example.com/page")

if __name__ == '__main__':
    unittest.main()
