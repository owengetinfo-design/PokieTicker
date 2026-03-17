"""Migration script: Add market field to tickers table for multi-market support.

This script:
1. Adds the 'market' column to the tickers table (if not exists)
2. Populates market values based on symbol patterns:
   - .SH/.SZ suffix -> CN (A-shares)
   - .HK suffix -> HK (Hong Kong)
   - No suffix -> US (US stocks)
3. Updates existing records
"""

import sqlite3
from backend.config import settings


def migrate():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row

    print(f"Connected to database: {settings.database_path}")

    # Check if market column exists
    cursor = conn.execute("PRAGMA table_info(tickers)")
    columns = [row[1] for row in cursor.fetchall()]

    if "market" not in columns:
        print("Adding 'market' column to tickers table...")
        conn.execute("ALTER TABLE tickers ADD COLUMN market TEXT DEFAULT 'US'")
        print("  ✓ Column added")
    else:
        print("'market' column already exists")

    # Update market values based on symbol patterns
    print("\nUpdating market values...")

    # Get all tickers
    rows = conn.execute("SELECT symbol FROM tickers").fetchall()
    print(f"  Found {len(rows)} tickers to process")

    # Categorize by pattern
    cn_count = conn.execute(
        "UPDATE tickers SET market = 'CN' WHERE symbol LIKE '%.SH' OR symbol LIKE '%.SZ'"
    ).rowcount

    hk_count = conn.execute(
        "UPDATE tickers SET market = 'HK' WHERE symbol LIKE '%.HK'"
    ).rowcount

    us_count = conn.execute(
        "UPDATE tickers SET market = 'US' WHERE market IS NULL OR market = ''"
    ).rowcount

    conn.commit()

    print(f"  ✓ Updated {cn_count} A-share tickers (CN)")
    print(f"  ✓ Updated {hk_count} HK tickers (HK)")
    print(f"  ✓ Updated {us_count} US tickers (US)")

    # Show summary
    print("\nMarket distribution after migration:")
    summary = conn.execute(
        "SELECT market, COUNT(*) as count FROM tickers GROUP BY market ORDER BY count DESC"
    ).fetchall()
    for row in summary:
        print(f"  {row['market']}: {row['count']} tickers")

    conn.close()
    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
