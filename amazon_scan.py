"""Daily Drops Amazon research scanner: rotating searches, accurate offer parsing, and safe output.
Official Creators API only. No scraping. API offer snapshots expire after 1 hour.
"""
import datetime,json,os,pathlib,re,time,urllib.error,urllib.request
from collections import defaultdict
from price_history import enrich, PATH as HISTORY_PATH
from candidate_queue import build_queue
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/'data'/'amazon-deals.json'
ALL_OUT=ROOT/'data'/'amazon-all-products.json'
STATE=ROOT/'data'/'amazon-scan-state.json'
NOW=datetime.datetime.now(datetime.timezone.utc)
STAMP=NOW.isoformat()
# Broad, deliberately safe categories. Keyword rotation widens coverage across runs.
QUERIES=[
('ToysAndGames','building blocks'),('ToysAndGames','board games'),('ToysAndGames','dolls'),('ToysAndGames','preschool toys'),('ToysAndGames','puzzles'),('ToysAndGames','remote control cars'),
('HomeAndKitchen','kitchen organizers'),('HomeAndKitchen','small kitchen appliances'),('HomeAndKitchen','cookware'),('HomeAndKitchen','bedding'),('HomeAndKitchen','storage baskets'),('HomeAndKitchen','coffee makers'),('HomeAndKitchen','vacuum cleaners'),
('Electronics','computer accessories'),('Electronics','smart home'),('Electronics','chargers'),('Electronics','tablets'),
('Beauty','skin care'),('Beauty','hair care'),('Beauty','makeup organizers'),('Beauty','beauty tools'),
('Fashion','women clothing'),('Fashion','handbags'),('Fashion','sneakers'),('Fashion','winter coats'),
('OfficeProducts','school supplies'),('PetSupplies','dog beds'),('HomeAndKitchen','outdoor decor'),('Baby','baby blankets'),
('ToysAndGames','holiday gifts'),('HomeAndKitchen','home decor'),('Electronics','portable speakers')
]
# Household search priorities reflect practical repeat purchases, not verified sales rank.
ESSENTIAL_QUERIES=[("All","laundry detergent"),("All","paper towels"),("All","toilet paper"),("All","dish soap"),("All","trash bags"),("All","coffee pods"),("All","ground coffee"),("All","diapers"),("All","baby wipes"),("All","dishwasher pods"),("All","cleaning wipes"),("All","hand soap"),("All","toothpaste"),("All","shampoo"),("All","pet food"),("All","food storage bags"),("All","batteries AA"),("All","dryer sheets"),("All","facial tissues"),("All","body wash"),("All","breakfast cereal"),("All","snack variety pack"),("All","water filters"),("All","laundry scent boosters")]
HIGH_DEMAND_QUERIES=[('All','best selling household essentials'),('ToysAndGames','ride on toys for kids'),('ToysAndGames','electric ride on cars for kids'),('All','electric scooters'),('All','electric bikes'),('ToysAndGames','outdoor toys'),('ToysAndGames','educational toys'),('ToysAndGames','LEGO building sets'),('Beauty','skin care gift sets'),('Beauty','hair styling tools'),('Beauty','makeup gift sets'),('HomeAndKitchen','robot vacuums'),('HomeAndKitchen','air fryers'),('HomeAndKitchen','blenders'),('HomeAndKitchen','bedding sets'),('HomeAndKitchen','storage organizers'),('Electronics','portable chargers'),('All','cleaning supplies'),('All','coffee'),('All','paper products'),('All','pet supplies')]
BLACK_FRIDAY_QUERIES=[('All','early black friday deals'),('HomeAndKitchen','black friday kitchen deals'),('ToysAndGames','black friday toys'),('HomeAndKitchen','black friday vacuum'),('All','black friday household essentials'),('All','black friday coffee makers'),('All','black friday gifts')]
# Search Amazon quick-link topics are also scanned automatically, not just opened in a browser.
QUICK_LINK_QUERIES=[
 ('ToysAndGames','toys and games'),('HomeAndKitchen','kitchen appliances'),
 ('HomeAndKitchen','home organization'),
 ('Beauty','beauty tools'),('ToysAndGames','holiday gifts'),
 ('Fashion','women pants'),('Fashion','shoes')
]
# Wider catalog coverage: popular deal categories beyond the original list.
# Search indexes are the standard www.amazon.com SearchIndex values.
QUERIES+=[
('Electronics','bluetooth speakers'),('Electronics','smart watches'),('Electronics','streaming devices'),('Electronics','security cameras'),('Electronics','smart plugs'),('Electronics','power banks'),('Electronics','usb c cables'),('Electronics','wireless chargers'),('Electronics','phone cases'),('Electronics','tv mounts'),('Electronics','dash cams'),('Electronics','action cameras'),('Electronics','projectors'),('Electronics','e readers'),('Electronics','fitness trackers'),('Electronics','surge protectors'),('Electronics','smart lights'),('Electronics','video doorbells'),
('Computers','computer monitors'),('Computers','gaming mouse'),('Computers','mechanical keyboards'),('Computers','external hard drives'),('Computers','usb flash drives'),('Computers','laptop stands'),('Computers','webcams'),('Computers','wifi routers'),('Computers','memory cards'),('Computers','laptop bags'),
('HomeAndKitchen','air purifiers'),('HomeAndKitchen','humidifiers'),('HomeAndKitchen','space heaters'),('HomeAndKitchen','throw blankets'),('HomeAndKitchen','pillows'),('HomeAndKitchen','mattress toppers'),('HomeAndKitchen','bath towels'),('HomeAndKitchen','shower curtains'),('HomeAndKitchen','curtains'),('HomeAndKitchen','area rugs'),('HomeAndKitchen','wall art'),('HomeAndKitchen','candles'),('HomeAndKitchen','christmas decorations'),('HomeAndKitchen','closet organizers'),('HomeAndKitchen','food storage containers'),('HomeAndKitchen','knife sets'),('HomeAndKitchen','cutting boards'),('HomeAndKitchen','baking supplies'),('HomeAndKitchen','water bottles'),('HomeAndKitchen','travel mugs'),('HomeAndKitchen','slow cookers'),('HomeAndKitchen','pressure cookers'),('HomeAndKitchen','toasters'),('HomeAndKitchen','electric kettles'),('HomeAndKitchen','espresso machines'),('HomeAndKitchen','stand mixers'),('HomeAndKitchen','food processors'),('HomeAndKitchen','cordless vacuums'),('HomeAndKitchen','steam mops'),('HomeAndKitchen','dinnerware sets'),('HomeAndKitchen','kitchen utensils'),
('Appliances','mini fridges'),('Appliances','ice makers'),('Appliances','countertop microwaves'),
('ToysAndGames','stem toys'),('ToysAndGames','action figures'),('ToysAndGames','plush toys'),('ToysAndGames','card games'),('ToysAndGames','arts and crafts kits'),('ToysAndGames','play kitchen'),('ToysAndGames','toy vehicles'),('ToysAndGames','dollhouses'),('ToysAndGames','nerf blasters'),('ToysAndGames','magnetic tiles'),('ToysAndGames','kids tablets'),('ToysAndGames','stocking stuffers'),
('VideoGames','nintendo switch games'),('VideoGames','ps5 games'),('VideoGames','xbox games'),('VideoGames','gaming controllers'),('VideoGames','gaming accessories'),('VideoGames','gaming chairs'),
('Beauty','perfume'),('Beauty','nail polish'),('Beauty','face masks'),('Beauty','hair dryers'),('Beauty','curling irons'),('Beauty','makeup brushes'),('Beauty','sunscreen'),('Beauty','moisturizer'),('Beauty','serum'),('Beauty','lip care'),
('HealthPersonalCare','vitamins'),('HealthPersonalCare','electric toothbrush'),('HealthPersonalCare','electric shavers'),('HealthPersonalCare','massage guns'),('HealthPersonalCare','first aid'),('HealthPersonalCare','protein powder'),('HealthPersonalCare','thermometers'),('HealthPersonalCare','heating pads'),('HealthPersonalCare','oral care'),('HealthPersonalCare','deodorant'),('HealthPersonalCare','razors'),
('ToolsAndHomeImprovement','power tools'),('ToolsAndHomeImprovement','cordless drills'),('ToolsAndHomeImprovement','tool sets'),('ToolsAndHomeImprovement','led light bulbs'),('ToolsAndHomeImprovement','flashlights'),('ToolsAndHomeImprovement','smart thermostats'),('ToolsAndHomeImprovement','door locks'),('ToolsAndHomeImprovement','extension cords'),('ToolsAndHomeImprovement','shop vacuums'),('ToolsAndHomeImprovement','faucets'),('ToolsAndHomeImprovement','shower heads'),('ToolsAndHomeImprovement','tool storage'),
('GardenAndOutdoor','patio furniture'),('GardenAndOutdoor','grills'),('GardenAndOutdoor','solar lights'),('GardenAndOutdoor','garden hoses'),('GardenAndOutdoor','planters'),('GardenAndOutdoor','string lights'),('GardenAndOutdoor','leaf blowers'),('GardenAndOutdoor','pressure washers'),
('SportsAndOutdoors','camping gear'),('SportsAndOutdoors','yoga mats'),('SportsAndOutdoors','dumbbells'),('SportsAndOutdoors','resistance bands'),('SportsAndOutdoors','bikes'),('SportsAndOutdoors','coolers'),('SportsAndOutdoors','hiking backpacks'),('SportsAndOutdoors','fishing gear'),('SportsAndOutdoors','exercise bikes'),('SportsAndOutdoors','sleds'),('SportsAndOutdoors','golf accessories'),
('PetSupplies','cat litter'),('PetSupplies','dog toys'),('PetSupplies','cat trees'),('PetSupplies','dog treats'),('PetSupplies','pet carriers'),('PetSupplies','aquarium supplies'),('PetSupplies','dog harness'),('PetSupplies','pet grooming'),
('Baby','strollers'),('Baby','car seats'),('Baby','baby monitors'),('Baby','high chairs'),('Baby','baby bottles'),('Baby','diaper bags'),('Baby','baby toys'),('Baby','nursery decor'),
('OfficeProducts','office chairs'),('OfficeProducts','desk organizers'),('OfficeProducts','printers'),('OfficeProducts','notebooks'),('OfficeProducts','pens'),('OfficeProducts','label makers'),('OfficeProducts','standing desks'),('OfficeProducts','shredders'),
('Automotive','car accessories'),('Automotive','car vacuums'),('Automotive','jump starters'),('Automotive','tire inflators'),('Automotive','car phone mounts'),('Automotive','car seat covers'),('Automotive','car cleaning'),('Automotive','floor mats'),
('Fashion','men clothing'),('Fashion','hoodies'),('Fashion','leggings'),('Fashion','socks'),('Fashion','pajamas'),('Fashion','backpacks'),('Fashion','wallets'),('Fashion','watches'),('Fashion','jewelry'),('Fashion','sunglasses'),('Fashion','kids clothing'),('Fashion','boots'),('Fashion','slippers'),('Fashion','gloves'),
('Luggage','luggage sets'),('Luggage','carry on luggage'),('Luggage','travel accessories'),
('GroceryAndGourmetFood','snacks'),('GroceryAndGourmetFood','candy'),('GroceryAndGourmetFood','tea'),('GroceryAndGourmetFood','k cups'),('GroceryAndGourmetFood','energy drinks'),('GroceryAndGourmetFood','protein bars'),('GroceryAndGourmetFood','gift baskets'),('GroceryAndGourmetFood','spices'),
('All','household supplies'),('All','storage bins'),('All','light bulbs'),('All','air fresheners'),('All','sponges'),('All','zip bags'),('All','aluminum foil'),('All','plastic wrap'),('All','paper plates'),('All','gift wrap'),
]
# Each scan is limited by a request budget (env AMAZON_SCAN_REQUEST_BUDGET, hard cap 2000),
# a wall-clock limit, the daily cap, and >=1.1s spacing between requests (API limit is 1 TPS).
def _env_int(name,default,low,high):
    try:value=int(os.environ.get(name,default))
    except (TypeError,ValueError):value=default
    return max(low,min(high,value))
