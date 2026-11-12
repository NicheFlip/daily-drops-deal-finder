"""Safe Amazon Creators API connection check; does not print secrets or tokens."""
import os,json,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
out=Path('data/amazon-status.json')
status={'checkedAt':datetime.now(timezone.utc).isoformat(),'state':'not_configured','message':'API credentials or partner tag missing'}
cid=os.getenv('AMAZON_CREATORS_CREDENTIAL_ID','')
secret=os.getenv('AMAZON_CREATORS_SECRET','')
tag=os.getenv('AMAZON_PARTNER_TAG','')
version=os.getenv('AMAZON_CREATORS_VERSION','3.1')
endpoints={'3.1':'https://api.amazon.com/auth/o2/token','3.2':'https://api.amazon.co.uk/auth/o2/token','3.3':'https://api.amazon.co.jp/auth/o2/token'}
if cid and secret and tag and version in endpoints:
    try:
        payload=json.dumps({'grant_type':'client_credentials','client_id':cid,'client_secret':secret,'scope':'creatorsapi::default'}).encode()
        req=urllib.request.Request(endpoints[version],payload,{'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=20) as response:
            token=json.load(response).get('access_token')
        if not token: raise ValueError('No access token returned')
        status={'checkedAt':status['checkedAt'],'state':'authenticated','message':'Amazon OAuth authentication succeeded; catalog access not yet tested'}
    except urllib.error.HTTPError as e:
        status={'checkedAt':status['checkedAt'],'state':'auth_failed','message':'Amazon authentication returned HTTP '+str(e.code)}
    except Exception as e:
        status={'checkedAt':status['checkedAt'],'state':'auth_failed','message':'Amazon authentication check failed ('+type(e).__name__+')'}
elif cid and secret and not tag:
    status['message']='Add AMAZON_PARTNER_TAG repository secret to enable check'
elif version not in endpoints:
    status['message']='Invalid AMAZON_CREATORS_VERSION; expected 3.1, 3.2, or 3.3'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(status,indent=2))
print('Amazon connection state:',status['state'])
