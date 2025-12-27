import httpx
import re
import asyncio
from lxml import html

class RightMoveListing:
    def __init__(self, url):
        self.url = url

    async def scrapePrice(self):
        url = self.url.split("#", 1)[0]  # fragment not sent to server
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()

        tree = html.fromstring(r.text)
        content = tree.xpath("//meta[@name='twitter:description']/@content")
        m = re.search(r'£\s*\d{1,3}(?:,\d{3})*', content[0] if content else "")
        return m.group(0) if m else None

