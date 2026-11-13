"""Optional PostgreSQL archive for verified-source product observations.
Set DATABASE_URL as a GitHub Actions secret. Never expose it in GitHub Pages.
"""
import json,os,pathlib
ROOT=pathlib.Path(__file__).parent
SCHEMA="""
CREATE TABLE IF NOT EXISTS products (
 retailer TEXT NOT NULL,
 product_id TEXT NOT NULL,
 title TEXT NOT NULL,
 product_url TEXT NOT NULL,
 image_url TEXT,
 category TEXT,
 last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY (retailer,product_id)
);
CREATE TABLE IF NOT EXISTS price_observations (
 retailer TEXT NOT NULL,
 product_id TEXT NOT NULL,
 observed_at TIMESTAMPTZ NOT NULL,
 price NUMERIC(12,2) NOT NULL CHECK(price>0),
 reference_price NUMERIC(12,2),
 reference_type TEXT,
 source TEXT NOT NULL,
 PRIMARY KEY(retailer,product_id,observed_at),
 FOREIGN KEY(retailer,product_id) REFERENCES products(retailer,product_id)
);
CREATE INDEX IF NOT EXISTS idx_observations_latest ON price_observations(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_product ON price_observations(retailer,product_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS discoveries (
 retailer TEXT NOT NULL,
 product_id TEXT NOT NULL,
 observed_at TIMESTAMPTZ NOT NULL,
 reason TEXT NOT NULL,
 observed_price NUMERIC(12,2) NOT NULL,
 previous_observed_price NUMERIC(12,2),
 PRIMARY KEY(retailer,product_id,observed_at,reason),
 FOREIGN KEY(retailer,product_id) REFERENCES products(retailer,product_id)
);
"""
def persist(deals,discoveries=()):
 url=os.environ.get('DATABASE_URL','')
 if not url:
  print('PostgreSQL not configured; GitHub JSON archive remains active.')
  return False
 import psycopg
 with psycopg.connect(url,connect_timeout=12) as conn:
  with conn.cursor() as cur:
   cur.execute(SCHEMA)
   for d in deals:
    asin=d.get('asin')
    if not asin or not d.get('title') or not d.get('url') or not d.get('checkedAt'):continue
    cur.execute("""INSERT INTO products(retailer,product_id,title,product_url,image_url,category,last_seen)
      VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(retailer,product_id)
      DO UPDATE SET title=EXCLUDED.title,product_url=EXCLUDED.product_url,
      image_url=COALESCE(EXCLUDED.image_url,products.image_url),category=EXCLUDED.category,
      last_seen=GREATEST(products.last_seen,EXCLUDED.last_seen)""",
      ('Amazon',asin,d['title'],d['url'],d.get('imageUrl'),d.get('category'),d['checkedAt']))
    cur.execute("""INSERT INTO price_observations(retailer,product_id,observed_at,price,reference_price,reference_type,source)
      VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
      ('Amazon',asin,d['checkedAt'],d['price'],d.get('referencePrice'),d.get('referenceType'),'Amazon Creators API snapshot; checkout unverified'))
   for d in discoveries:
    asin=d.get('asin')
    if not asin or not d.get('checkedAt') or not d.get('reason'):continue
    cur.execute("""INSERT INTO discoveries(retailer,product_id,observed_at,reason,observed_price,previous_observed_price)
      SELECT %s,%s,%s,%s,%s,%s WHERE EXISTS(SELECT 1 FROM products WHERE retailer=%s AND product_id=%s)
      ON CONFLICT DO NOTHING""",
      ('Amazon',asin,d['checkedAt'],d['reason'],d['price'],d.get('previousObservedPrice'),'Amazon',asin))
 print('PostgreSQL observation archive updated.')
 return True
if __name__=='__main__':
 deals=json.loads((ROOT/'data'/'amazon-all-products.json').read_text()).get('products',[]) if (ROOT/'data'/'amazon-all-products.json').exists() else json.loads((ROOT/'data'/'amazon-deals.json').read_text()).get('deals',[])
 archive=json.loads((ROOT/'data'/'amazon-discovery-archive.json').read_text()).get('events',[])
 persist(deals,archive)
