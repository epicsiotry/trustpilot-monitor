"""Trustpilot scraper for Anima, eConsult, and PATCHS.

Trustpilot limits unfiltered pagination to ~10 pages. To get all reviews,
we scrape each star rating separately (e.g. ?stars=1&page=1), which gives
access to the full set.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime, timezone
from database import get_connection, init_db, upsert_review, log_scrape

COMPANIES = {
    "anima": "patients.animahealth.com",
    "econsult": "econsult.net",
    "patchs": "www.patchs.ai",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def fetch_page(domain, page=1, stars=None, retries=3):
    """Fetch a single page of reviews from Trustpilot."""
    url = f"https://uk.trustpilot.com/review/{domain}?page={page}"
    if stars is not None:
        url += f"&stars={stars}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {resp.status_code} on page {page}, attempt {attempt+1}")
                time.sleep(5)
        except requests.RequestException as e:
            print(f"  Request error on page {page}: {e}")
            time.sleep(5)
    return None


def parse_page(html, company_key):
    """Extract reviews and metadata from a Trustpilot page."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return [], {}, 0

    data = json.loads(script.string)
    props = data["props"]["pageProps"]

    # Extract rating statistics
    filters = props.get("filters", {})
    ratings_data = filters.get("reviewStatistics", {}).get("ratings", {})
    pagination = filters.get("pagination", {})
    business = props.get("businessUnit", {})

    stats = {
        "rating": business.get("trustScore"),
        "total": ratings_data.get("total", 0),
        "one": ratings_data.get("one", 0),
        "two": ratings_data.get("two", 0),
        "three": ratings_data.get("three", 0),
        "four": ratings_data.get("four", 0),
        "five": ratings_data.get("five", 0),
    }
    total_pages = pagination.get("totalPages", 1)

    # Extract reviews
    now = datetime.now(timezone.utc).isoformat()
    reviews = []
    for r in props.get("reviews", []):
        reply = r.get("reply")
        consumer = r.get("consumer", {})
        location = r.get("location") or {}

        review = {
            "id": r["id"],
            "company": company_key,
            "rating": r["rating"],
            "title": r.get("title", ""),
            "text": r.get("text", ""),
            "date_published": r.get("dates", {}).get("publishedDate", ""),
            "consumer_name": consumer.get("displayName", ""),
            "consumer_country": location.get("countryCode", ""),
            "has_reply": 1 if reply else 0,
            "reply_text": reply.get("message", "") if reply else "",
            "reply_date": reply.get("publishedDate", "") if reply else "",
            "review_url": f"https://uk.trustpilot.com/reviews/{r['id']}",
            "scraped_at": now,
        }
        reviews.append(review)

    return reviews, stats, total_pages


def scrape_company(company_key, domain, full=False):
    """Scrape all reviews for a company by iterating each star rating."""
    print(f"\nScraping {company_key} ({domain})...")

    conn = get_connection()

    existing = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE company = ?", (company_key,)
    ).fetchone()[0]
    print(f"  Existing reviews in DB: {existing}")

    # First, get overall stats from the unfiltered page
    html = fetch_page(domain, page=1)
    if not html:
        print(f"  Failed to fetch first page for {company_key}")
        conn.close()
        return

    _, stats, _ = parse_page(html, company_key)
    total_reviews_on_tp = stats.get("total", 0)
    print(f"  Trustpilot shows {total_reviews_on_tp} total reviews")
    print(f"  Rating: {stats.get('rating')}/5")
    print(f"  Stars: 5={stats.get('five')} 4={stats.get('four')} 3={stats.get('three')} 2={stats.get('two')} 1={stats.get('one')}")

    # Scrape each star rating separately to bypass pagination limits
    total_new = 0
    total_scraped = 0

    for star in [1, 2, 3, 4, 5]:
        time.sleep(random.uniform(1.5, 3.0))

        # Get first page for this star rating to find total pages
        html = fetch_page(domain, page=1, stars=star)
        if not html:
            print(f"  Failed to fetch {star}-star reviews")
            continue

        reviews, _, total_pages = parse_page(html, company_key)
        star_count = stats.get({1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}[star], 0)
        print(f"  {star}-star: {star_count} reviews, {total_pages} pages")

        if not full and existing > 0:
            pages_to_scrape = min(3, total_pages)
        else:
            pages_to_scrape = total_pages

        # Save first page
        new_on_star = 0
        for r in reviews:
            if not conn.execute("SELECT 1 FROM reviews WHERE id = ?", (r["id"],)).fetchone():
                new_on_star += 1
            upsert_review(conn, r)
        conn.commit()
        total_scraped += len(reviews)

        # Remaining pages
        for page in range(2, pages_to_scrape + 1):
            time.sleep(random.uniform(1.5, 3.0))
            html = fetch_page(domain, page=page, stars=star)
            if not html:
                break
            reviews, _, _ = parse_page(html, company_key)
            if not reviews:
                break
            for r in reviews:
                if not conn.execute("SELECT 1 FROM reviews WHERE id = ?", (r["id"],)).fetchone():
                    new_on_star += 1
                upsert_review(conn, r)
            conn.commit()
            total_scraped += len(reviews)

        total_new += new_on_star
        if new_on_star > 0:
            print(f"    {new_on_star} new reviews added")

    # Log the scrape
    now = datetime.now(timezone.utc).isoformat()
    log_scrape(conn, company_key, now, total_scraped, total_new, stats)
    conn.commit()

    final_count = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE company = ?", (company_key,)
    ).fetchone()[0]
    print(f"  Done! {total_new} new reviews. Total in DB: {final_count}")

    conn.close()


def scrape_all(full=False):
    """Scrape all companies."""
    init_db()
    for key, domain in COMPANIES.items():
        scrape_company(key, domain, full=full)
        time.sleep(random.uniform(3, 6))
    print("\nAll scraping complete!")


if __name__ == "__main__":
    import sys
    full_mode = "--full" in sys.argv
    if full_mode:
        print("Running FULL scrape (all pages for all companies)...")
    else:
        print("Running incremental scrape (new reviews only)...")
        print("Use --full for a complete scrape of all pages")
    scrape_all(full=full_mode)
