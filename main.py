import httpx
import re
import asyncio
from lxml import html
import json
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

DB_NAME = os.environ.get("DB_NAME", "default.db")

def clean_url(url: str) -> str:
    return url.split("#", 1)[0]

class RightMoveListing:
    def __init__(self, url):
        self.url = clean_url(url)
        self.html = None

    async def fetch_html(self):
        url = self.url
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.html != None:
            return self.html
        
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            self.html = r.text
            return self.html

    async def scrapePrice(self):
        htmltext = await self.fetch_html()
        tree = html.fromstring(htmltext)
        content = tree.xpath("//meta[@name='twitter:description']/@content")
        m = re.search(r'£\s*\d{1,3}(?:,\d{3})*', content[0] if content else "")
        return m.group(0) if m else None

    async def scrapeAddress(self):
        htmltext = await self.fetch_html()
        tree = html.fromstring(htmltext)
        content = tree.xpath("//meta[@name='twitter:description']/@content")
        m = re.search(r'\bin\s+(.*?)\s+for\s+£', content[0] if content else "")
        return m.group(1) if m else None
    
    async def scrapefirstimageURL(self):
        htmltext = await self.fetch_html()
        tree = html.fromstring(htmltext)
        return tree.xpath("//meta[@name='twitter:image:src']/@content")
    
    async def scrapeDescription(self):
        htmltext = await self.fetch_html()
        m = re.search(r'"description":"(.*?)"', htmltext) # Finds "description":"(capture everything until next quote)"
        return m.group(1) if m else None
    
    async def scrapeimageURL(self):
        html_content = await self.fetch_html()

        match = re.search(r'"images"\s*:\s*(\[.*?\])', html_content, re.DOTALL)
        if not match:
            return []

        try:
            image_data_list = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        return [item["url"] for item in image_data_list if isinstance(item, dict) and "url" in item]

def load_lines(path: str, limit: int | None = None) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [
            line.strip()
            for line in f
            if line.strip() and not line.lstrip().startswith("#")
        ]
    return lines[:limit] if limit else lines

async def scrape_url(url: str) -> dict[str, object]:

    listing = RightMoveListing(url)

    try:
        await listing.fetch_html()
        price, address, first_image, description, images = await asyncio.gather(
            listing.scrapePrice(),
            listing.scrapeAddress(),
            listing.scrapefirstimageURL(),
            listing.scrapeDescription(),
            listing.scrapeimageURL(),
        )

        # first_image is a list (from xpath). Convert to a single string or None.
        first_image_url = first_image[0] if isinstance(first_image, list) and first_image else None

        return {
            "url": url,
            "price": price,
            "address": address,
            "description": description,
            "firstImageUrl": first_image_url,
            "imageUrls": images if isinstance(images, list) else [],
        }

    except Exception as e:
        return {
            "url": url,
            "error": f"{type(e).__name__}: {e}",
        }

def init_db(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        with con:  
            con.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    price TEXT,
                    address TEXT,
                    description TEXT,
                    first_image_url TEXT,
                    scraped_at TEXT NOT NULL,
                    status TEXT,
                    error TEXT
                );
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS listing_images (
                    listing_id INTEGER NOT NULL,
                    image_url TEXT NOT NULL,
                    PRIMARY KEY (listing_id, image_url),
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                );
            """)
    finally:
        con.close()

def listing_exists(url: str, db_path: str) -> bool:
    url = clean_url(url)
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT 1 FROM listings WHERE url = ? LIMIT 1;",
            (url,),
        ).fetchone()
        return row is not None
    finally:
        con.close()

def insert_listing(data: dict[str, object], db_path: str) -> None:
    url = clean_url(str(data["url"]))
    scraped_at = datetime.now(timezone.utc).isoformat()

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        with con:
            # Insert the listing row (skip if already present)
            con.execute(
                """
                INSERT OR IGNORE INTO listings
                    (url, price, address, description, first_image_url, scraped_at, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    url,
                    data.get("price"),
                    data.get("address"),
                    data.get("description"),
                    data.get("firstImageUrl"),
                    scraped_at,
                    "error" if data.get("error") else "ok",
                    data.get("error"),
                ),
            )

            # If it already existed, nothing to do
            row = con.execute("SELECT id FROM listings WHERE url = ?;", (url,)).fetchone()
            if not row:
                return
            listing_id = row[0]

            # Insert image URLs (deduped by PRIMARY KEY(listing_id, image_url))
            for img_url in data.get("imageUrls", []) or []:
                con.execute(
                    "INSERT OR IGNORE INTO listing_images (listing_id, image_url) VALUES (?, ?);",
                    (listing_id, img_url),
                )
    finally:
        con.close()



"""
if __name__ == "__main__":
    init_db(DB_NAME)

    url = "https://www.rightmove.co.uk/properties/167177405#/?channel=RES_BUY"
    if not listing_exists(url, DB_NAME):
        data = asyncio.run(scrape_url(url))
        insert_listing(data, DB_NAME)

"""