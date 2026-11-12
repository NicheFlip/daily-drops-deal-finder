"""Test Amazon Creators API catalog access without exposing credentials."""
import os,json,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
status={'checkedAt':datetime.now(timezone.utc).isoformat(),'state':'not_configured','message':'Missing credentials or partner tag'}
try:
    cid=os.environ['AMAZON_CREATORS_CREDENTIAL_ID']; secret=os.environ['AMAZON_CREATORS_SECRET']; tag=os.environ['AMAZON_PARTNER_TAG']
    token_req=urllib.request.Request('https://api.amazon.com/auth/o2/token',json.dumps({'grant_type':'client_credentials','client_id':cid,'client_secret':secret,'scope':'creatorsapi::default'}).encode(),{'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(token_req,timeout=25) as resp: token=json.load(resp)['access_token']
    body={'partnerTag':tag,'marketplace':'www.amazon.com','keywords':'kitchen storage','searchIndex':'HomeAndKitchen','itemCount':3,'resources':['itemInfo.title','offersV2.listings.price']}
    req=urllib.request.Request('https://creatorsapi.amazon/catalog/v1/searchItems',json.dumps(body).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+token,'x-marketplace':'www.amazon.com'},method='POST')
    with urllib.request.urlopen(req,timeout=25) as resp: data=json.load(resp)
    items=data.get('searchResult',{}).get('items',[])
    status={'checkedAt':status['checkedAt'],'state':'catalog_access_ok' if items else 'catalog_empty','message':'Catalog request succeeded; returned '+str(len(items))+' products. Price fields not independently verified.'}
except urllib.error.HTTPError as e:
    status={'checkedAt':status['checkedAt'],'state':'catalog_failed','message':'Catalog or authentication request returned HTTP '+str(e.code)}
except Exception as e:
    status={'checkedAt':status['checkedAt'],'state':'catalog_failed','message':'Catalog test failed ('+type(e).__name__+')'}
Path('data').mkdir(exist_ok=True)
Path('data/amazon-catalog-status.json').write_text(json.dumps(status,indent=2))
print(status['state'],status['message'])
