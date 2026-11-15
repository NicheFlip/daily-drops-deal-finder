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
# Discover explicitly advertised public RSS/Atom feeds on partner deal pages.
# Do not crawl product pages or bypass access restrictions.
from html.parser import HTMLParser
from urllib.parse import urljoin
class FeedLinks(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag!='link':return
        a=dict(attrs)
        if 'alternate' in a.get('rel','').lower() and any(t in a.get('type','').lower() for t in ('rss+xml','atom+xml')):
            if a.get('href'):self.links.append(a['href'])
def discover_public_feeds():
    found=[]
    for site in config.get('sites',[]):
        try:
            url=site['url']
            if urlparse(url).scheme!='https':continue
            req=urllib.request.Request(url,headers={'User-Agent':'DailyDropsResearch/1.0 (public RSS discovery)'})
            with urllib.request.urlopen(req,timeout=10) as response:
                final=response.geturl()
                if urlparse(final).hostname!=urlparse(url).hostname:continue
                page=response.read(350_000).decode('utf-8','replace')
            parser=FeedLinks();parser.feed(page)
            for href in parser.links[:3]:
                feed_url=urljoin(final,href)
                if urlparse(feed_url).scheme=='https' and urlparse(feed_url).hostname==urlparse(url).hostname:
                    found.append({'name':site['name'],'url':feed_url})
            if not parser.links:print('No public RSS advertised:',site['name'])
        except Exception as exc:print('Site feed discovery unavailable:',site['name'],type(exc).__name__)
    return found
site_names={site['name'] for site in config.get('sites',[])}
for feed in config['feeds']+discover_public_feeds():
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
            if any(w in combined for w in ['firearm','ammunition','gun safe','vape','nicotine','liquor','whiskey','casino','sportsbook','lottery','pepper spray','switchblade']):continue
            if feed['name'] not in site_names and not any(w in combined for w in ['amazon','walmart','clearance','coupon','price mistake','price error','glitch']): continue
            retailer='Amazon' if 'amazon' in combined else 'Walmart' if 'walmart' in combined else 'Other / verify'
            if retailer=='Other / verify' and feed['name'] not in site_names and not any(w in combined for w in ['clearance','coupon','glitch','price error']):continue
            prior=by_url.get(link,{})
            image=''
            for el in item.iter():
                tag=el.tag.split('}')[-1].lower()
                if tag in ('thumbnail','content','enclosure'):
                    candidate=el.attrib.get('url','')
                    media_type=el.attrib.get('type','')
                    if candidate.startswith('https://') and (media_type.startswith('image/') or candidate.lower().split('?')[0].endswith(('.jpg','.jpeg','.png','.webp'))):
                        image=candidate;break
            if not image:
                class DescriptionImage(HTMLParser):
                    def __init__(self):super().__init__();self.src=''
                    def handle_starttag(self,tag,attrs):
                        if tag=='img' and not self.src:
                            a=dict(attrs);self.src=a.get('src','') or a.get('data-src','')
                desc=' '.join(''.join(el.itertext()) for el in item.iter() if el.tag.split('}')[-1].lower() in ('description','encoded','summary','content'))
                if desc:
                    parser=DescriptionImage();parser.feed(desc[:100000])
                    if parser.src.startswith('https://'):image=parser.src
            by_url[link]={**prior,'title':title[:200],'url':link,'source':feed['name'],'retailer':retailer,'firstSeen':prior.get('firstSeen',now),'lastSeen':now,'imageUrl':image or prior.get('imageUrl',''),'verified':False,'notes':'Deal lead only. Verify retailer price and coupon terms.'}
    except Exception as exc:
        print('Feed unavailable:',feed['name'],type(exc).__name__,str(exc)[:120])
result=sorted(by_url.values(),key=lambda d:d['lastSeen'],reverse=True)[:350]
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'updated':now,'deals':result},indent=2))
print('Saved',len(result),'unverified deal leads')
