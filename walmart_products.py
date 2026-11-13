"""Import an authorized Walmart Creator/product feed. No scraping or invented prices.
Configure WALMART_PRODUCT_FEED_URL to an approved HTTPS JSON or CSV export.
"""
import csv,datetime,io,json,os,pathlib,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/'data'/'walmart-products.json'
HISTORY=ROOT/'data'/'walmart-price-history.json'
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def walmart_url(url):
    try:
        u=urllib.parse.urlparse(str(url))
        return u.scheme=='https' and u.hostname in ('www.walmart.com','walmart.com')
    except ValueError:return False
def normalize(row):
    if not isinstance(row,dict):return None
    get=lambda *keys:next((row[k] for k in keys if row.get(k) not in (None,'')),None)
    item=str(get('itemId','item_id','id','productId') or '').strip()
    title=str(get('title','name','productName') or '').strip()
    url=str(get('url','productUrl','product_url') or '').strip()
    try:price=round(float(str(get('price','currentPrice','salePrice') or '').replace('$','').replace(',','')),2)
    except ValueError:return None
    if not item or not title or price<=0 or not walmart_url(url):return None
    image=str(get('imageUrl','image','thumbnail') or '')
    if image:
        parsed=urllib.parse.urlparse(image)
        if parsed.scheme!='https' or not (parsed.hostname or '').endswith(('.walmartimages.com','.walmart.com')):
            image=''
    return {'itemId':item[:100],'title':title[:220],'price':price,'url':url,
      'category':str(get('category','department') or 'Other')[:70],
      'imageUrl':image,'checkedAt':NOW,'retailer':'Walmart'}
def run():
    endpoint=os.getenv('WALMART_PRODUCT_FEED_URL','').strip()
    if not endpoint:
        print('No authorized Walmart product feed configured; research catalog remains available.')
        return
    u=urllib.parse.urlparse(endpoint)
    if u.scheme!='https' or not u.hostname:raise ValueError('Feed URL must use HTTPS')
    request=urllib.request.Request(endpoint,headers={'User-Agent':'DailyDropsAuthorizedFeed/1.0','Accept':'application/json,text/csv'})
    with urllib.request.urlopen(request,timeout=35) as response:
        body=response.read(8_000_001)
    if len(body)>8_000_000:raise ValueError('Feed exceeds 8MB limit')
    content=body.decode('utf-8-sig')
    if content.lstrip().startswith(('{','[')):
        data=json.loads(content)
        raw=data if isinstance(data,list) else data.get('products',data.get('items',[]))
    else:raw=list(csv.DictReader(io.StringIO(content)))
    if not isinstance(raw,list):raise ValueError('Expected product array')
    products={p['itemId']:p for row in raw if (p:=normalize(row))}
    if not products:raise ValueError('No valid Walmart products returned; refusing to replace prior feed')
    previous={}
    if HISTORY.exists():
        try:previous=json.loads(HISTORY.read_text())
        except (ValueError,OSError):pass
    changed=0
    for item,p in products.items():
        old=previous.get(item,[])
        last=old[-1]['price'] if old else None
        if last!=p['price']:
            changed+=1
            old.append({'checkedAt':NOW,'price':p['price']})
        previous[item]=old[-60:]
        p['previousPrice']=last
        p['priceChanged']=last is not None and last!=p['price']
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'updated':NOW,'status':'connected','source':'Authorized product feed','count':len(products),'changed':changed,'products':list(products.values())},indent=2))
    HISTORY.write_text(json.dumps(previous,indent=2))
    print('Walmart authorized products:',len(products),'changed prices:',changed)
if __name__=='__main__':run()
