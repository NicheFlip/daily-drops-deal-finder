"""Validate real Amazon API scan output rather than relying on a green workflow badge."""
import datetime
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parent
FEED=ROOT/'data'/'amazon-deals.json'
HEALTH=ROOT/'data'/'amazon-scan-health.json'

def validate():
    now=datetime.datetime.now(datetime.timezone.utc)
    issues=[]
    try:
        data=json.loads(FEED.read_text(encoding='utf-8'))
        updated=datetime.datetime.fromisoformat(data['updated'].replace('Z','+00:00'))
        if updated.tzinfo is None:
            issues.append('Timestamp missing timezone')
        else:
            age=(now-updated).total_seconds()/60
            if age>30 or age < -5:issues.append('Scan timestamp is not from this run')
        scanned=int(data.get('scannedProducts') or 0)
        requests=int(data.get('requestsCompleted') or 0)
        deals=data.get('deals',[])
        errors=data.get('errors') or []
        if scanned<=0:issues.append('No products returned by Amazon API')
        if requests<=0:issues.append('No successful Amazon API requests')
        if not isinstance(deals,list):issues.append('Deals payload is not a list')
        elif any(not isinstance(x,dict) or not x.get('asin') for x in deals):issues.append('Malformed product in deal feed')
        if errors:issues.append('Amazon API reported '+str(len(errors))+' errors')
    except (OSError,ValueError,TypeError,KeyError) as exc:
        data={}
        scanned=requests=0
        deals=[]
        issues.append('Unable to validate feed: '+type(exc).__name__)
    report={'checkedAt':now.isoformat(),'lastScanAt':data.get('updated'),
        'status':'healthy' if not issues else 'failed',
        'scannedProducts':scanned,'requestsCompleted':requests,
        'publishedDeals':len(deals) if isinstance(deals,list) else 0,
        'issues':issues}
    HEALTH.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return not issues

if __name__=='__main__':
    sys.exit(0 if validate() else 1)