REQUEST_BUDGET_HARD_CAP=2000
PER_RUN=_env_int('AMAZON_SCAN_REQUEST_BUDGET',300,1,REQUEST_BUDGET_HARD_CAP)
MAX_DAILY_CALLS=_env_int('AMAZON_MAX_DAILY_CALLS',8000,1,200000)  # kept under the base 8,640 requests/day
MAX_SCAN_SECONDS=_env_int('AMAZON_SCAN_MAX_SECONDS',1200,60,3000)
MIN_REQUEST_INTERVAL=1.1
RETRY_DELAYS=(2,5,10)
TRANSIENT_HTTP=(429,500,502,503,504)
BROAD_PAGES=3
WATCH_CALLS=30
WATCH_BATCH=10
WATCH_POOL_LIMIT=600
RESOURCES=['itemInfo.title','images.primary.medium','offersV2.listings.price','offersV2.listings.availability','offersV2.listings.condition']
class BudgetReached(Exception):
    """Raised when the per-run request budget or time limit is used up."""
def api(url,payload,headers=None):
    req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json',**(headers or {})},method='POST')
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def amount(v):
    if not isinstance(v,dict):return None
    if 'money' in v:return amount(v['money'])
    x=v.get('amount')
    try:return round(float(x),2) if x is not None else None
    except (TypeError,ValueError):return None
