import json,os,re,datetime,pathlib,urllib.parse
body=os.environ.get('ISSUE_BODY','')
start=body.find('DAILY_DROPS_COMMUNITY_JSON_START')
end=body.find('DAILY_DROPS_COMMUNITY_JSON_END')
if start<0 or end<start: raise SystemExit('Missing structured verified deal payload')
d=json.loads(body[start+len('DAILY_DROPS_COMMUNITY_JSON_START'):end].strip())
asin=str(d.get('asin','')).upper();title=str(d.get('title','')).strip()[:220];url=str(d.get('url','')).strip();price=float(d.get('price',0))
if not re.fullmatch(r'[A-Z0-9]{10}',asin) or not title or not (0<price<100000):raise SystemExit('Invalid product ID/title/price')
u=urllib.parse.urlparse(url)
if u.scheme!='https' or u.hostname not in ('amazon.com','www.amazon.com') or u.path!='/dp/'+asin or urllib.parse.parse_qs(u.query).get('tag')!=['dealstoday0b3-20']:raise SystemExit('Link must be clean product URL with own affiliate tag')
now=datetime.datetime.now(datetime.timezone.utc).isoformat();p=pathlib.Path('data/community-verified.json');j=json.loads(p.read_text());deals=[x for x in j.get('deals',[]) if x.get('asin')!=asin]
deals.insert(0,{'asin':asin,'title':title,'price':round(price,2),'url':url,'retailer':'Amazon','category':'Other','keyword':'Community verified','checkedAt':now,'firstSeen':now,'source':'Community lead — owner verified','verification':'Price and product manually verified by owner; confirm at checkout','discountPercent':0,'imageUrl':''})
j.update({'format':'daily-drops-community-verified-v1','updatedAt':now,'deals':deals[:250]});p.write_text(json.dumps(j,indent=2)+'\\n')
