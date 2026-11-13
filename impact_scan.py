"""Read-only impact.com catalog discovery. Credentials never enter public output."""
import base64,datetime,json,os,pathlib,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/"data"/"impact-status.json"
BASE="https://api.impact.com"
def main():
    sid=os.environ.get("IMPACT_ACCOUNT_SID","").strip()
    token=os.environ.get("IMPACT_API_TOKEN","").strip()
    if not sid or not token: raise RuntimeError("Missing IMPACT_ACCOUNT_SID or IMPACT_API_TOKEN")
    if not sid.isalnum(): raise RuntimeError("Account SID must be alphanumeric")
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    endpoint=f"{BASE}/Mediapartners/{sid}/Marketplace/Products?PageSize=5"
    # impact.com API v16 uses HTTP Basic auth: Account SID as username, API token as password.
    auth=base64.b64encode((sid+":"+token).encode("utf-8")).decode("ascii")
    request=urllib.request.Request(endpoint,headers={
        "Authorization":"Basic "+auth,
        "Accept":"application/json",
        "User-Agent":"DailyDropsDealFinder/1.0"})
    status={"checkedAt":now,"source":"impact.com marketplace products API",
            "connection":"not_verified","productsReturned":0,
            "note":"Connectivity check only; no prices or affiliate links published."}
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            payload=json.load(response)
        if isinstance(payload,dict):
            # Impact API collections can be nested; count only actual returned records.
            for key in ("Products","products","Items","items"):
                items=payload.get(key)
                if isinstance(items,list):
                    status["productsReturned"]=len(items)
                    break
            status["connection"]="connected"
            status["note"]="API accepted request; product counts may be page-limited. Catalog access and price freshness require further validation."
        else:
            status["connection"]="connected"
            status["note"]="API returned an unexpected shape; inspect privately before product import."
    except urllib.error.HTTPError as exc:
        status["connection"]="http_error"
        status["httpStatus"]=exc.code
        status["note"]="API rejected request; verify token permissions, API version, and authentication. No secret or response body logged."
    except (urllib.error.URLError,TimeoutError) as exc:
        status["connection"]="network_error"
        status["note"]="API connection failed; retry or inspect network availability."
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(status,indent=2)+"\n")
    print("Impact connectivity:",status["connection"],"HTTP:",status.get("httpStatus","OK"),"products:",status["productsReturned"])
    if status["connection"]!="connected":raise RuntimeError("Impact API check unsuccessful; see safe status output")
if __name__=="__main__":main()