EXCLUDED_AUDIO=re.compile(r'\b(?:headphones?|headsets?|earbuds?|earpods?|airpods?|earphones?|in[ -]?ear headphones?|over[ -]?ear headphones?)\b',re.I)
def excluded_audio(title):
    return bool(EXCLUDED_AUDIO.search(str(title or '')))
def parse(item,category,keyword,minimum_discount=40):
    asin=item.get('asin','')
    if not re.fullmatch('[A-Z0-9]{10}',asin):return None
    title=item.get('itemInfo',{}).get('title',{}).get('displayValue','')
    if not title or excluded_audio(title):return None
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
          'url':'https://www.amazon.com/dp/'+asin,'imageUrl':((item.get('images') or {}).get('primary') or {}).get('medium',{}).get('url'),'price':price,
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
    demand_offset=int(state.get('demandOffset',0))%len(HIGH_DEMAND_QUERIES)
    quick_offset=int(state.get('quickLinkOffset',0))%len(QUICK_LINK_QUERIES)
    budget=max(0,min(PER_RUN,MAX_DAILY_CALLS-calls))
    if budget==0:
        raise RuntimeError('Amazon daily request budget exhausted; keeping previous published deals instead of replacing them with an empty scan')
    run_number=int(state.get('runNumber',0))
    previous={}
    if OUT.exists():
        try:previous={d['asin']:d for d in json.loads(OUT.read_text()).get('deals',[]) if d.get('asin')}
        except (ValueError,KeyError):pass
    previous_asins=set(previous)
    # Keep a rolling discovery window; each product retains its original checkedAt.
    # Older observations are not represented as fresh prices.
    fresh={}
    for asin,d in previous.items():
        try:
            checked=datetime.datetime.fromisoformat(d['checkedAt'])
            if (NOW-checked).total_seconds()<6*3600:fresh[asin]=d
        except (KeyError,ValueError,TypeError):pass
    all_products={}
    if ALL_OUT.exists():
        try:
            prior=json.loads(ALL_OUT.read_text())
            for d in prior.get('products',[]):
                checked=datetime.datetime.fromisoformat(d['checkedAt'])
                if (NOW-checked).total_seconds()<24*3600:all_products[d['asin']]=d
        except (ValueError,KeyError,TypeError):pass
    errors=[]; scanned=0; completed=0; newly=0
    observed={}
    baseline={}
    # Build a rotating watch pool from observed history; API lookups cost one call per 10 ASINs.
    try:
        history=json.loads(HISTORY_PATH.read_text()).get('items',{})
        if not isinstance(history,dict):history={}
    except (OSError,ValueError,TypeError):history={}
    eligible=[]
    for asin,entry in history.items():
        if not re.fullmatch(r'[A-Z0-9]{10}',asin) or not isinstance(entry,dict):continue
        if excluded_audio(entry.get('title','')) or not entry.get('points'):continue
        try:
            last=datetime.datetime.fromisoformat(entry.get('lastSeen','').replace('Z','+00:00'))
            if (NOW-last).days>30:continue
        except (ValueError,TypeError):continue
        essential=bool(re.search(r'coffee|laundry|detergent|paper|soap|diaper|clean|trash|dish|battery|toothpaste|shampoo|wipes',entry.get('title',''),re.I))
        eligible.append((asin,entry,essential))
    eligible.sort(key=lambda x:(x[2],len(x[1].get('points',[])),x[1].get('lastSeen','')),reverse=True)
    watch_pool=[x[0] for x in eligible[:WATCH_POOL_LIMIT]]
    watch_set=set(watch_pool)
    watch_offset=int(state.get('watchOffset',0))%max(1,len(watch_pool))
    rotated=watch_pool[watch_offset:]+watch_pool[:watch_offset]
    # Reserve up to a quarter of the run for re-checking watched ASINs (10 per GetItems call).
    watch_budget=min(-(-len(rotated)//WATCH_BATCH),budget//4,WATCH_CALLS) if rotated else 0
    discovery_budget=budget-watch_budget
    # Core repeat-purchase searches recur every run; remaining calls rotate across
    # seasonal, popular and broad categories so the feed discovers different items.
    essential_budget=min(len(ESSENTIAL_QUERIES),discovery_budget)
    seasonal_active=NOW.month==11 and NOW.day<=30
    seasonal_budget=min(len(BLACK_FRIDAY_QUERIES),max(0,discovery_budget-essential_budget)) if seasonal_active else 0
    demand_budget=min(len(HIGH_DEMAND_QUERIES),max(0,discovery_budget-essential_budget-seasonal_budget))
    quick_budget=min(len(QUICK_LINK_QUERIES),max(0,discovery_budget-essential_budget-seasonal_budget-demand_budget))
    broad_budget=discovery_budget-essential_budget-seasonal_budget-demand_budget-quick_budget
    cycle=int(state.get('cycle',0))
    plan=[]
    for i in range(discovery_budget):
        if i<essential_budget:
            category,keyword=ESSENTIAL_QUERIES[(essential_offset+i)%len(ESSENTIAL_QUERIES)]
        elif i<essential_budget+seasonal_budget:
            category,keyword=BLACK_FRIDAY_QUERIES[(seasonal_offset+i-essential_budget)%len(BLACK_FRIDAY_QUERIES)]
        elif i<essential_budget+seasonal_budget+demand_budget:
            category,keyword=HIGH_DEMAND_QUERIES[(demand_offset+i-essential_budget-seasonal_budget)%len(HIGH_DEMAND_QUERIES)]
        elif i<essential_budget+seasonal_budget+demand_budget+quick_budget:
            category,keyword=QUICK_LINK_QUERIES[(quick_offset+i-essential_budget-seasonal_budget-demand_budget)%len(QUICK_LINK_QUERIES)]
        else:
            # Broad list: walk keywords in order; each full pass moves to the next results page.
            g=cycle*len(QUERIES)+offset+i-(discovery_budget-broad_budget)
            category,keyword=QUERIES[g%len(QUERIES)]
            plan.append((category,keyword,1+(g//len(QUERIES))%BROAD_PAGES,False))
            continue
        # Rotate results pages on every run, not only when a keyword list wraps.
        page=1+((run_number//2+i//6)%5)
        plan.append((category,keyword,page,i<essential_budget))
    # Never spend a request on the same search twice in one run.
    seen_searches=set(); deduped=[]
    for entry in plan:
        key=(entry[0],entry[1].lower(),entry[2])
        if key in seen_searches:continue
        seen_searches.add(key); deduped.append(entry)
    plan=deduped
    searched=[]
    unique_seen=set()
    headers={'Authorization':'Bearer '+token,'x-marketplace':'www.amazon.com'}
    meter={'attempts':0,'last':0.0}
    started=time.monotonic()
    def call(url,payload):
        """One throttled API request with backoff on throttling/transient errors.
        Every attempt (including retries) counts against this run's request budget."""
        for retry in range(len(RETRY_DELAYS)+1):
            if meter['attempts']>=budget or time.monotonic()-started>MAX_SCAN_SECONDS:raise BudgetReached()
            wait=MIN_REQUEST_INTERVAL-(time.monotonic()-meter['last'])
            if wait>0:time.sleep(wait)
            meter['last']=time.monotonic(); meter['attempts']+=1
            try:return api(url,payload,headers)
            except urllib.error.HTTPError as e:
                if e.code not in TRANSIENT_HTTP or retry==len(RETRY_DELAYS):raise
            except (urllib.error.URLError,TimeoutError,ConnectionError):
                if retry==len(RETRY_DELAYS):raise
            time.sleep(RETRY_DELAYS[retry])
    stopped_reason=None
    for i,(category,keyword,page,is_essential) in enumerate(plan):
        payload={'partnerTag':tag,'marketplace':'www.amazon.com','keywords':keyword,
                 'searchIndex':category,'itemCount':10,'itemPage':page,
                 'resources':RESOURCES}
        try:
            result=call('https://creatorsapi.amazon/catalog/v1/searchItems',payload)
            searched.append({'category':category,'keyword':keyword,'page':page})
            items=result.get('searchResult',{}).get('items',[]) or []
            scanned+=len(items)
            unique_seen.update(item.get('asin') for item in items if item.get('asin'))
            for item in items:
                baseline_item=parse(item,category,keyword,minimum_discount=0)
                if baseline_item:
                    all_products[baseline_item['asin']]=baseline_item
                    # Watched ASINs found by search keep their history baseline without a GetItems call.
                    if is_essential or baseline_item['asin'] in watch_set:baseline[baseline_item['asin']]=baseline_item
                d=parse(item,category,keyword)
                if d:
                    observed[d['asin']]=d
                    if d['asin'] not in previous or previous[d['asin']].get('price')!=d['price']:newly+=1
                    fresh[d['asin']]=d
            completed+=1
        except BudgetReached:
            stopped_reason='budget'; break
        except urllib.error.HTTPError as e:
            errors.append(category+' / '+keyword+': HTTP '+str(e.code))
            if e.code in (401,403,429):stopped_reason='HTTP '+str(e.code); break
        except Exception as e:errors.append(category+' / '+keyword+': '+type(e).__name__)
    # Watched ASINs already returned by a search this run are skipped (deduped).
    watch_batches=[]; pending=[]; consumed=0
    for asin in rotated:
        if len(watch_batches)>=watch_budget:break
        consumed+=1
        if asin in unique_seen:continue
        pending.append(asin)
        if len(pending)==WATCH_BATCH:watch_batches.append(pending); pending=[]
    if pending and len(watch_batches)<watch_budget:watch_batches.append(pending)
    watch_completed=0
    watch_requested=0
    for batch in watch_batches:
        if stopped_reason:break
        try:
            result=call('https://creatorsapi.amazon/catalog/v1/getItems',
                       {'partnerTag':tag,'marketplace':'www.amazon.com','itemIds':batch,'resources':RESOURCES})
            searched.append({'category':'Watched ASINs','keyword':'GetItems','count':len(batch)})
            watch_requested+=len(batch)
            items=result.get('itemsResult',{}).get('items',[]) or []
            scanned+=len(items)
            unique_seen.update(item.get('asin') for item in items if item.get('asin'))
            for item in items:
                asin=item.get('asin','')
                category=history.get(asin,{}).get('category') or 'All'
                baseline_item=parse(item,category,'Watched ASIN',minimum_discount=0)
                if baseline_item:
                    all_products[asin]=baseline_item
                    baseline[asin]=baseline_item
                d=parse(item,category,'Watched ASIN')
                if d:
                    observed[asin]=d
                    if asin not in previous or previous[asin].get('price')!=d['price']:newly+=1
                    fresh[asin]=d
            completed+=1
            watch_completed+=1
        except BudgetReached:
            stopped_reason='budget'; break
        except urllib.error.HTTPError as e:
            errors.append('Watch GetItems: HTTP '+str(e.code))
            if e.code in (401,403,429):break
        except Exception as e:errors.append('Watch GetItems: '+type(e).__name__)
    attempts=meter['attempts']
    duration=round(time.monotonic()-started,1)
    # Never overwrite a working public feed when every API request failed or returned nothing.
    if completed==0 or scanned==0:
        raise RuntimeError(f'Amazon scan returned no usable products (requests={completed}, products={scanned}, errors={errors[:4]}). Previous public feed preserved.')
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
    deals=sorted((d for d in fresh.values() if not excluded_audio(d.get('title'))),key=lambda d:(d['asin'] not in previous_asins,d.get('priceEvidence')=='observed_reduction',d.get('dealScore',0),d['checkedAt']),reverse=True)[:150]
    OUT.parent.mkdir(exist_ok=True)
    ALL_OUT.write_text(json.dumps({'updated':STAMP,'scannedProducts':scanned,'requestsCompleted':completed,'uniqueProductsSeen':len(unique_seen),'products':sorted(all_products.values(),key=lambda d:d['checkedAt'],reverse=True)[:4000]},indent=2))
    OUT.write_text(json.dumps({'updated':STAMP,'status':'partial' if errors else 'ok','scannedProducts':scanned,
      'requestsCompleted':completed,'uniqueProductsSeen':len(unique_seen),'searches':searched,'runNumber':run_number+1,'discoveryRequestsPlanned':discovery_budget,'watchRequestsCompleted':watch_completed,'watchedAsinsRequested':watch_requested,'requestBudget':budget,'requestsAttempted':attempts,'durationSeconds':duration,'stoppedEarly':stopped_reason,'errors':errors[:12],'deals':deals,'newOrChangedLeads':newly,'observedPriceDrops':observed_drops,'newCandidates':candidate_count,
      'note':'Scanner observations with individual timestamps; recent discoveries are retained across runs.'},indent=2))
    STATE.write_text(json.dumps({'essentialOffset':(essential_offset+essential_budget)%len(ESSENTIAL_QUERIES),'day':day,'callsToday':calls+attempts,
      'quickLinkOffset':(quick_offset+quick_budget)%len(QUICK_LINK_QUERIES),
      'seasonalOffset':(seasonal_offset+seasonal_budget)%len(BLACK_FRIDAY_QUERIES),'demandOffset':(demand_offset+demand_budget)%len(HIGH_DEMAND_QUERIES),'nextOffset':(offset+broad_budget)%len(QUERIES),
      'watchOffset':(watch_offset+consumed)%max(1,len(watch_pool)),'runNumber':run_number+1,'cycle':cycle+(offset+broad_budget)//len(QUERIES)},indent=2))
    print('API products:',scanned,'unique products:',len(unique_seen),'requests:',completed,'attempts:',attempts,'budget:',budget,'seconds:',duration,'stopped early:',stopped_reason,'new/changed:',newly,'rolling leads:',len(deals),'errors:',len(errors))
if __name__=='__main__':scan()
