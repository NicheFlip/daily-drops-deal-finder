"""Publish a safe, bounded public price-history summary from private PostgreSQL.
No credentials or unpublished rows are exported. Prices are API observations, not checkout quotes.
"""
import datetime,json,os,pathlib
OUT=pathlib.Path(__file__).parent/'data'/'price-history-public.json'
QUERY="""
SELECT p.product_id,p.title,p.product_url,p.image_url,p.category,
       COUNT(*)::integer AS samples,MIN(o.price) AS low,MAX(o.price) AS high,
       (ARRAY_AGG(o.price ORDER BY o.observed_at DESC))[1] AS latest,
       MAX(o.observed_at) AS last_seen
FROM products p JOIN price_observations o
 ON p.retailer=o.retailer AND p.product_id=o.product_id
WHERE p.retailer='Amazon'
GROUP BY p.product_id,p.title,p.product_url,p.image_url,p.category
ORDER BY MAX(o.observed_at) DESC
LIMIT 500
"""
def export():
 url=os.environ.get('DATABASE_URL')
 if not url:
  print('No DATABASE_URL; public history export skipped.')
  return False
 import psycopg
 with psycopg.connect(url,connect_timeout=12) as conn:
  with conn.cursor() as cur:
   cur.execute(QUERY)
   rows=cur.fetchall()
 records=[]
 for asin,title,link,image,category,samples,low,high,latest,seen in rows:
  if not isinstance(asin,str) or len(asin)!=10:continue
  records.append({'asin':asin,'title':title,'url':'https://www.amazon.com/dp/'+asin,
   'imageUrl':image if isinstance(image,str) and image.startswith('https://') else None,
   'category':category,'observations':samples,'observedLow':float(low),
   'observedHigh':float(high),'latestObserved':float(latest),'checkedAt':seen.isoformat()})
 payload={'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'source':'Amazon API sampled observations; not current checkout prices',
  'products':records}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(payload,indent=2)+'\n')
 print('Published '+str(len(records))+' historical product summaries.')
 return True
if __name__=='__main__':export()
