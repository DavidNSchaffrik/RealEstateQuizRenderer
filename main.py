import httpx
import re
import asyncio
from lxml import html
import json

class RightMoveListing:
    def __init__(self, url):
        self.url = url

    async def scrapePrice(self):
        url = self.url.split("#", 1)[0]
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()

        tree = html.fromstring(r.text)
        content = tree.xpath("//meta[@name='twitter:description']/@content")
        m = re.search(r'£\s*\d{1,3}(?:,\d{3})*', content[0] if content else "")
        return m.group(0) if m else None


    async def scrapeAddress(self):
        url = self.url.split("#", 1)[0]
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()

        tree = html.fromstring(r.text)
        content = tree.xpath("//meta[@name='twitter:description']/@content")
        m = re.search(r'\bin\s+(.*?)\s+for\s+£', content[0] if content else "")
        return m.group(1) if m else None
    

    async def scrapefirstimageURL(self):
        url = self.url.split("#", 1)[0]
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()

        tree = html.fromstring(r.text)
        return tree.xpath("//meta[@name='twitter:image:src']/@content")
    
    async def scrapeDescription(self):
        url = self.url.split("#", 1)[0]
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()

        # Matches: "description":"(capture everything until next quote)"
        m = re.search(r'"description":"(.*?)"', r.text)
        return m.group(1) if m else None
    



    async def scrapeimageURL(self):
            # Clean the URL before requesting
            url = self.url.split("#", 1)[0]
            url = url.split("?", 1)[0]
            
            # Use standard headers to look like a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.rightmove.co.uk/",
            }

            print(f"Requesting: {url}")
            async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
                try:
                    r = await client.get(url)
                    r.raise_for_status() # Raise exception for bad status codes (4xx, 5xx)
                    html_content = r.text
                    print("Successfully retrieved HTML.")
                except httpx.RequestError as e:
                    print(f"An error occurred while requesting {e.request.url!r}.")
                    return []
                except httpx.HTTPStatusError as e:
                    print(f"Error response {e.response.status_code} while requesting {e.request.url!r}.")
                    return []
            match = re.search(r'"images"\s*:\s*(\[.*?\])', html_content, re.DOTALL)

            if not match:
                print("Could not find the 'images' JSON block in the HTML source.")
                return []

            json_data_string = match.group(1)
            
            try:
                image_data_list = json.loads(json_data_string)
                final_urls = [item['url'] for item in image_data_list if 'url' in item]
                
                print(f"Found {len(final_urls)} images.")
                return final_urls

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON data: {e}")
                print(f"Problematic string snippet: {json_data_string[:100]}...")
                return []
            except Exception as e:
                print(f"An unexpected error occurred during parsing: {e}")
                return []


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
    test = asyncio.run(scrape_url("https://www.rightmove.co.uk/properties/163722422#/?channel=RES_BUY"))
    print(test)




        


