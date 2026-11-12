"""Daily Drops Amazon research scanner: rotating searches, accurate offer parsing, and safe output.
Official Creators API only. No scraping. API offer snapshots expire after 1 hour.
"""
import datetime,json,os,pathlib,re,time,urllib.error,urllib.request
from collections import defaultdict
from price_history import enrich
from candidate_queue import build_queue
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/'data'/'amazon-deals.json'
STATE=ROOT/'data'/'amazon-scan-state.json'
NOW=datetime.datetime.now(datetime.timezone.utc)
STAMP=NOW.isoformat()
# Broad, deliberately safe categories. Keyword rotation widens coverage across runs.
QUERIES=[
('ToysAndGames','building blocks'),('ToysAndGames','board games'),('ToysAndGames','dolls'),('ToysAndGames','preschool toys'),('ToysAndGames','puzzles'),('ToysAndGames','remote control cars'),
('HomeAndKitchen','kitchen organizers'),('HomeAndKitchen','small kitchen appliances'),('HomeAndKitchen','cookware'),('HomeAndKitchen','bedding'),('HomeAndKitchen','storage baskets'),('HomeAndKitchen','coffee makers'),('HomeAndKitchen','vacuum cleaners'),
('Electronics','wireless headphones'),('Electronics','computer accessories'),('Electronics','smart home'),('Electronics','chargers'),('Electronics','tablets'),
('Beauty','skin care'),('Beauty','hair care'),('Beauty','makeup organizers'),('Beauty','beauty tools'),
('Fashion','women clothing'),('Fashion','handbags'),('Fashion','sneakers'),('Fashion','winter coats'),
('OfficeProducts','school supplies'),('PetSupplies','dog beds'),('HomeAndKitchen','outdoor decor'),('Baby','baby blankets'),
('ToysAndGames','holiday gifts'),('HomeAndKitchen','home decor'),('Electronics','portable speakers')
]
# Household search priorities reflect practical repeat purchases, not verified sales rank.
ESSENTIAL_QUERIES=[("All","laundry detergent"),("All","paper towels"),("All","toilet paper"),("All","dish soap"),("All","trash bags"),("All","coffee pods"),("All","ground coffee"),("All","diapers"),("All","baby wipes"),("All","dishwasher pods"),("All","cleaning wipes"),("All","hand soap"),("All","toothpaste"),("All","shampoo"),("All","pet food"),("All","food storage bags"),("All","batteries AA"),("All","dryer sheets"),("All","facial tissues"),("All","body wash"),("All","breakfast cereal"),("All","snack variety pack"),("All","water filters"),("All","laundry scent boosters")]
BLACK_FRIDAY_QUERIES=[('All','early black friday deals'),('HomeAndKitchen','black friday kitchen deals'),('Electronics','black friday headphones'),('ToysAndGames','black friday toys'),('HomeAndKitchen','black friday vacuum'),('All','black friday household essentials'),('All','black friday coffee makers'),('All','black friday gifts')]
# API returns at most 10 items per request; distribute calls instead of bursts.
PER_RUN=24
MAX_DAILY_CALLS=1200  # conservative cap, well below initial 8640 TPD
RESOURCES=['itemInfo.title','offersV2.listings.price','offersV2.listings.availability','offersV2.listings.condition']
def api(url,payload,headers=None):
    req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json',**(headers or {})},method='POST')
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def amount(v):
    if not isinstance(v,dict):return None
    if 'money' in v:return amount(v['money'])
    x=v.get('amount')
    try:return round(float(x),2) if x is not None else None
    except (TypeError,ValueError):return None
def parse(item,category,keyword,minimum_discount=40):
    asin=item.get('asin','')
    if not re.fullmatch('[A-Z0-9]{10}',asin):return None
    title=item.get('itemInfo',{}).get('title',{}).get('displayValue','')
    if not title:return None
    for offer in item.get('offersV2',{}).get('listings',[]) or []:
        if offer.get('condition',{}).get('value','New') not in ('New',None):continue
        if offer.get('availability',{}).get('type') in ('OUT_OF_STOCK','UNAVAILABLE'):continue
        price_data=offer.get('price') or {}
        price=amount(price_data)
        basis=price_data.get('savingBasis',{}) if isinstance(price_data,dict) else {}
        reference=amount(basis)
        savings=price_data.get('savings',{}) if isinstance(price_data,dict) else {}
        if not price or price<=0:continue
        percent=round(100*(reference-price)/reference) if reference and reference>price else 0
        if percent<minimum_discount:continue
        # Prefer the API-provided percent when present and consistent.
        declared=savings.get('percentage') if isinstance(savings,dict) else None
        if isinstance(declared,(int,float)) and abs(declared-percent)>2:continue
        return {'asin':asin,'title':title[:180],'retailer':'Amazon',
          'url':'https://www.amazon.com/dp/'+asin,'price':price,
          'referencePrice':reference,'referenceType':basis.get('savingBasisTypeLabel') or basis.get('savingBasisType') or 'API savings basis',
          'discountPercent':percent,'category':category,'keyword':keyword,
          'checkedAt':STAMP,'couponVerified':False,'possibleGlitch':False,
          'verification':'Amazon API offer snapshot; checkout price, coupons and historical pricing not independently verified'}
    return None
