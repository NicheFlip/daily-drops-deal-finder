"""Publish rotating official Walmart search destinations, NOT verified product deals."""
import datetime,json,pathlib,urllib.parse
ROOT=pathlib.Path(__file__).parent
OUT=ROOT/'data'/'walmart-research.json'
GROUPS={
 'Essentials':['laundry detergent clearance','paper towels deals','coffee rollback','diapers clearance','cleaning supplies deals','toilet paper deals'],
 'Toys and gifts':['toys clearance','LEGO deals','ride on toys clearance','electric ride on car kids','holiday gifts clearance'],
 'Bikes and scooters':['electric bikes deals','electric scooters deals','kids scooters clearance'],
 'Beauty':['skin care clearance','makeup deals','hair styling tools clearance'],
 'Home and kitchen':['air fryer clearance','robot vacuum deals','cookware clearance','bedding clearance','storage organizers deals'],
 'Electronics':['headphones clearance','tablets deals','portable chargers clearance'],
 'Fashion':['boys clothing clearance','girls clothing clearance','women clothing clearance','shoes clearance']
}
def build():
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 rows=[{'category':category,'query':q,'url':'https://www.walmart.com/search?'+urllib.parse.urlencode({'q':q}),'verifiedProduct':False,'verifiedPrice':False,'affiliateLink':None} for category,queries in GROUPS.items() for q in queries]
 return {'updated':now,'source':'Official Walmart search URLs; no product API or price verification','status':'research_only','count':len(rows),'searches':rows,'note':'Search links only. No prices, discounts, stock levels or affiliate links are claimed.'}
if __name__=='__main__':
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(build(),indent=2))
 print('Walmart research destinations:',len(build()['searches']))
