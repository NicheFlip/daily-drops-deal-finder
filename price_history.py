"""Compact, transparent history for qualifying Amazon API offers."""
import datetime,json,pathlib
ROOT=pathlib.Path(__file__).parent
PATH=ROOT/'data'/'amazon-price-history.json'
CHANGES=ROOT/'data'/'amazon-deal-changes.json'
def enrich(observed,stamp):
    now=datetime.datetime.fromisoformat(stamp)
    try: history=json.loads(PATH.read_text()).get('items',{})
    except (OSError,ValueError,AttributeError):history={}
    cutoff=now-datetime.timedelta(days=90)
    for asin in list(history):
        entry=history[asin]; points=[]
        for point in entry.get('points',[]):
            try:
                dt=datetime.datetime.fromisoformat(point[0].replace('Z','+00:00'))
                price=float(point[1])
                if dt>=cutoff and price>0:points.append([point[0],round(price,2)])
            except (ValueError,TypeError,IndexError):pass
        if points:entry['points']=points[-90:]
        else:del history[asin]
    changes=[]
    for asin,d in observed.items():
        entry=history.get(asin,{'points':[]})
        points=entry['points']
        prior=[p[1] for p in points]
        previous=prior[-1] if prior else None
        price=float(d['price'])
        drop=round(100*(previous-price)/previous,1) if previous and price<previous else 0
        low=bool(prior) and price<min(prior)
        if not points or points[-1][1]!=price or points[-1][0][:10]!=stamp[:10]:
            points.append([stamp,price])
        entry.update({'title':d['title'],'category':d['category'],'lastSeen':stamp,'points':points[-90:]})
        history[asin]=entry
        d.update({'observedLow90d':min(p[1] for p in entry['points']),
                  'observationCount':len(entry['points']),
                  'observedPriceDropPercent':drop,'newObservedLow':low,
                  'dealScore':min(90,min(25,max(0,d['discountPercent']-40))+min(35,round(drop*1.5))+20+(10 if len(prior)>=2 else 0))})
        if previous is not None and price<previous:
            changes.append({'asin':asin,'title':d['title'],'previousObservedPrice':previous,
                            'currentObservedPrice':price,'dropPercent':drop,'newObservedLow':low,
                            'checkedAt':stamp,'url':d['url']})
    history=dict(sorted(history.items(),key=lambda x:x[1].get('lastSeen',''),reverse=True)[:1200])
    PATH.write_text(json.dumps({'updated':stamp,'scope':'Observed qualifying API offers only, not market-wide history','items':history},separators=(',',':')))
    CHANGES.write_text(json.dumps({'updated':stamp,'changes':sorted(changes,key=lambda x:x['dropPercent'],reverse=True)[:100],
                                  'note':'API-observed drops only; verify checkout.'},indent=2))
    return len(changes)
