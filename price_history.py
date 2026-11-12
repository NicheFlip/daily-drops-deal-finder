"""Free SQLite processing with compact, Git-persisted JSON price observations.

SQLite is in-memory during a scheduled scan. The JSON history is the durable
checkpoint; no database server or committed binary database is required.
"""
import datetime
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).parent
PATH = ROOT / 'data' / 'amazon-price-history.json'
CHANGES = ROOT / 'data' / 'amazon-deal-changes.json'
MAX_ITEMS = 1200
MAX_POINTS = 90


def enrich(observed, stamp, baseline=None):
    now = datetime.datetime.fromisoformat(stamp)
    cutoff = (now - datetime.timedelta(days=90)).isoformat()
    try:
        history = json.loads(PATH.read_text()).get('items', {})
        if not isinstance(history, dict):
            history = {}
    except (OSError, ValueError, AttributeError):
        history = {}

    with sqlite3.connect(':memory:') as db:
        db.executescript("""
            CREATE TABLE products (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE observations (
                asin TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents > 0),
                PRIMARY KEY(asin, checked_at)
            );
            CREATE INDEX observation_lookup ON observations(asin, checked_at);
        """)
        # Import previously collected observations; malformed legacy entries
        # are skipped rather than causing an entire hourly scan to fail.
        for asin, entry in history.items():
            if not isinstance(asin, str) or not isinstance(entry, dict):
                continue
            points = []
            for point in entry.get('points', []):
                try:
                    checked = datetime.datetime.fromisoformat(point[0].replace('Z', '+00:00'))
                    cents = round(float(point[1]) * 100)
                    if checked >= now - datetime.timedelta(days=90) and cents > 0:
                        points.append((asin, checked.isoformat(), cents))
                except (TypeError, ValueError, IndexError, AttributeError):
                    continue
            if not points:
                continue
            db.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?)',
                       (asin, str(entry.get('title', ''))[:180],
                        str(entry.get('category', ''))[:60], str(entry.get('lastSeen', stamp))))
            db.executemany('INSERT OR REPLACE INTO observations VALUES (?,?,?)', points[-MAX_POINTS:])

        changes = []
        # All valid essentials establish price baselines; only qualifying deals
        # receive scoring and enter the public change feed.
        tracked = dict(baseline or {})
        tracked.update(observed)
        for asin, deal in tracked.items():
            price_cents = round(float(deal['price']) * 100)
            if price_cents <= 0:
                continue
            old = db.execute(
                'SELECT price_cents FROM observations WHERE asin=? ORDER BY checked_at',
                (asin,)).fetchall()
            prior = [row[0] for row in old]
            previous = prior[-1] if prior else None
            drop = round(100 * (previous - price_cents) / previous, 1) if previous and price_cents < previous else 0
            new_low = bool(prior) and price_cents < min(prior)
            last = db.execute('SELECT checked_at, price_cents FROM observations WHERE asin=? ORDER BY checked_at DESC LIMIT 1', (asin,)).fetchone()
            if last is None or last[1] != price_cents or last[0][:10] != stamp[:10]:
                db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?)', (asin, stamp, price_cents))
            db.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?)',
                       (asin, deal['title'][:180], deal['category'][:60], stamp))
            summary = db.execute('SELECT MIN(price_cents), COUNT(*) FROM observations WHERE asin=?', (asin,)).fetchone()
            if asin not in observed:
                continue
            deal.update({
                'observedLow90d': round(summary[0] / 100, 2),
                'observationCount': summary[1],
                'observedPriceDropPercent': drop,
                'newObservedLow': new_low,
                'dealScore': min(90, min(25, max(0, deal['discountPercent'] - 40)) +
                                 min(35, round(drop * 1.5)) + 20 +
                                 (10 if len(prior) >= 2 else 0))
            })
            if previous is not None and price_cents < previous:
                changes.append({
                    'asin': asin, 'title': deal['title'],
                    'previousObservedPrice': round(previous / 100, 2),
                    'currentObservedPrice': round(price_cents / 100, 2),
                    'dropPercent': drop, 'newObservedLow': new_low,
                    'checkedAt': stamp, 'url': deal['url']
                })

        # Bound storage growth, then export JSON as the durable checkpoint.
        rows = db.execute('SELECT asin,title,category,last_seen FROM products ORDER BY last_seen DESC LIMIT ?', (MAX_ITEMS,)).fetchall()
        exported = {}
        for asin, title, category, last_seen in rows:
            points = db.execute(
                'SELECT checked_at,price_cents FROM observations WHERE asin=? ORDER BY checked_at DESC LIMIT ?',
                (asin, MAX_POINTS)).fetchall()
            if points:
                exported[asin] = {
                    'title': title, 'category': category, 'lastSeen': last_seen,
                    'points': [[ts, round(cents / 100, 2)] for ts, cents in reversed(points)]
                }

    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps({
        'updated': stamp,
        'scope': 'API-observed qualifying deals plus sampled everyday essentials; not market-wide price history',
        'storage': 'SQLite processed, JSON checkpoint',
        'items': exported
    }, separators=(',', ':')))
    CHANGES.write_text(json.dumps({
        'updated': stamp,
        'changes': sorted(changes, key=lambda x: x['dropPercent'], reverse=True)[:100],
        'note': 'API-observed price drops only; checkout not verified.'
    }, indent=2))
    return len(changes)
