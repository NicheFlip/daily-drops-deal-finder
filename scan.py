"""Discover unverified deal leads from public RSS feeds. No retailer scraping."""
import json, pathlib, re, urllib.request, xml.etree.ElementTree as ET, datetime, html
from urllib.parse import urlparse
ROOT=pathlib.Path(__file__).parent
config=json.loads((ROOT/'feeds.json').read_text())
out=ROOT/'data'/'deals.json'
previous=json.loads(out.read_text()).get('deals',[]) if out.exists() else []
by_url={d['url']:d for d in previous if d.get('url')}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def text(el,name):
    v=el.find(name)
    return ''.join(v.itertext()).strip() if v is not None else ''
for feed in config['feeds']:
    url=feed['url']
    if urlparse(url).scheme!='https': continue
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'DailyDropsResearch/1.0 (public RSS feed reader)'})
        with urllib.request.urlopen(req,timeout=18) as response: data=response.read(2_000_000)
        root=ET.fromstring(data)
        items=root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        for item in items[:80]:
            title=html.unescape(re.sub('<[^>]*>','',text(item,'title') or text(item,'{http://www.w3.org/2005/Atom}title')))
            link=text(item,'link')
            if not link:
                a=item.find('{http://www.w3.org/2005/Atom}link')
                link=a.get('href','') if a is not None else ''
            if not title or not link.startswith('https://'): continue
            combined=(title+' '+text(item,'description')).lower()
            if not any(w in combined for w in ['amazon','walmart','clearance','coupon','price mistake','price error','glitch']): continue
            retailer='Amazon' if 'amazon' in combined else 'Walmart' if 'walmart' in combined else 'Other / verify'
            if retailer=='Other / verify' and not any(w in combined for w in ['clearance','coupon','glitch','price error']):continue
            prior=by_url.get(link,{})
            by_url[link]={**prior,'title':title[:200],'url':link,'source':feed['name'],'retailer':retailer,'firstSeen':prior.get('firstSeen',now),'lastSeen':now,'verified':False,'notes':'Deal lead only. Verify retailer price and coupon terms.'}
    except Exception as exc:
        print('Feed unavailable:',feed['name'],type(exc).__name__,str(exc)[:120])
result=sorted(by_url.values(),key=lambda d:d['lastSeen'],reverse=True)[:350]
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'updated':now,'deals':result},indent=2))
print('Saved',len(result),'unverified deal leads')
