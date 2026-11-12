"""Amazon Creators API research scanner. Never publishes secrets or unverifiable discounts."""
import os,json,urllib.request,urllib.error,datetime,pathlib,time,re
from urllib.parse import urlparse
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/'data'/'amazon-deals.json'
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
CATEGORIES=[('ToysAndGames','toys gifts'),('HomeAndKitchen','kitchen organizers'),('HomeAndKitchen','small kitchen appliances'),('Electronics','headphones'),('Beauty','skin care'),('Fashion','women clothing'),('ToysAndGames','building sets')]
def request(url,payload,headers=None):
    req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json',**(headers or {})},method='POST')
    with urllib.request.urlopen(req,timeout=30) as resp:return json.load(resp)
def money(obj):
    if not isinstance(obj,dict):return None
    v=obj.get('amount') or obj.get('value')
    try:return round(float(v),2) if v is not None else None
    except (ValueError,TypeError):return None
def scan():
    cid=os.environ['AMAZON_CREATORS_CREDENTIAL_ID'];secret=os.environ['AMAZON_CREATORS_SECRET'];tag=os.environ['AMAZON_PARTNER_TAG']
    token=request('https://api.amazon.com/auth/o2/token',{'grant_type':'client_credentials','client_id':cid,'client_secret':secret,'scope':'creatorsapi::default'})['access_token']
    prior={}
    if OUT.exists():
        try:prior={x['asin']:x for x in json.loads(OUT.read_text()).get('deals',[])}
        except (ValueError,KeyError):pass
    deals=[]; errors=[];count=0
    for index,(category,keywords) in enumerate(CATEGORIES):
        if index:time.sleep(1.5)
        payload={'partnerTag':tag,'marketplace':'www.amazon.com','keywords':keywords,'searchIndex':category,'itemCount':10,'resources':['itemInfo.title','offersV2.listings.price']}
        try:
            data=request('https://creatorsapi.amazon/catalog/v1/searchItems',payload,{'Authorization':'Bearer '+token,'x-marketplace':'www.amazon.com'})
            items=data.get('searchResult',{}).get('items',[])
            count+=len(items)
            for item in items:
                asin=item.get('asin','')
                if not re.fullmatch(r'[A-Z0-9]{10}',asin):continue
                title=item.get('itemInfo',{}).get('title',{}).get('displayValue','')
                listings=item.get('offersV2',{}).get('listings',[])
                if not isinstance(listings,list):listings=[]
                price=None;reference=None
                for listing in listings:
                    p=listing.get('price',{})
                    price=money(p.get('money',p)) if isinstance(p,dict) else None
                    if price is not None:
                        for field in ('savingBasis','savingBasisPrice','listPrice'):
                            obj=listing.get(field,{})
                            reference=money(obj.get('money',obj)) if isinstance(obj,dict) else None
                            if reference:break
                        break
                if not title or price is None or price<=0:continue
                discount=round((reference-price)/reference*100) if reference and reference>price else None
                if discount is None or discount<40:continue
                old=prior.get(asin,{})
                deals.append({'asin':asin,'title':title[:180],'retailer':'Amazon','url':'https://www.amazon.com/dp/'+asin,'price':price,'referencePrice':reference,'discountPercent':discount,'category':category,'firstSeen':old.get('firstSeen',NOW),'checkedAt':NOW,'priceSource':'Amazon Creators API offer listing','referenceCaveat':'API savings basis or list price; not independently verified as historical selling price','couponVerified':False,'possibleGlitch':False})
        except urllib.error.HTTPError as e:errors.append(category+': HTTP '+str(e.code))
        except Exception as e:errors.append(category+': '+type(e).__name__)
    deals=sorted({d['asin']:d for d in deals}.values(),key=lambda d:d['discountPercent'],reverse=True)[:80]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'updated':NOW,'status':'partial' if errors else 'ok','scannedProducts':count,'errors':errors,'deals':deals},indent=2))
    print('Scanned',count,'products;',len(deals),'discount leads;',len(errors),'category errors')
if __name__=='__main__':
    try:scan()
    except Exception as e:
        print('Amazon scan failed:',type(e).__name__)
        raise SystemExit(1)
