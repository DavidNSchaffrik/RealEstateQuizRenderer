import httpx
import re
import asyncio
from lxml import html
import json

class RightMoveListing:
    def __init__(self, url):
        self.url = url
        self.html = None

    async def fetch_html(self):
        url = self.url.split("#", 1)[0]
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.html != None:
            return self.html
        
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

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




if __name__ == "__main__":
    test = RightMoveListing("https://www.rightmove.co.uk/properties/167177405#/?channel=RES_BUY")
    p = asyncio.run(test.scrapePrice())
    print(str(p))