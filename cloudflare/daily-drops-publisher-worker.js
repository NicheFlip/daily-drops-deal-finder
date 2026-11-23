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
// ---- Posted deals: follower shop "Posted on Facebook" + Telegram -------------------------
// Heather marks a deal as posted (private /posted page, same sign-in) -> saved in D1 table
// posted_deals -> public GET /api/posted feeds the shop -> optional Telegram send (once per ASIN).
// Optional Facebook sync (cron) reads her Page's own posts only when FB_PAGE_ID and FB_PAGE_TOKEN
// are set. Every external call is skipped quietly when its secret is missing. Tokens are never
// returned, logged, or put in URLs that are logged.
const AMAZON_DISCLOSURE='As an Amazon Associate, I earn from qualifying purchases.';
const TELEGRAM_CAPTION_LIMIT=1024,TELEGRAM_TEXT_LIMIT=4096;
const GRAPH_VERSION='v27.0';
const CONDITIONS=['Used','Open Box','Warehouse','Renewed'];
const postedReady=new WeakSet();
async function ensurePostedTables(env){
 if(postedReady.has(env.DB))return;
 await env.DB.prepare("CREATE TABLE IF NOT EXISTS posted_deals (asin TEXT PRIMARY KEY, title TEXT NOT NULL, price REAL, link TEXT NOT NULL, image_url TEXT, condition_label TEXT, prime INTEGER NOT NULL DEFAULT 0, caption TEXT, source TEXT NOT NULL, fb_post_id TEXT, posted_at TEXT NOT NULL, telegram_status TEXT, telegram_message_id TEXT, telegram_sent_at TEXT, updated_at TEXT NOT NULL)").run();
 await env.DB.prepare("CREATE TABLE IF NOT EXISTS fb_seen_posts (post_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL)").run();
 postedReady.add(env.DB);
}
function amazonLink(asin,value){
 const canonical='https://www.amazon.com/dp/'+asin+'?tag='+AFFILIATE_TAG;
 try{const u=new URL(String(value||''));if(u.protocol!=='https:'||u.username||u.password||u.port)return canonical;
  if(u.hostname==='link.amazon'||u.hostname==='amzn.to')return u.href.slice(0,300);
  if(['www.amazon.com','amazon.com'].includes(u.hostname)){u.searchParams.set('tag',AFFILIATE_TAG);return u.href.slice(0,600)}
 }catch{}
 return canonical;
}
function asinFromUrl(value){try{const u=new URL(String(value||''));if(!/(^|\.)amazon\.com$/.test(u.hostname))return '';const m=u.pathname.match(/\/(?:dp|gp\/product|gp\/aw\/d)\/([A-Z0-9]{10})(?:[/?]|$)/i);return m?m[1].toUpperCase():''}catch{return ''}}
const htmlEscape=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
// Plain caption (Facebook text) -> Telegram HTML caption within Telegram's limit.
// Keeps the affiliate link and the Amazon disclosure; shortens the description first.
function buildTelegramCaption(d,limit=TELEGRAM_CAPTION_LIMIT){
 const link=d.link||('https://www.amazon.com/dp/'+d.asin+'?tag='+AFFILIATE_TAG);
 let text=String(d.caption||'').replace(/\r/g,'').trim();
 if(!text){const price=Number(d.price)>0?'🔥 $'+Number(d.price).toFixed(2):'🔥 Deal';text=[price+(d.conditionLabel?' · '+d.conditionLabel:''),'',String(d.title||'Amazon find').slice(0,200),d.prime?'✅ Sold by Amazon · free shipping with Prime':'','👉 '+link].filter((x,i)=>x||i===1).join('\n')}
 if(!text.includes(link)&&!/https:\/\/(?:link\.amazon|amzn\.to|(?:www\.)?amazon\.com)\//i.test(text))text+='\n\n👉 '+link;
 let lines=text.split('\n');
 if(!lines.some(l=>/as an amazon associate/i.test(l)))lines.push('',AMAZON_DISCLOSURE);
 const keep=l=>/https:\/\//.test(l)||/as an amazon associate/i.test(l);
 const fits=()=>lines.join('\n').length<=limit;
 if(!fits())lines=lines.filter(l=>!/^\s*(#\w+\s*)+$/.test(l));            // hashtags first
 if(!fits())lines=lines.filter(l=>!/prices change fast/i.test(l));
 while(!fits()){const i=lines.map((l,i)=>[l,i]).filter(([l])=>!keep(l)&&l.trim()).sort((a,b)=>b[0].length-a[0].length)[0];if(!i)break;const over=lines.join('\n').length-limit;const l=i[0];lines[i[1]]=l.length-over-1>20?l.slice(0,l.length-over-1).trimEnd()+'…':'';lines=lines.filter((x,j)=>x!==''||j===0||lines[j-1]!=='')}
 return htmlEscape(lines.join('\n').replace(/\n{3,}/g,'\n\n').slice(0,limit));
}
async function telegramCall(env,method,body){
 const r=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_BOT_TOKEN+'/'+method,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(12000)});
 let j={};try{j=await r.json()}catch{}
 return {ok:r.ok&&j.ok===true,id:j.result?.message_id,error:j.ok?'':String(j.description||('HTTP '+r.status)).slice(0,160)};
}
async function sendTelegramDeal(env,d){
 if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return {status:'not_configured'};
 const chat_id=String(env.TELEGRAM_CHAT_ID).trim();
 let res=null;
 if(d.imageUrl&&/^https:\/\//.test(d.imageUrl))res=await telegramCall(env,'sendPhoto',{chat_id,photo:d.imageUrl,caption:buildTelegramCaption(d),parse_mode:'HTML'});
 if(!res||!res.ok)res=await telegramCall(env,'sendMessage',{chat_id,text:buildTelegramCaption(d,TELEGRAM_TEXT_LIMIT),parse_mode:'HTML'});
 return res.ok?{status:'sent',messageId:String(res.id||'')}:{status:'failed',error:res.error};
}
function cleanPosted(d){
 const asin=String(d.asin||'').trim().toUpperCase();
 const title=String(d.title||'').replace(/\s+/g,' ').trim().slice(0,220);
 const price=Number(d.price);
 if(!/^[A-Z0-9]{10}$/.test(asin)||!title)return null;
 const conditionLabel=CONDITIONS.includes(d.conditionLabel)?d.conditionLabel:null;
 return {asin,title,price:Number.isFinite(price)&&price>0&&price<100000?Math.round(price*100)/100:null,link:amazonLink(asin,d.link),
  imageUrl:officialImage(d.imageUrl)||(d.imageConfirmed===true?communityImage(d.imageUrl):'')||communityImage(d.fbImage)||'',
  conditionLabel,prime:d.prime===true,caption:String(d.caption||'').slice(0,3000),source:d.source==='facebook'?'facebook':'dashboard',fbPostId:d.fbPostId?String(d.fbPostId).slice(0,80):null};
}
// Save one posted deal, then send it to Telegram once (claimed atomically so two taps can't double-send).
async function recordPosted(env,raw,{sendTelegram=true,resend=false}={}){
 await ensurePostedTables(env);
 const d=cleanPosted(raw);if(!d)return {error:'Invalid product'};
 if(!d.imageUrl)d.imageUrl=await findProductImage(d.asin,env).catch(()=>'')||'';
 const now=new Date().toISOString();
 await env.DB.prepare("INSERT INTO posted_deals (asin,title,price,link,image_url,condition_label,prime,caption,source,fb_post_id,posted_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(asin) DO UPDATE SET title=excluded.title,price=COALESCE(excluded.price,posted_deals.price),link=excluded.link,image_url=COALESCE(NULLIF(excluded.image_url,''),posted_deals.image_url),condition_label=excluded.condition_label,prime=excluded.prime,caption=excluded.caption,fb_post_id=COALESCE(excluded.fb_post_id,posted_deals.fb_post_id),posted_at=excluded.posted_at,updated_at=excluded.updated_at")
  .bind(d.asin,d.title,d.price,d.link,d.imageUrl||null,d.conditionLabel,d.prime?1:0,d.caption,d.source,d.fbPostId,now,now).run();
 let telegram={status:'skipped'};
 if(sendTelegram){
  if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)telegram={status:'not_configured'};
  else{
   const claim=await env.DB.prepare("UPDATE posted_deals SET telegram_status='sending' WHERE asin=? AND (telegram_status IS NULL OR telegram_status NOT IN ('sent','sending')"+(resend?" OR 1=1":"")+")").bind(d.asin).run();
   if(!(claim.meta&&claim.meta.changes===1))telegram={status:'already_sent'};
   else{
    telegram=await sendTelegramDeal(env,d).catch(e=>({status:'failed',error:String(e&&e.name||'error')}));
    await env.DB.prepare("UPDATE posted_deals SET telegram_status=?,telegram_message_id=?,telegram_sent_at=? WHERE asin=?").bind(telegram.status==='sent'?'sent':'failed',telegram.messageId||null,telegram.status==='sent'?new Date().toISOString():null,d.asin).run();
   }
  }
 }
 return {ok:true,asin:d.asin,imageFound:!!d.imageUrl,telegram};
}
async function listPosted(env,limit=60){
 await ensurePostedTables(env);
 const {results}=await env.DB.prepare("SELECT asin,title,price,link AS url,image_url AS imageUrl,condition_label AS conditionLabel,prime,source,posted_at AS postedAt,telegram_status AS telegramStatus FROM posted_deals ORDER BY posted_at DESC LIMIT ?").bind(limit).all();
 return results.map(r=>({...r,prime:!!r.prime,retailer:'Amazon'}));
}
// ---- Optional Facebook Page sync (cron). Needs FB_PAGE_ID + FB_PAGE_TOKEN; otherwise does nothing.
function amazonRefs(text){const refs=new Set();for(const m of String(text||'').matchAll(/https?:\/\/[^\s<>"')]+/g)){const u=m[0].replace(/[.,!?]+$/,'');if(/(^|\/\/)(?:www\.)?amazon\.com\//i.test(u)||/\/\/(?:amzn\.to|link\.amazon)\//i.test(u))refs.add(u)}return [...refs].slice(0,3)}
async function resolveAsin(url){
 const direct=asinFromUrl(url);if(direct)return direct;
 try{let next=url;for(let hop=0;hop<3;hop++){const r=await fetch(next,{method:'GET',redirect:'manual',signal:AbortSignal.timeout(6000)});const loc=r.headers.get('location');if(!loc)break;next=new URL(loc,next).href;const a=asinFromUrl(next);if(a)return a}}catch{}
 return '';
}
async function scannerProduct(asin){
 for(const feed of [...PRODUCT_FEEDS,'https://nicheflip.github.io/daily-drops-deal-finder/data/amazon-used-offers.json']){
  try{const r=await fetch(feed,{signal:AbortSignal.timeout(4000)});if(!r.ok)continue;const b=await r.json();
   const hit=[...(b.deals||[]),...(b.products||[]),...(b.offers||[])].find(x=>x&&x.asin===asin);if(hit)return hit}catch{}
 }
 return null;
}
function postTitle(message){const line=String(message||'').split('\n').map(l=>l.replace(/https?:\/\/\S+/g,'').replace(/[#@]\w+/g,'').trim()).find(l=>l.length>=12&&!/^(?:🔥|👉)?\s*\$?\d/.test(l));return (line||'').replace(/^[^\w$]+/,'').slice(0,200)}
async function syncFacebook(env,{fetchPosts}={}){
 if(!env.FB_PAGE_ID||!env.FB_PAGE_TOKEN)return {status:'not_configured'};
 await ensurePostedTables(env);
 let posts=[];
 if(fetchPosts)posts=await fetchPosts();
 else{
  const u='https://graph.facebook.com/'+GRAPH_VERSION+'/'+encodeURIComponent(String(env.FB_PAGE_ID).trim())+'/posts?fields=id,message,created_time,full_picture,is_published&limit=15';
  const r=await fetch(u,{headers:{authorization:'Bearer '+env.FB_PAGE_TOKEN},signal:AbortSignal.timeout(10000)});
  if(!r.ok){let msg='HTTP '+r.status;try{msg=String((await r.json()).error?.message||msg).slice(0,140)}catch{}console.log('Facebook sync skipped: '+msg);return {status:'error',error:msg}}
  posts=((await r.json()).data)||[];
 }
 const seenCount=(await env.DB.prepare('SELECT COUNT(*) AS n FROM fb_seen_posts').first())?.n||0;
 const firstRun=seenCount===0;   // first sync: add recent posts to the shop but don't flood Telegram
 let added=0,sent=0;
 for(const p of posts){
  if(!p||!p.id||p.is_published===false)continue;
  const fresh=await env.DB.prepare('INSERT OR IGNORE INTO fb_seen_posts (post_id,seen_at) VALUES (?,?)').bind(String(p.id),new Date().toISOString()).run();
  if(!(fresh.meta&&fresh.meta.changes===1))continue;
  if(Date.now()-Date.parse(p.created_time||0)>7*86400000)continue;
  for(const ref of amazonRefs(p.message)){
   const asin=await resolveAsin(ref);if(!asin)continue;
   const known=await env.DB.prepare('SELECT asin FROM posted_deals WHERE asin=?').bind(asin).first();if(known)continue;
   const s=await scannerProduct(asin)||{};
   const price=Number(s.price)||Number((String(p.message||'').match(/\$\s?(\d{1,5}(?:\.\d{2})?)/)||[])[1])||null;
   const res=await recordPosted(env,{asin,title:s.title||postTitle(p.message)||('Amazon find '+asin),price,link:ref.includes('amazon.com/')?'':ref,imageUrl:s.imageUrl,fbImage:p.full_picture,conditionLabel:s.conditionLabel,prime:s.soldByAmazon===true,caption:p.message,source:'facebook',fbPostId:p.id},{sendTelegram:!firstRun});
   if(res.ok){added++;if(res.telegram.status==='sent')sent++}
  }
 }
 return {status:'ok',added,sent,firstRun};
}
const postedPage=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Posted deals · Daily Drops</title><style>body{font:16px system-ui;background:#faf8f5;color:#24201d;max-width:640px;margin:auto;padding:20px}h1{font-size:24px;margin:8px 0}section{background:#fff;border:1px solid #ddd7cf;border-radius:15px;padding:16px;margin:14px 0}label{display:block;margin:10px 0}input,select,textarea,button{box-sizing:border-box;font:inherit;padding:12px;border-radius:9px;width:100%;border:1px solid #b8afa5}textarea{min-height:170px}button{background:#5b2333;color:#fff;border:0;font-weight:700;margin:6px 0;min-height:50px}button.secondary{background:#f0e9e6;color:#33252b}.muted{color:#625c57;font-size:14px}.row{display:flex;gap:10px;align-items:center}.row img{width:84px;height:84px;object-fit:contain;background:#fff;border-radius:8px;border:1px solid #eee}.ok{color:#12664a;font-weight:700}.warn{color:#9b3a31;font-weight:700}#editor,#list{display:none}.item{display:flex;gap:10px;align-items:center;border-top:1px solid #eee;padding:8px 0}.item img{width:48px;height:48px;object-fit:contain}.item button{width:auto;min-height:38px;padding:6px 12px}.check{display:flex;gap:8px;align-items:center}.check input{width:auto}</style>
<h1>📣 Posted on Facebook</h1><p class="muted">Tell the follower shop (and your Telegram channel) about a deal you just posted. Private page: your secret stays on this Cloudflare address.</p>
<section id="login"><h2>Sign in</h2><label>Publishing secret<input id="secret" type="password" autocomplete="off"></label><button id="signin">Unlock</button></section>
<section id="editor"><p id="integrations" class="muted"></p><div class="row"><img id="photo" alt=""><div><strong id="ptitle"></strong><div id="pmeta" class="muted"></div></div></div>
<label>Amazon link or ASIN<input id="asin" autocomplete="off"></label><label>Title<input id="title" maxlength="220"></label><label>Price ($)<input id="price" type="number" min=".01" step=".01"></label>
<label>Condition<select id="condition"><option value="">New</option><option>Used</option><option>Open Box</option><option>Warehouse</option><option>Renewed</option></select></label>
<label class="check"><input id="prime" type="checkbox"> Sold by Amazon (Prime · free shipping)</label>
<label>Caption for Telegram (same as your Facebook post)<textarea id="caption"></textarea></label>
<label class="check"><input id="sendTg" type="checkbox" checked> Also send to Telegram (only once per product)</label>
<button id="save">✓ Add to shop<span id="tgWord"> &amp; send to Telegram</span></button><p id="message" role="status" class="ok"></p></section>
<section id="list"><h2>Recently posted</h2><div id="items" class="muted">Loading…</div><button class="secondary" id="test">Send a Telegram test message</button><button class="secondary" id="logout">Sign out</button></section>
<script>
const el=id=>document.getElementById(id),params=new URLSearchParams(location.search);
for(const [k,id] of [['asin','asin'],['title','title'],['price','price'],['caption','caption']])if(params.has(k))el(id).value=params.get(k).slice(0,k==='caption'?3000:300);
if(params.get('condition'))el('condition').value=params.get('condition');el('prime').checked=params.get('prime')==='1';
const imageUrl=params.get('imageUrl')||'',link=params.get('link')||'';
function preview(){el('ptitle').textContent=el('title').value||'Product';el('pmeta').textContent=(el('price').value?'$'+Number(el('price').value).toFixed(2):'')+(el('condition').value?' · '+el('condition').value:'');if(/^https:/.test(imageUrl))el('photo').src=imageUrl;else el('photo').style.display='none'}
for(const id of ['title','price','condition'])el(id).addEventListener('input',preview);preview();
el('sendTg').addEventListener('change',()=>el('tgWord').style.display=el('sendTg').checked?'':'none');
function asinOf(v){v=String(v||'').trim();if(/^[A-Z0-9]{10}$/i.test(v))return v.toUpperCase();const m=v.match(/\\/(?:dp|gp\\/product|gp\\/aw\\/d)\\/([A-Z0-9]{10})/i);return m?m[1].toUpperCase():''}
const msg=(t,bad)=>{el('message').textContent=t;el('message').className=bad?'warn':'ok'};
async function refresh(){const j=await (await fetch('/api/session',{credentials:'same-origin'})).json();el('login').style.display=j.authenticated?'none':'block';for(const id of ['editor','list'])el(id).style.display=j.authenticated?'block':'none';if(j.authenticated){el('integrations').innerHTML='Telegram: '+(j.telegram?'<span class=ok>connected</span>':'<span class=warn>not set up yet (shop still updates)</span>')+' · Facebook auto-sync: '+(j.facebookSync?'<span class=ok>on</span>':'off');loadList()}}
async function loadList(){const j=await (await fetch('/api/posted',{cache:'no-store'})).json();el('items').innerHTML=(j.deals||[]).slice(0,20).map(d=>'<div class="item">'+(d.imageUrl?'<img src="'+d.imageUrl.replace(/"/g,'')+'" alt="">':'')+'<div style="flex:1"><div>'+String(d.title).replace(/</g,'&lt;').slice(0,70)+'</div><div class="muted">'+(d.price?'$'+Number(d.price).toFixed(2)+' · ':'')+new Date(d.postedAt).toLocaleDateString()+(d.telegramStatus==='sent'?' · sent to Telegram':'')+'</div></div><button class="secondary" data-remove="'+d.asin+'">Remove</button></div>').join('')||'Nothing posted yet.'}
el('signin').onclick=async()=>{const secret=el('secret').value;el('secret').value='';const r=await fetch('/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({secret})});msg(r.ok?'Signed in.':'Sign-in failed.',!r.ok);await refresh()};
el('save').onclick=async()=>{const asin=asinOf(el('asin').value);if(!asin||!el('title').value.trim()){msg('Add the Amazon link (or ASIN) and a title.',true);return}el('save').disabled=true;try{const r=await fetch('/api/posted',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({asin,title:el('title').value,price:Number(el('price').value)||null,imageUrl,imageConfirmed:!!imageUrl,link,conditionLabel:el('condition').value||null,prime:el('prime').checked,caption:el('caption').value,sendTelegram:el('sendTg').checked})});const j=await r.json();if(!r.ok){msg(j.error||'Could not save.',true);return}const t=j.telegram?.status;msg('✓ Added to the follower shop.'+(t==='sent'?' ✓ Sent to Telegram.':t==='already_sent'?' (Already sent to Telegram before, not sent again.)':t==='not_configured'?' Telegram is not set up yet.':t==='failed'?' Telegram send failed: '+(j.telegram.error||''):''),t==='failed');loadList()}finally{el('save').disabled=false}};
el('items').onclick=async e=>{const b=e.target.closest('[data-remove]');if(!b)return;await fetch('/api/posted',{method:'DELETE',headers:{'content-type':'application/json'},body:JSON.stringify({asin:b.dataset.remove})});loadList()};
el('test').onclick=async()=>{const r=await fetch('/api/telegram/test',{method:'POST'});const j=await r.json();msg(j.ok?'✓ Test message sent to Telegram.':'Telegram test failed: '+(j.error||'not set up'),!j.ok)};
el('logout').onclick=async()=>{await fetch('/api/logout',{method:'POST'});await refresh()};refresh();
<\/script></html>`;
export default {async scheduled(event,env,ctx){ctx.waitUntil(dispatchAmazonScan(env).catch(e=>console.error('Scan timer error',e)));ctx.waitUntil(syncFacebook(env).then(r=>{if(r.status!=='not_configured')console.log('Facebook sync',JSON.stringify(r))}).catch(e=>console.error('Facebook sync error',e&&e.name)))},
async fetch(request,env,ctx){
 try{
  const u=new URL(request.url),path=u.pathname;
  if(!env.DB||!env.PUBLISH_SECRET)return json({error:'Worker setup incomplete: DB and PUBLISH_SECRET required'},503);
  if(path==='/'&&request.method==='GET')return new Response(adminPage,{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','content-security-policy':"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src https: data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",'referrer-policy':'no-referrer'}});
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
  if(path==='/api/session'&&request.method==='GET'){const ok=await authorized(request,env);return json(ok?{authenticated:true,telegram:!!(env.TELEGRAM_BOT_TOKEN&&env.TELEGRAM_CHAT_ID),facebookSync:!!(env.FB_PAGE_ID&&env.FB_PAGE_TOKEN)}:{authenticated:false})}
  if(path==='/posted'&&request.method==='GET')return new Response(postedPage,{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','content-security-policy':"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src https: data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",'referrer-policy':'no-referrer'}});
  if(path==='/api/posted'&&request.method==='GET')return json({format:'daily-drops-posted-v1',deals:await listPosted(env)},200,cors);
  if(path==='/api/posted'&&(request.method==='POST'||request.method==='DELETE')){
   if(!originOK(request)||!(await authorized(request,env)))return json({error:'Sign in on the private Posted page first'},403);
   const d=await request.json().catch(()=>({}));
   if(request.method==='DELETE'){const asin=String(d.asin||'').toUpperCase();if(!/^[A-Z0-9]{10}$/.test(asin))return json({error:'Invalid ASIN'},400);await ensurePostedTables(env);await env.DB.prepare('DELETE FROM posted_deals WHERE asin=?').bind(asin).run();return json({ok:true,asin,removed:true})}
   const res=await recordPosted(env,{...d,source:'dashboard'},{sendTelegram:d.sendTelegram!==false,resend:d.resend===true});
   return res.error?json({error:res.error},400):json(res);
  }
  if(path==='/api/telegram/test'&&request.method==='POST'){
   if(!originOK(request)||!(await authorized(request,env)))return json({error:'Sign in first'},403);
   if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return json({ok:false,error:'TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set yet'});
   const r=await telegramCall(env,'sendMessage',{chat_id:String(env.TELEGRAM_CHAT_ID).trim(),text:'✅ Daily Drops with Heather is connected. New deals will appear here.'}).catch(e=>({ok:false,error:String(e&&e.name)}));
   return json({ok:r.ok,error:r.ok?undefined:r.error});
  }
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
