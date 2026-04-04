"""Database schema and helpers for the Anima Trustpilot Sentiment Monitor."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reviews.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            rating INTEGER NOT NULL,
            title TEXT,
            text TEXT,
            date_published TEXT NOT NULL,
            consumer_name TEXT,
            consumer_country TEXT,
            has_reply INTEGER DEFAULT 0,
            reply_text TEXT,
            reply_date TEXT,
            review_url TEXT,
            scraped_at TEXT NOT NULL,
            -- LLM categorisation fields (for 1-2 star reviews)
            category TEXT,
            software_complaint INTEGER,
            category_confidence REAL,
            categorised_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_company ON reviews(company);
        CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);
        CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(date_published);
        CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews(category);

        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            reviews_found INTEGER,
            new_reviews INTEGER,
            rating REAL,
            total_reviews INTEGER,
            one_star INTEGER,
            two_star INTEGER,
            three_star INTEGER,
            four_star INTEGER,
            five_star INTEGER
        );
    """)
    conn.commit()
    conn.close()


def upsert_review(conn, review_dict):
    conn.execute("""
        INSERT INTO reviews (id, company, rating, title, text, date_published,
            consumer_name, consumer_country, has_reply, reply_text, reply_date,
            review_url, scraped_at)
        VALUES (:id, :company, :rating, :title, :text, :date_published,
            :consumer_name, :consumer_country, :has_reply, :reply_text, :reply_date,
            :review_url, :scraped_at)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            text=excluded.text,
            has_reply=excluded.has_reply,
            reply_text=excluded.reply_text,
            reply_date=excluded.reply_date,
            scraped_at=excluded.scraped_at
    """, review_dict)


def log_scrape(conn, company, scraped_at, reviews_found, new_reviews, stats):
    conn.execute("""
        INSERT INTO scrape_log (company, scraped_at, reviews_found, new_reviews,
            rating, total_reviews, one_star, two_star, three_star, four_star, five_star)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (company, scraped_at, reviews_found, new_reviews,
          stats.get('rating'), stats.get('total'), stats.get('one'),
          stats.get('two'), stats.get('three'), stats.get('four'), stats.get('five')))


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
