"""Read-only Impact marketplace discovery; never publish credentials or raw API responses."""
import base64,datetime,json,os,pathlib,urllib.request,urllib.error,time
ROOT=pathlib.Path(__file__).parent
DATA=ROOT/"data"
BASE="https://api.impact.com"
CATEGORIES=("household","cleaning","laundry","kitchen","bedding","toys","kids clothing","coffee","storage","beauty","pet supplies")
def number(value):
    try:
        v=float(str(value).replace("$","").replace(",",""))
        return round(v,2) if 0<v<100000 else None
    except (ValueError,TypeError):return None
def truth(v):
    return v is True or str(v).lower() in ("true","yes","1")
def main():
    sid=os.environ.get("IMPACT_ACCOUNT_SID","").strip()
    token=os.environ.get("IMPACT_API_TOKEN","").strip()
    if not sid or not token or not sid.isalnum():raise RuntimeError("Impact credentials missing or invalid")
    auth=base64.b64encode((sid+":"+token).encode()).decode()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    records={}
    diagnostics=[]
    # Search several pages and everyday buying categories. Bound work to control API usage.
    searches=("",)+CATEGORIES
    for term in searches:
        page=1
        for _ in range(2):
            from urllib.parse import urlencode
            query={"PageSize":100,"Page":page}
            if term:query["Keyword"]=term
            url=BASE+"/Mediapartners/"+sid+"/Marketplace/Products?"+urlencode(query)
            req=urllib.request.Request(url,headers={"Authorization":"Basic "+auth,"Accept":"application/json","User-Agent":"DailyDropsDealFinder/2.0"})
            try:
                with urllib.request.urlopen(req,timeout=25) as response: payload=json.load(response)
            except urllib.error.HTTPError as exc:
                diagnostics.append({"search":term or "all","page":page,"httpStatus":exc.code})
                if exc.code in (401,403):raise RuntimeError("Impact API authorization failed")
                break
            except (urllib.error.URLError,TimeoutError,ValueError):
                diagnostics.append({"search":term or "all","page":page,"error":"request_failed"})
                break
            if not isinstance(payload,dict):break
            items=payload.get("Results",[])
            if not isinstance(items,list):break
            diagnostics.append({"search":term or "all","page":page,"returned":len(items)})
            for item in items:
                if not isinstance(item,dict):continue
                ident=str(item.get("Id") or item.get("Uri") or "")
                name=str(item.get("Name") or "").strip()
                if not ident or not name:continue
                price=number(item.get("BestPrice"))
                if price is None:continue
                discount=number(item.get("BestDiscountPercentage"))
                discount=min(100,max(0,discount or 0))
                stock=truth(item.get("ContainsOfferInStock"))
                sale=truth(item.get("ContainsOfferOnSale"))
                promo=truth(item.get("ContainsOfferOnPromotion"))
                category=str(item.get("Category") or "")
                text=(name+" "+category).lower()
                essentials=any(w in text for w in ("laundry","detergent","paper towel","toilet paper","dish soap","cleaning","coffee","diaper","trash bag","bedding","storage","kitchen","toy","pet","shampoo"))
                score=round(min(100,discount*.65+(18 if stock else 0)+(12 if sale or promo else 0)+(10 if essentials else 0)))
                # Do not infer a retailer or affiliate tracking link from the marketplace product.
                record={"id":ident[:160],"title":name[:240],"price":price,"discountReported":discount,
                        "image":str(item.get("ImageUrl") or "")[:700],
                        "category":category[:120],"inStockSignal":stock,"saleSignal":sale,"promotionSignal":promo,
                        "score":score,"source":"impact.com marketplace","observedAt":now,
                        "status":"research_only","retailer":"Not verified","affiliateUrl":None}
                old=records.get(ident)
                if old is None or record["score"]>old["score"]:records[ident]=record
            if len(items)<100:break
            page+=1
            time.sleep(.2)
    ranked=sorted(records.values(),key=lambda x:(-x["score"],-x["discountReported"],x["price"]))
    DATA.mkdir(exist_ok=True)
    output={"generatedAt":now,"source":"impact.com marketplace","verification":"Research leads only. Prices, seller, availability, and affiliate tracking must be checked before posting.",
            "count":len(ranked),"deals":ranked[:500]}
    (DATA/"impact-deals.json").write_text(json.dumps(output,indent=2)+"\n")
    status={"checkedAt":now,"connection":"connected","productsReturned":len(ranked),
            "searchesAttempted":len(searches),"diagnostics":diagnostics,
            "note":"Product leads saved; not verified checkout prices or retailer-specific clearance."}
    (DATA/"impact-status.json").write_text(json.dumps(status,indent=2)+"\n")
    print("Impact research products:",len(ranked),"searches:",len(searches))
if __name__=="__main__":main()
