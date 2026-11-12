"""Deduplicated, research-only candidate queue for API-observed Amazon offers."""
import datetime
import json
import pathlib

ROOT=pathlib.Path(__file__).parent
STATE=ROOT/'data'/'amazon-candidate-state.json'
QUEUE=ROOT/'data'/'amazon-candidates.json'
RETENTION_DAYS=45

def build_queue(observed, stamp):
    now=datetime.datetime.fromisoformat(stamp)
    try:
        previous=json.loads(STATE.read_text()).get('items',{})
        if not isinstance(previous,dict):previous={}
    except (OSError,ValueError,AttributeError):
        previous={}
    cutoff=now-datetime.timedelta(days=RETENTION_DAYS)
    retained={}
    for asin,entry in previous.items():
        try:
            if datetime.datetime.fromisoformat(entry['lastSeen'])>=cutoff:
                retained[asin]=entry
        except (KeyError,ValueError,TypeError):pass
    candidates=[]
    for asin,deal in observed.items():
        price=round(float(deal['price']),2)
        earlier=retained.get(asin)
        old_price=earlier.get('lastPrice') if earlier else None
        if earlier is None:
            reason='First observation'
        elif old_price is not None and price<round(float(old_price),2):
            reason='Observed price drop'
        else:
            reason=None
        # Only newly discovered or actually reduced-price products enter
        # this run's queue; no re-alert for an unchanged price.
        if reason:
            candidates.append({
                'asin':asin,'title':deal['title'],'category':deal['category'],
                'url':deal['url'],'price':price,
                'referencePrice':deal['referencePrice'],
                'discountPercent':deal['discountPercent'],
                'dealScore':deal.get('dealScore',0),
                'reason':reason,
                'previousObservedPrice':old_price,
                'newObservedLow':bool(deal.get('newObservedLow')),
                'checkedAt':deal['checkedAt'],
                'verification':'Amazon API snapshot; checkout and coupon stacking not verified'
            })
        retained[asin]={'lastPrice':price,'lastSeen':stamp}
    retained=dict(sorted(retained.items(),key=lambda pair:pair[1]['lastSeen'],reverse=True)[:3000])
    candidates.sort(key=lambda d:(d['reason']=='Observed price drop',d['dealScore'],d['discountPercent']),reverse=True)
    STATE.write_text(json.dumps({'updated':stamp,'items':retained},separators=(',',':')))
    QUEUE.write_text(json.dumps({'updated':stamp,'candidates':candidates[:100],
        'count':len(candidates),
        'note':'Research queue only; not verified at checkout. Unchanged offers suppressed.'},indent=2))
    return len(candidates)
