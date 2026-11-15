"""Read-only Impact marketplace discovery; never publish credentials or raw API responses."""
import base64, datetime, json, os, pathlib, urllib.request, urllib.error, time, urllib.parse
ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
BASE = "https://api.impact.com"
CATEGORIES = ("household", "cleaning", "laundry", "kitchen", "bedding", "toys", "kids clothing", "coffee", "storage", "beauty", "pet supplies")

def number(value):
    try:
        v = float(str(value).replace("$", "").replace(",", ""))
        return round(v, 2) if 0 < v < 100000 else None
    except (ValueError, TypeError):
        return None

def truth(v):
    return v is True or str(v).lower() in ("true", "yes", "1")

def get_tracking_url(item, sid, token, walmart_pid, sams_pid):
    """Pull existing tracking URL or generate one if we have a destination + program ID."""
    url = item.get("Url") or item.get("url") or item.get("TrackingUrl") or item.get("trackingUrl")
    original = item.get("OriginalUrl") or item.get("originalUrl") or item.get("ProductUrl") or item.get("productUrl")
    
    offers = item.get("Offers") or item.get("offers") or []
    if isinstance(offers, list) and offers:
        for offer in offers:
            if isinstance(offer, dict):
                url = url or offer.get("Url") or offer.get("url")
                original = original or offer.get("OriginalUrl") or offer.get("originalUrl")
                break

    if url and isinstance(url, str) and url.startswith("http"):
        return url, original

    dest = original or url
    if not dest or not isinstance(dest, str) or not dest.startswith("http"):
        return None, original

    dest_lower = dest.lower()
    program_id = None
    if "walmart.com" in dest_lower and walmart_pid:
        program_id = walmart_pid
    elif ("samsclub.com" in dest_lower or "sam's" in dest_lower) and sams_pid:
        program_id = sams_pid

    if not program_id:
        return None, original

    try:
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        params = urllib.parse.urlencode({"DeepLink": dest, "Type": "Regular"})
        link_url = f"{BASE}/Mediapartners/{sid}/Programs/{program_id}/TrackingLinks?{params}"
        req = urllib.request.Request(link_url, method="POST", headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "User-Agent": "DailyDropsDealFinder/2.1"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        tracking = data.get("TrackingURL") or data.get("TrackingLink")
        if tracking and isinstance(tracking, str) and tracking.startswith("http"):
            return tracking, original
    except Exception:
        pass
    return None, original

def main():
    sid = os.environ.get("IMPACT_ACCOUNT_SID", "").strip()
    token = os.environ.get("IMPACT_API_TOKEN", "").strip()
    walmart_pid = os.environ.get("WALMART_PROGRAM_ID", "").strip()
    sams_pid = os.environ.get("SAMS_PROGRAM_ID", "").strip()
    if not sid or not token or not sid.isalnum():
        raise RuntimeError("Impact credentials missing or invalid")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = {}
    diagnostics = []

    searches = ("",) + CATEGORIES
    for term in searches:
        page = 1
        for _ in range(2):
            query = {"PageSize": 100, "Page": page}
            if term:
                query["Keyword"] = term
            url = BASE + "/Mediapartners/" + sid + "/Marketplace/Products?" + urllib.parse.urlencode(query)
            req = urllib.request.Request(url, headers={
                "Authorization": "Basic " + auth,
                "Accept": "application/json",
                "User-Agent": "DailyDropsDealFinder/2.1"
            })
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as exc:
                diagnostics.append({"search": term or "all", "page": page, "httpStatus": exc.code})
                if exc.code in (401, 403):
                    raise RuntimeError("Impact API authorization failed")
                break
            except (urllib.error.URLError, TimeoutError, ValueError):
                diagnostics.append({"search": term or "all", "page": page, "error": "request_failed"})
                break
            if not isinstance(payload, dict):
                break
            items = payload.get("Results") or payload.get("results") or []
            if not isinstance(items, list):
                break
            diagnostics.append({"search": term or "all", "page": page, "returned": len(items)})
            for item in items:
                if not isinstance(item, dict):
                    continue
                ident = str(item.get("Id") or item.get("Uri") or "")
                name = str(item.get("Name") or "").strip()
                if not ident or not name:
                    continue
                price = number(item.get("BestPrice") or item.get("CurrentPrice") or item.get("Price"))
                if price is None:
                    continue
                discount = number(item.get("BestDiscountPercentage") or item.get("DiscountPercentage"))
                discount = min(100, max(0, discount or 0))
                stock = truth(item.get("ContainsOfferInStock") or item.get("InStock"))
                sale = truth(item.get("ContainsOfferOnSale") or item.get("OnSale"))
                promo = truth(item.get("ContainsOfferOnPromotion") or item.get("OnPromotion"))
                category = str(item.get("Category") or "")
                text = (name + " " + category).lower()
                essentials = any(w in text for w in ("laundry", "detergent", "paper towel", "toilet paper", "dish soap", "cleaning", "coffee", "diaper", "trash bag", "bedding", "storage", "kitchen", "toy", "pet", "shampoo"))
                score = round(min(100, discount * .65 + (18 if stock else 0) + (12 if sale or promo else 0) + (10 if essentials else 0)))

                affiliate_url, original_url = get_tracking_url(item, sid, token, walmart_pid, sams_pid)
                retailer = "Not verified"
                if original_url and "walmart.com" in original_url.lower():
                    retailer = "Walmart"
                elif original_url and ("samsclub.com" in original_url.lower() or "sam's" in original_url.lower()):
                    retailer = "Sam's Club"
                elif "walmartimages" in str(item.get("ImageUrl") or "").lower():
                    retailer = "Walmart"

                status = "deal" if affiliate_url else "research_only"

                record = {
                    "id": ident[:160],
                    "title": name[:240],
                    "price": price,
                    "discountReported": discount,
                    "image": str(item.get("ImageUrl") or "")[:700],
                    "category": category[:120],
                    "inStockSignal": stock,
                    "saleSignal": sale,
                    "promotionSignal": promo,
                    "score": score,
                    "source": "impact.com marketplace",
                    "observedAt": now,
                    "status": status,
                    "retailer": retailer,
                    "affiliateUrl": affiliate_url,
                    "originalUrl": original_url
                }
                old = records.get(ident)
                if old is None or record["score"] > old["score"]:
                    records[ident] = record
            if len(items) < 100:
                break
            page += 1
            time.sleep(0.2)

    ranked = sorted(records.values(), key=lambda x: (-x["score"], -x["discountReported"], x["price"]))
    DATA.mkdir(exist_ok=True)
    output = {
        "generatedAt": now,
        "source": "impact.com marketplace",
        "verification": "Research leads. Affiliate links generated when available from Impact or Tracking Links API.",
        "count": len(ranked),
        "deals": ranked[:500]
    }
    (DATA / "impact-deals.json").write_text(json.dumps(output, indent=2) + "\n")
    status = {
        "checkedAt": now,
        "connection": "connected",
        "productsReturned": len(ranked),
        "withAffiliateLinks": sum(1 for d in ranked if d.get("affiliateUrl")),
        "searchesAttempted": len(searches),
        "diagnostics": diagnostics,
        "note": "Product leads saved with affiliate links when available."
    }
    (DATA / "impact-status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(f"Impact research products: {len(ranked)} (with links: {status['withAffiliateLinks']})")

if __name__ == "__main__":
    main()