def scan():
    cid=os.environ['AMAZON_CREATORS_CREDENTIAL_ID'];secret=os.environ['AMAZON_CREATORS_SECRET'];tag=os.environ['AMAZON_PARTNER_TAG']
    token=api('https://api.amazon.com/auth/o2/token',{'grant_type':'client_credentials','client_id':cid,'client_secret':secret,'scope':'creatorsapi::default'})['access_token']
    state={}
    if STATE.exists():
        try:state=json.loads(STATE.read_text())
        except ValueError:pass
    day=NOW.strftime('%Y-%m-%d')
    calls=state.get('callsToday',0) if state.get('day')==day else 0
    offset=int(state.get('nextOffset',0))%len(QUERIES)
    essential_offset=int(state.get('essentialOffset',0))%len(ESSENTIAL_QUERIES)
    seasonal_offset=int(state.get('seasonalOffset',0))%len(BLACK_FRIDAY_QUERIES)
    budget=max(0,min(PER_RUN,MAX_DAILY_CALLS-calls))
    previous={}
    if OUT.exists():
        try:previous={d['asin']:d for d in json.loads(OUT.read_text()).get('deals',[]) if d.get('asin')}
        except (ValueError,KeyError):pass
    # Drop old prices rather than show them as current.
    fresh={}
    for asin,d in previous.items():
        try:
            checked=datetime.datetime.fromisoformat(d['checkedAt'])
            if (NOW-checked).total_seconds()<3600:fresh[asin]=d
        except (KeyError,ValueError,TypeError):pass
    errors=[]; scanned=0; completed=0; newly=0
    observed={}
    baseline={}
    essential_budget=min(8,budget)
    seasonal_active=NOW.month==11 and NOW.day<=30
    seasonal_budget=min(4,max(0,budget-essential_budget)) if seasonal_active else 0
    broad_budget=budget-essential_budget-seasonal_budget
    for i in range(budget):
        if i<essential_budget:
            category,keyword=ESSENTIAL_QUERIES[(essential_offset+i)%len(ESSENTIAL_QUERIES)]
        elif i<essential_budget+seasonal_budget:
            category,keyword=BLACK_FRIDAY_QUERIES[(seasonal_offset+i-essential_budget)%len(BLACK_FRIDAY_QUERIES)]
        else:
            category,keyword=QUERIES[(offset+i-essential_budget-seasonal_budget)%len(QUERIES)]
        # Spread requests, respect throttling, and continue after transient failures.
        if i:time.sleep(1.25)
        payload={'partnerTag':tag,'marketplace':'www.amazon.com','keywords':keyword,
                 'searchIndex':category,'itemCount':10,'itemPage':1+(int(state.get('cycle',0))%3),
                 'resources':RESOURCES}
        try:
            result=api('https://creatorsapi.amazon/catalog/v1/searchItems',payload,
                       {'Authorization':'Bearer '+token,'x-marketplace':'www.amazon.com'})
            items=result.get('searchResult',{}).get('items',[]) or []
            scanned+=len(items)
            for item in items:
                baseline_item=parse(item,category,keyword,minimum_discount=0)
                if baseline_item and i<essential_budget:
                    baseline[baseline_item['asin']]=baseline_item
                d=parse(item,category,keyword)
                if d:
                    observed[d['asin']]=d
                    if d['asin'] not in previous or previous[d['asin']].get('price')!=d['price']:newly+=1
                    fresh[d['asin']]=d
            completed+=1
        except urllib.error.HTTPError as e:
            errors.append(category+' / '+keyword+': HTTP '+str(e.code))
            if e.code in (401,403,429):break
        except Exception as e:errors.append(category+' / '+keyword+': '+type(e).__name__)
    # Track valid everyday essentials even without a qualifying discount.
    # Only qualifying leads enter the public deal and candidate feeds.
    observed_drops=enrich(observed,STAMP,baseline=baseline)
    # Retained still-fresh leads may predate the evidence schema. Never
    # preserve a legacy score or imply a witnessed reduction for those leads.
    for asin, deal in fresh.items():
        if asin not in observed:
            deal['priceEvidence']='first_observation'
            deal['priorObservedPrice']=None
            deal['newObservedLow']=False
            deal['observedPriceDropPercent']=0
            deal['dealScore']=min(20,max(0,deal.get('discountPercent',0)-40))
    candidate_count=build_queue(observed,STAMP)
    # Don't discard existing still-fresh results when an API call fails.
    deals=sorted(fresh.values(),key=lambda d:(d.get('dealScore',0),d['discountPercent'],d['checkedAt']),reverse=True)[:150]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'updated':STAMP,'status':'partial' if errors else 'ok','scannedProducts':scanned,
      'requestsCompleted':completed,'errors':errors[:12],'deals':deals,'newOrChangedLeads':newly,'observedPriceDrops':observed_drops,'newCandidates':candidate_count,
      'note':'Only Amazon API snapshots under 1 hour old are displayed. Not verified checkout prices.'},indent=2))
    STATE.write_text(json.dumps({'essentialOffset':(essential_offset+essential_budget)%len(ESSENTIAL_QUERIES),'day':day,'callsToday':calls+completed+len(errors),
      'seasonalOffset':(seasonal_offset+seasonal_budget)%len(BLACK_FRIDAY_QUERIES),'nextOffset':(offset+broad_budget)%len(QUERIES),
      'cycle':int(state.get('cycle',0))+(1 if offset+broad_budget>=len(QUERIES) else 0)},indent=2))
    print('API products:',scanned,'requests:',completed,'current leads:',len(deals),'errors:',len(errors))
if __name__=='__main__':scan()
