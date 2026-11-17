"""Compact, Git-persisted JSON price history.

Each product keeps one point per price change (sorted, no repeated identical
consecutive points) plus lastChecked/checks for repeat sightings at the same price.
"""
import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
PATH = ROOT / 'data' / 'amazon-price-history.json'
CHANGES = ROOT / 'data' / 'amazon-deal-changes.json'
MAX_ITEMS = 5000   # was 1200: too small, products were evicted and came back as "first seen"
MAX_POINTS = 90    # price-change points per product (not per scan)


def compact_points(raw, horizon=None):
    """Sorted, de-duplicated price timeline: one point per price change.

    Returns (points, last_checked, checks). Consecutive points at the same price are
    collapsed into the first one (when that price was first seen); the latest
    timestamp is kept as last_checked so no real observation is lost.
    """
    clean = []
    for point in raw or []:
        try:
            checked = datetime.datetime.fromisoformat(str(point[0]).replace('Z', '+00:00'))
            cents = round(float(point[1]) * 100)
        except (TypeError, ValueError, IndexError, AttributeError):
            continue
        if cents <= 0 or (horizon is not None and checked < horizon):
            continue
        clean.append((checked.isoformat(), cents))
    clean.sort()
    points = []
    for ts, cents in clean:
        if points and points[-1][0] == ts:
            points[-1] = (ts, cents)          # same timestamp twice: keep one
        elif not points or points[-1][1] != cents:
            points.append((ts, cents))
    return points, (clean[-1][0] if clean else None), len(clean)


def summarize(points, price_cents=None):
    """High/low/previous-different price from a compacted timeline (cents)."""
    prices = [c for _, c in points]
    if price_cents is not None:
        prices = prices + [price_cents]
    previous = None
    if points:
        current = price_cents if price_cents is not None else points[-1][1]
        for ts, cents in reversed(points):
            if cents != current:
                previous = (ts, cents)
                break
    return {'low': min(prices) if prices else None, 'high': max(prices) if prices else None,
            'previous': previous, 'firstSeen': points[0][0] if points else None}


def enrich(observed, stamp, baseline=None):
    now = datetime.datetime.fromisoformat(stamp)
    horizon = now - datetime.timedelta(days=90)
    try:
        history = json.loads(PATH.read_text()).get('items', {})
        if not isinstance(history, dict):
            history = {}
    except (OSError, ValueError, AttributeError):
        history = {}

    timelines = {}
    for asin, entry in history.items():
        if not isinstance(asin, str) or not isinstance(entry, dict):
            continue
        points, last_raw, raw_count = compact_points(entry.get('points', []), horizon)
        if not points:
            continue
        timelines[asin] = {
            'title': str(entry.get('title', ''))[:100], 'category': str(entry.get('category', ''))[:60],
            'lastSeen': str(entry.get('lastSeen') or last_raw or stamp),
            'lastChecked': max(filter(None, [entry.get('lastChecked'), last_raw])),
            'checks': max(int(entry.get('checks') or 0), raw_count),
            'points': points[-MAX_POINTS:]}

    changes = []
    # Every valid product seen this scan extends its timeline; only qualifying
    # deals receive scoring and enter the public change feed.
    tracked = dict(baseline or {})
    tracked.update(observed)
    for asin, deal in tracked.items():
        try:
            price_cents = round(float(deal['price']) * 100)
        except (KeyError, TypeError, ValueError):
            continue
        if price_cents <= 0:
            continue
        line = timelines.get(asin)
        prior = list(line['points']) if line else []
        previous = prior[-1][1] if prior else None          # last recorded price
        drop = round(100 * (previous - price_cents) / previous, 1) if previous and price_cents < previous else 0
        new_low = bool(prior) and price_cents < min(c for _, c in prior)
        if line is None:
            line = timelines[asin] = {'points': [], 'checks': 0, 'lastChecked': None}
        if not prior or prior[-1][1] != price_cents:
            line['points'] = (prior + [(stamp, price_cents)])[-MAX_POINTS:]
        if line.get('lastChecked') != stamp:
            line['checks'] = int(line.get('checks') or 0) + 1
        line.update({'title': str(deal.get('title', ''))[:100], 'category': str(deal.get('category', ''))[:60],
                     'lastSeen': stamp, 'lastChecked': stamp})
        if asin not in observed:
            continue
        info = summarize(prior, price_cents)
        confidence = ('observed_reduction' if previous is not None and price_cents < previous else
                      'repeat_observation' if prior else 'first_observation')
        deal.update({
            'priceEvidence': confidence,
            'priorObservedPrice': round(previous / 100, 2) if previous is not None else None,
            'previousDifferentPrice': round(info['previous'][1] / 100, 2) if info['previous'] else None,
            'previousDifferentPriceAt': info['previous'][0] if info['previous'] else None,
            'observedLow90d': round(info['low'] / 100, 2),
            'observedHigh90d': round(info['high'] / 100, 2),
            'firstSeenAt': info['firstSeen'] or stamp,
            'observationCount': line['checks'],
            'priceChangeCount': len(line['points']),
            'observedPriceDropPercent': drop,
            'newObservedLow': new_low,
            'dealScore': min(90, min(20, max(0, deal['discountPercent'] - 40)) +
                             min(40, round(drop * 1.5)) +
                             (20 if previous is not None and price_cents < previous else 0) +
                             (10 if len(prior) >= 2 else 0))
        })
        if previous is not None and price_cents < previous:
            changes.append({
                'asin': asin, 'title': deal['title'],
                'previousObservedPrice': round(previous / 100, 2),
                'currentObservedPrice': round(price_cents / 100, 2),
                'dropPercent': drop, 'newObservedLow': new_low,
                'checkedAt': stamp, 'url': deal['url'],
                **{k: deal[k] for k in ('seller', 'soldByAmazon', 'isPrime', 'freeShipping', 'shippingStatus') if k in deal}
            })

    # Bound storage growth (most recently seen first), then export JSON as the durable checkpoint.
    keep = sorted(timelines.items(), key=lambda kv: kv[1].get('lastSeen') or '', reverse=True)[:MAX_ITEMS]
    exported = {}
    for asin, line in keep:
        if not line.get('points'):
            continue
        exported[asin] = {'title': line.get('title', ''), 'category': line.get('category', ''),
                          'lastSeen': line.get('lastSeen'), 'lastChecked': line.get('lastChecked'),
                          'checks': line.get('checks', len(line['points'])),
                          'points': [[ts, round(c / 100, 2)] for ts, c in line['points']]}

    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps({
        'updated': stamp,
        'scope': 'API-observed qualifying deals plus sampled everyday essentials; not market-wide price history',
        'storage': 'JSON checkpoint; one point per price change, lastChecked/checks record repeat sightings',
        'items': exported
    }, separators=(',', ':')))
    CHANGES.write_text(json.dumps({
        'updated': stamp,
        'changes': sorted(changes, key=lambda x: x['dropPercent'], reverse=True)[:100],
        'note': 'API-observed price drops only; checkout not verified.'
    }, indent=2))
    return len(changes)
