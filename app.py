# app.py
import asyncio
import re

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from main import (
    DB_NAME,
    clean_url,
    init_db,
    listing_exists,
    insert_listing,
    scrape_url,
    get_recent_listings,
    get_listing_by_id,
    get_listing_images,
)

MAX_URLS = 50
CONCURRENCY = 5

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db(DB_NAME)


def extract_urls(text: str) -> list[str]:
    raw = re.findall(r"https?://[^\s]+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for u in raw:
        u = clean_url(u.strip())
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "results": None, "error": None},
    )


@app.post("/scrape", response_class=HTMLResponse)
async def scrape_and_save(
    request: Request,
    urls: str | None = Form(None),  # textarea name="urls"
    url: str | None = Form(None),   # optional old field name="url"
):
    text = (urls or "").strip()
    if not text and url:
        text = url.strip()

    if not text:
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "results": None, "error": "No URL(s) provided."},
            status_code=400,
        )

    url_list = extract_urls(text)
    if not url_list:
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "results": None, "error": "No valid URLs found."},
            status_code=400,
        )

    url_list = url_list[:MAX_URLS]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def handle_one(u: str, sem: asyncio.Semaphore) -> dict:
        async with sem:
            if "rightmove.co.uk" not in u:
                return {"url": u, "status": "invalid", "error": "Not a Rightmove URL"}

            exists = await run_in_threadpool(listing_exists, u, DB_NAME)
            if exists:
                return {"url": u, "status": "exists", "error": None}

            data = await scrape_url(u)
            await run_in_threadpool(insert_listing, data, DB_NAME)

            if data.get("error"):
                return {"url": u, "status": "error", "error": data["error"]}
            return {"url": u, "status": "inserted", "error": None}

    results = await asyncio.gather(*(handle_one(u, sem) for u in url_list))

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "results": results, "error": None},
    )


@app.get("/listings", response_class=HTMLResponse)
async def listings(request: Request):
    listings = await run_in_threadpool(get_recent_listings, DB_NAME, 200)
    return templates.TemplateResponse(
        "listing_grid.html",
        {"request": request, "listings": listings},
    )


@app.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_detail(request: Request, listing_id: int):
    listing = await run_in_threadpool(get_listing_by_id, DB_NAME, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    images = await run_in_threadpool(get_listing_images, DB_NAME, listing_id)
    return templates.TemplateResponse(
        "listing_detail.html",
        {"request": request, "listing": listing, "images": images},
    )
