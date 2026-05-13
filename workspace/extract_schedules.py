
import sqlite3
import re
from html.parser import HTMLParser
import os

class ScheduleParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.in_table = False
        self.in_tbody = False
        self.in_row = False
        self.in_cell = False
        self.cells = []
        self.current_cell = ""
        self.current_link = ""
        self.schedules = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tbody" and self.in_table:
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_row = True
            self.cells = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.current_cell = ""
        elif tag == "a" and self.in_cell:
            for name, value in attrs:
                if name == "href":
                    self.current_link = value

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if len(self.cells) >= 4:
                title = self.cells[1].strip()
                # Clean up title (remove "새글" etc)
                title = title.replace("새글", "").strip()
                date_str = self.cells[3].strip()
                link = self.current_link
                if link.startswith("/"):
                    link = "https://software.korea.ac.kr" + link
                
                self.schedules.append({
                    "title": title,
                    "link": link,
                    "date": date_str
                })
        elif tag == "td" and self.in_cell:
            self.in_cell = False
            self.cells.append(self.current_cell)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

def parse_due_date(title, post_date):
    # Try to find deadline in title: e.g. (~4/23일 17시 마감)
    # Pattern: ~M/D, ~M.D, ~M월 D일
    match = re.search(r"~(\d+)[./월](\d+)", title)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        # Year from post_date or current year
        year = post_date.split(".")[0] if "." in post_date else "2026"
        
        # Check for time: e.g. 17시
        time_match = re.search(r"(\d+)시", title)
        hour = time_match.group(1).zfill(2) if time_match else "00"
        
        return f"{year}-{month:02d}-{day:02d} {hour}:00"
    return ""

def main():
    db_path = "workspace/data/schedule.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get URL mapping
    cursor.execute("SELECT id, url FROM page_urls")
    url_map = {row[0]: row[1] for row in cursor.fetchall()}

    # Get unprocessed contents
    cursor.execute("SELECT id, url_id, content FROM page_contents WHERE is_processed = 0")
    rows = cursor.fetchall()

    all_schedules = []
    processed_ids = []

    for pc_id, url_id, content in rows:
        base_url = url_map.get(url_id, "")
        parser = ScheduleParser(base_url)
        parser.feed(content)
        
        for item in parser.schedules:
            title = item["title"]
            link = item["link"]
            post_date = item["date"]
            
            due_date = parse_due_date(title, post_date)
            
            all_schedules.append({
                "url": link,
                "content": title,
                "due_date": due_date
            })
        
        processed_ids.append(pc_id)

    conn.close()
    
    import json
    print(json.dumps({"schedules": all_schedules, "processed_ids": processed_ids}, ensure_ascii=False))

if __name__ == "__main__":
    main()
