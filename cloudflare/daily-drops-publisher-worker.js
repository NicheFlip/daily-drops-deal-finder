// Daily Drops Publisher — Cloudflare Worker. D1 binding: DB; secret: PUBLISH_SECRET.
// Admin UI and write API are same-origin; public API is read-only.
const SHOP_ORIGIN='https://nicheflip.github.io';
const AFFILIATE_TAG='dealstoday0b3-20';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'};
const json=(data,status=200,extra={})=>new Response(JSON.stringify(data),{status,headers:{...headers,...extra}});
const encoder=new TextEncoder();
const hex=bytes=>Array.from(new Uint8Array(bytes)).map(x=>x.toString(16).padStart(2,'0')).join('');
async function signature(secret,payload){const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return hex(await crypto.subtle.sign('HMAC',key,encoder.encode(payload)))}
function equal(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0}
async function authorized(request,env){const cookie=request.headers.get('cookie')||'';const token=cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('dd_session='))?.slice(11);if(!token)return false;const parts=token.split('.');if(parts.length!==2||!/^[0-9]{10,13}$/.test(parts[0])||Number(parts[0])<Date.now()||Number(parts[0])>Date.now()+9*3600000)return false;return equal(parts[1],await signature(env.PUBLISH_SECRET,parts[0]))}
const PRODUCT_FEEDS=['https://nicheflip.github.io/daily-drops-deal-finder/data/amazon-deals.json','https://nicheflip.github.io/daily-drops-deal-finder/data/amazon-all-products.json'];
function communityImage(value){try{const u=new URL(String(value||''));if(u.protocol!=='https:'||u.username||u.password||u.href.length>1800||u.port)return '';const host=u.hostname.toLowerCase();if(host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host.endsWith('.internal')||/^(?:[0-9.]+|\[.*\])$/.test(host))return '';return u.href}catch{return ''}}
function officialImage(value){try{const u=new URL(String(value||''));return u.protocol==='https:'&&['m.media-amazon.com','images-na.ssl-images-amazon.com'].includes(u.hostname)?u.href:''}catch{return ''}}
async function findProductImage(asin,env){
 const existing=await env.DB.prepare('SELECT image_url FROM deals WHERE asin=?').bind(asin).first();
 const saved=officialImage(existing?.image_url);if(saved)return saved;
 for(const feed of PRODUCT_FEEDS){
  try{
   const response=await fetch(feed,{signal:AbortSignal.timeout(3500),headers:{'accept':'application/json'}});
   if(!response.ok)continue;
   const body=await response.json();
   const products=[...(Array.isArray(body.deals)?body.deals:[]),...(Array.isArray(body.products)?body.products:[])];
   const found=products.find(d=>d.asin===asin&&officialImage(d.imageUrl||d.image));
   if(found)return officialImage(found.imageUrl||found.image);
  }catch(e){console.warn('Product image lookup skipped',feed,e?.message)}
 }
 return '';
}
function originOK(request){return request.headers.get('origin')===new URL(request.url).origin}
const cors={'access-control-allow-origin':SHOP_ORIGIN,'vary':'Origin','access-control-allow-methods':'GET'};
const adminPage=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Daily Drops Publisher</title><style>body{font:16px system-ui;background:#faf8f5;color:#24201d;max-width:600px;margin:auto;padding:24px}h1{font-size:25px}section{background:white;border:1px solid #ddd7cf;border-radius:15px;padding:18px;margin:15px 0}label{display:block;margin:12px 0}input,select,button{box-sizing:border-box;font:inherit;padding:12px;border-radius:9px;width:100%;border:1px solid #b8afa5}button{background:#5b2333;color:white;border:0;font-weight:700;margin:7px 0}button.secondary{background:#f0e9e6;color:#33252b}.muted{color:#625c57;font-size:14px}#editor{display:none}</style><h1>Daily Drops Publisher</h1><p class="muted">Private owner publishing. Your secret stays on this Cloudflare address, never in the public GitHub site.</p><section id="login"><h2>Sign in</h2><label>Publishing secret<input id="secret" type="password" autocomplete="off"></label><button id="signin">Unlock publishing</button></section><section id="editor"><h2>Review deal</h2><label>Verified Amazon link or ASIN<input id="asin" placeholder="Paste Amazon /dp/ link or ASIN" autocomplete="off"></label><label>Product title<input id="title" maxlength="220"></label><label>Verified price ($)<input id="price" type="number" min=".01" step=".01"></label><label>Community lead photo URL (optional)<input id="imageUrl" type="url" placeholder="https://..."></label><div id="photoPreview" style="display:none"><img id="photo" alt="Community lead photo preview" style="width:140px;height:140px;object-fit:contain;background:#fff;border-radius:8px"><label><input id="confirmImage" type="checkbox" style="width:auto"> I verified this photo shows the exact Amazon product</label></div><p class="muted">Official Amazon scanner photos are preferred. If unavailable, you can confirm the original community lead photo matches the exact product.</p><label>Decision<select id="status"><option value="published">Publish to shop</option><option value="saved">Save for later</option><option value="pass">Pass / remove from shop</option></select></label><button id="save">Save decision</button><button class="secondary" id="logout">Sign out</button></section><p id="message" role="status"></p><script>
const el=id=>document.getElementById(id),params=new URLSearchParams(location.search);
for(const id of ['asin','title','price','imageUrl'])if(params.has(id))el(id).value=params.get(id).slice(0,id==='imageUrl'?1800:220);
const message=t=>el('message').textContent=t;
function previewPhoto(){const v=el('imageUrl').value.trim();let ok=false;try{const u=new URL(v);ok=u.protocol==='https:'}catch{}el('photoPreview').style.display=ok?'block':'none';el('confirmImage').checked=false;if(ok)el('photo').src=v;else el('photo').removeAttribute('src')}
el('imageUrl').addEventListener('input',previewPhoto);previewPhoto();
function extractAsin(value){const raw=String(value||'').trim().toUpperCase();if(/^[A-Z0-9]{10}$/.test(raw))return raw;try{const u=new URL(value);const segments=u.pathname.split('/').filter(Boolean);if(u.hostname==='link.amazon'&&segments.length===1&&/^[A-Z0-9]{10}$/i.test(segments[0]))return segments[0].toUpperCase();if(!['amazon.com','www.amazon.com','smile.amazon.com'].includes(u.hostname))return '';let index=segments.indexOf('dp');if(index>=0)return /^[A-Z0-9]{10}$/i.test(segments[index+1]||'')?segments[index+1].toUpperCase():'';index=segments.indexOf('gp');if(index>=0&&segments[index+1]==='product'&&/^[A-Z0-9]{10}$/i.test(segments[index+2]||''))return segments[index+2].toUpperCase()}catch{}return ''}

async function refresh(){const r=await fetch('/api/session',{credentials:'same-origin'});const j=await r.json();el('login').style.display=j.authenticated?'none':'block';el('editor').style.display=j.authenticated?'block':'none'}
el('signin').onclick=async()=>{const secret=el('secret').value;el('secret').value='';const r=await fetch('/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({secret})});message(r.ok?'Signed in. Review and publish.':'Sign-in failed.');await refresh()};
el('save').onclick=async()=>{const asin=extractAsin(el('asin').value),title=el('title').value.trim(),price=Number(el('price').value),status=el('status').value;if(!/^[A-Z0-9]{10}$/.test(asin)||!title||!(price>0)){message('Enter a valid ASIN, title, and verified price.');return}const r=await fetch('/api/deals',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({asin,title,price,status,imageUrl:el('imageUrl').value.trim(),imageConfirmed:el('confirmImage').checked})});const j=await r.json();message(r.ok?(j.imageFound?'Saved successfully with product photo.':'Saved. No exact Amazon product photo was found yet; this item will stay off the shop until one is available.'):(j.error||'Unable to save'))};
el('logout').onclick=async()=>{await fetch('/api/logout',{method:'POST'});await refresh();message('Signed out')};refresh();
<\/script></html>`;

// Community lead photo lookup: read only the og:image/twitter:image of allowed deal pages.
const OG_ALLOWED_HOSTS=['slickdeals.net'];
const ogHits=new Map();
function ogAllowed(value){try{const u=new URL(String(value||''));if(u.protocol!=='https:'||u.username||u.password||u.port||u.href.length>1800)return null;const host=u.hostname.toLowerCase();return OG_ALLOWED_HOSTS.some(h=>host===h||host.endsWith('.'+h))?u:null}catch{return null}}
function ogLimited(request){const ip=request.headers.get('cf-connecting-ip')||'unknown',now=Date.now(),hit=ogHits.get(ip);if(!hit||now-hit.start>60000){if(ogHits.size>5000)ogHits.clear();ogHits.set(ip,{start:now,count:1});return false}hit.count++;return hit.count>60}
function ogDecode(v){return String(v).replace(/&amp;/g,'&').replace(/&#x2F;/gi,'/').replace(/&#47;/g,'/').replace(/&quot;/g,'"').replace(/&#39;/g,"'")}
function ogExtract(html,base){for(const tag of html.match(/<meta\b[^>]*>/gi)||[]){const key=(tag.match(/\b(?:property|name)\s*=\s*["']([^"']+)["']/i)||[])[1];if(!key||!['og:image','og:image:secure_url','twitter:image','twitter:image:src'].includes(key.toLowerCase()))continue;const content=(tag.match(/\bcontent\s*=\s*["']([^"']+)["']/i)||[])[1];if(!content)continue;try{const img=communityImage(new URL(ogDecode(content.trim()),base).href);if(img)return img}catch{}}return ''}
async function ogLookup(request,u,ctx){
 const ogCors={...cors,'cache-control':'public, max-age=86400'};
 const target=ogAllowed(u.searchParams.get('url'));
 if(!target)return json({imageUrl:null,error:'URL not allowed'},400,cors);
 target.hash='';['utm_source','utm_content','utm_medium','utm_campaign'].forEach(k=>target.searchParams.delete(k));
 const cacheKey=new Request('https://og-cache.invalid/?u='+encodeURIComponent(target.href));
 const cache=globalThis.caches?.default;
 if(cache){const hit=await cache.match(cacheKey).catch(()=>null);if(hit)return hit}
 if(ogLimited(request))return json({imageUrl:null,error:'Too many requests'},429,{...cors,'retry-after':'60'});
 let imageUrl='';
 try{
  const r=await fetch(target.href,{redirect:'follow',signal:AbortSignal.timeout(5000),headers:{'accept':'text/html','user-agent':'Mozilla/5.0 (compatible; DailyDropsPublisher/1.0)'}});
  if(r.ok&&ogAllowed(r.url||target.href)&&String(r.headers.get('content-type')||'').includes('text/html')&&r.body){
   const reader=r.body.getReader(),decoder=new TextDecoder();let html='';
   while(html.length<400000){const {done,value}=await reader.read();if(done)break;html+=decoder.decode(value,{stream:true});if(/<\/head>/i.test(html))break}
   reader.cancel().catch(()=>{});
   imageUrl=ogExtract(html,r.url||target.href);
  }
 }catch{}
 const res=json({imageUrl:imageUrl||null},200,imageUrl?ogCors:{...cors,'cache-control':'public, max-age=3600'});
 if(cache&&ctx?.waitUntil)ctx.waitUntil(cache.put(cacheKey,res.clone()).catch(()=>{}));
 return res;
}
async function dispatchAmazonScan(env){
 const t=env.GH_DISPATCH_TOKEN;if(!t){console.log('Scan timer skipped: GH_DISPATCH_TOKEN not set');return}
 const api='https://api.github.com/repos/NicheFlip/daily-drops-deal-finder/actions',h={authorization:'Bearer '+t,accept:'application/vnd.github+json','user-agent':'daily-drops-scan-timer','x-github-api-version':'2022-11-28'};
 for(const st of ['in_progress','queued']){const r=await fetch(api+'/workflows/amazon-scan.yml/runs?per_page=1&status='+st,{headers:h,signal:AbortSignal.timeout(10000)});if(r.ok&&((await r.json()).total_count||0)>0){console.log('Scan timer skipped: a scan is already '+st);return}}
 const r=await fetch(api+'/workflows/amazon-scan.yml/dispatches',{method:'POST',headers:{...h,'content-type':'application/json'},body:JSON.stringify({ref:'main'}),signal:AbortSignal.timeout(10000)});
 console.log(r.status===204?'Scan timer started amazon-scan.yml':'Scan timer dispatch failed: HTTP '+r.status);
}
export default {async scheduled(event,env,ctx){ctx.waitUntil(dispatchAmazonScan(env).catch(e=>console.error('Scan timer error',e)))},
async fetch(request,env,ctx){
 try{
  const u=new URL(request.url),path=u.pathname;
  if(!env.DB||!env.PUBLISH_SECRET)return json({error:'Worker setup incomplete: DB and PUBLISH_SECRET required'},503);
  if(path==='/'&&request.method==='GET')return new Response(adminPage,{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','content-security-policy':"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",'referrer-policy':'no-referrer'}});
  if(path==='/api/deals'&&request.method==='GET'){
   const {results}=await env.DB.prepare("SELECT asin,title,price,affiliate_url AS url,image_url AS imageUrl,source,verified_at AS checkedAt FROM deals WHERE status='published' ORDER BY verified_at DESC LIMIT 500").all();
   return json({format:'daily-drops-publisher-v1',deals:results.map(x=>({...x,retailer:'Amazon',category:'Other',keyword:'Owner verified',discountPercent:0}))},200,cors);
  }
  if(path==='/api/catalog'&&request.method==='GET'){
   const {results}=await env.DB.prepare("SELECT asin,title,price,affiliate_url AS url,image_url AS imageUrl,source,status,verified_at AS checkedAt FROM deals ORDER BY updated_at DESC LIMIT 1000").all();
   return json({format:'daily-drops-publisher-v1',deals:results.map(x=>({...x,retailer:'Amazon',category:'Other',keyword:'Owner verified',discountPercent:0}))},200,cors);
  }
  if(path==='/api/og'&&request.method==='GET')return await ogLookup(request,u,ctx);
  if(path==='/api/health'&&request.method==='GET'){
   try{await env.DB.prepare('SELECT asin FROM deals LIMIT 1').first();return json({ok:true,database:'connected',version:'publisher-v2'},200,cors)}
   catch{return json({ok:false,database:'unavailable'},503,cors)}
  }
  if(path==='/api/session'&&request.method==='GET')return json({authenticated:await authorized(request,env)});
  if(path==='/api/login'&&request.method==='POST'){
   if(!originOK(request))return json({error:'Origin rejected'},403);
   const d=await request.json().catch(()=>({}));
   if(!equal(d.secret,env.PUBLISH_SECRET))return json({error:'Invalid credentials'},401);
   const expires=String(Date.now()+8*3600000),sig=await signature(env.PUBLISH_SECRET,expires);
   return json({ok:true},200,{'set-cookie':'dd_session='+expires+'.'+sig+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800'});
  }
  if(path==='/api/logout'&&request.method==='POST'){
   if(!originOK(request))return json({error:'Origin rejected'},403);
   return json({ok:true},200,{'set-cookie':'dd_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'});
  }
  if(path==='/api/deals'&&request.method==='POST'){
   if(!originOK(request)||!(await authorized(request,env)))return json({error:'Sign in on the private publisher page first'},403);
   const d=await request.json().catch(()=>({})),asin=String(d.asin||'').trim().toUpperCase(),title=String(d.title||'').trim(),price=Number(d.price),status=d.status;
   if(!/^[A-Z0-9]{10}$/.test(asin)||!title||title.length>220||!Number.isFinite(price)||price<=0||price>100000||!['published','saved','pass'].includes(status))return json({error:'Invalid product, price, or decision'},400);
   const now=new Date().toISOString(),url='https://www.amazon.com/dp/'+asin+'?tag='+AFFILIATE_TAG,official=await findProductImage(asin,env),imageUrl=official||(d.imageConfirmed===true?communityImage(d.imageUrl):'');
   await env.DB.prepare("INSERT INTO deals (asin,title,price,affiliate_url,image_url,source,status,verified_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(asin) DO UPDATE SET title=excluded.title,price=excluded.price,affiliate_url=excluded.affiliate_url,image_url=COALESCE(excluded.image_url,deals.image_url),status=excluded.status,verified_at=excluded.verified_at,updated_at=excluded.updated_at").bind(asin,title,Math.round(price*100)/100,url,imageUrl||null,'Owner verified community lead',status,now,now).run();
   return json({ok:true,asin,status,imageFound:!!imageUrl,imageSource:official?'Amazon scanner':imageUrl?'Verified community photo':'none'});
  }
  return json({error:'Not found'},404);
 }catch(e){console.error('Publisher error',e);return json({error:'Publisher temporarily unavailable'},500)}
}};
