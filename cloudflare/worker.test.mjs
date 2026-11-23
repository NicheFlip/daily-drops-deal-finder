// Offline tests for the publisher Worker: posted deals, Telegram dedupe, captions, optional Facebook sync.
// Run: node --test cloudflare/worker.test.mjs   (needs Node 22.13+ for node:sqlite)
import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,writeFileSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const src=readFileSync(new URL('./daily-drops-publisher-worker.js',import.meta.url),'utf8')
 +'\nexport const __t={buildTelegramCaption,recordPosted,listPosted,syncFacebook,postLinks,postCoupon,postTitle,amazonLink,asinFromUrl,dealIdentity,dealHashtags};';
const file=join(mkdtempSync(join(tmpdir(),'ddw-')),'worker.mjs');writeFileSync(file,src);
const mod=await import(file);const worker=mod.default,T=mod.__t;

function d1(){const db=new DatabaseSync(':memory:');
 db.exec("CREATE TABLE deals (asin TEXT PRIMARY KEY,title TEXT,price REAL,affiliate_url TEXT,image_url TEXT,source TEXT,status TEXT,verified_at TEXT,updated_at TEXT)");
 const stmt=(sql,args=[])=>({bind:(...a)=>stmt(sql,a),run:async()=>{const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}}},first:async()=>db.prepare(sql).get(...args)??null,all:async()=>({results:db.prepare(sql).all(...args)})});
 return {prepare:sql=>stmt(sql),raw:db};}
function fakeFetch(log,{tgOk=true,photoOk=true}={}){return async(url,opt={})=>{url=String(url);log.push({url,body:opt.body?JSON.parse(opt.body):null});
 if(url.startsWith('https://api.telegram.org/')){const method=url.split('/').pop();const ok=tgOk&&(method!=='sendPhoto'||photoOk);return new Response(JSON.stringify(ok?{ok:true,result:{message_id:log.length}}:{ok:false,description:'Bad Request: wrong photo'}),{status:ok?200:400})}
 if(url.includes('nicheflip.github.io'))return new Response(JSON.stringify({deals:[{asin:'B0SCAN0001',title:'Scanner Air Fryer',price:39.99,imageUrl:'https://m.media-amazon.com/images/I/x.jpg',soldByAmazon:true}]}),{status:200});
 if(url.startsWith('https://amzn.to/'))return new Response('',{status:301,headers:{location:'https://www.amazon.com/dp/B0SHORT001?tag=dealstoday0b3-20'}});
 return new Response('{}',{status:404})}}
const env=(extra={})=>({DB:d1(),PUBLISH_SECRET:'s3cret',...extra});
const TG={TELEGRAM_BOT_TOKEN:'123:ABC',TELEGRAM_CHAT_ID:'@dailydrops'};

test('caption keeps link + disclosure and fits Telegram limit',()=>{
 const long='🔥 $9.99\n\n'+'Very long product description '.repeat(80)+'\n\n👉 https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20\n\n#DailyDropsWithHeather #AmazonFinds';
 const c=T.buildTelegramCaption({asin:'B0ABCDEF12',caption:long});
 const plain=c.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
 assert.ok(plain.length<=1024);assert.ok(plain.includes('https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20'));
 assert.ok(plain.includes('As an Amazon Associate, I earn from qualifying purchases.'));
 assert.ok(!plain.includes('#AmazonFinds'));
 const coup=T.buildTelegramCaption({asin:'B0ABCDEF12',title:'Lamp',price:5,couponCode:'SAVE20'});assert.ok(coup.includes('Use code SAVE20'));
 const wm=T.buildTelegramCaption({store:'Walmart',url:'https://www.walmart.com/ip/x/123456',title:'Bike',price:99});assert.ok(wm.includes('earn a commission')&&!wm.includes('Amazon Associate')&&wm.includes('#WalmartDeals'));
 assert.ok(!T.buildTelegramCaption({asin:'B0ABCDEF12',caption:'x\n#DailyDropsWithHeather #AmazonDeals'}).includes('DailyDropsWithHeather'));
 assert.equal(T.buildTelegramCaption({asin:'B0ABCDEF12',caption:'a <b> & c'}).split('\n')[0],'a &lt;b&gt; &amp; c');
 const built=T.buildTelegramCaption({asin:'B0ABCDEF12',title:'Lamp',price:5,prime:true});assert.ok(built.includes('tag=dealstoday0b3-20')&&built.includes('Prime'));
});
test('affiliate links always carry the tag',()=>{
 assert.equal(T.amazonLink('B0ABCDEF12','https://www.amazon.com/dp/B0ABCDEF12?tag=someoneelse-20'),'https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20');
 assert.equal(T.amazonLink('B0ABCDEF12','javascript:alert(1)'),'https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20');
 assert.equal(T.amazonLink('B0ABCDEF12','https://link.amazon/abc'),'https://link.amazon/abc');
});
test('identity: one id per product across stores, links pass through',()=>{
 assert.deepEqual(T.dealIdentity('https://www.amazon.com/Some/dp/B0ABCDEF12/ref=x?th=1'),{id:'B0ABCDEF12',asin:'B0ABCDEF12',store:'Amazon',url:'https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20'});
 const w1=T.dealIdentity('https://www.walmart.com/ip/Kids-Bike/1234567?athcpid=1'),w2=T.dealIdentity('https://goto.walmart.com/c/1/2/3?u='+encodeURIComponent('https://www.walmart.com/ip/Kids-Bike/1234567'));
 assert.equal(w1.id,'wm:1234567');assert.equal(w2.id,'wm:1234567');assert.equal(w2.store,'Walmart');assert.ok(w2.url.startsWith('https://goto.walmart.com/'));
 const t=T.dealIdentity('https://www.target.com/p/lamp/-/A-123?ref=fb');assert.equal(t.store,'Target');assert.equal(t.url,'https://www.target.com/p/lamp/-/A-123?ref=fb');
 assert.equal(T.dealIdentity('http://evil.example/x'),null);assert.equal(T.dealIdentity('https://127.0.0.1/x'),null);
});
test('hashtags: relevant, max 5, deterministic, never the old page tag',()=>{
 const a=T.dealHashtags({asin:'B0ABCDEF12',title:'Ninja Air Fryer 4qt',price:50,referencePrice:120,couponCode:'SAVE10'});
 assert.deepEqual(a,['#AmazonDeals','#KitchenDeals','#CouponCode','#Clearance','#DealFinds']);
 assert.deepEqual(T.dealHashtags({asin:'B0ABCDEF12',title:'Ninja Air Fryer 4qt',price:50,referencePrice:120,couponCode:'SAVE10'}),a);
 const w=T.dealHashtags({url:'https://www.walmart.com/ip/1234567',title:'LEGO Star Wars set',price:20,previousPrice:30});assert.deepEqual(w.slice(0,3),['#WalmartDeals','#ToyDeals','#PriceDrop']);
 for(const x of [a,w,T.dealHashtags({}),T.dealHashtags({title:'Warehouse mixer',conditionLabel:'Warehouse',asin:'B0ABCDEF12'})]){assert.ok(x.length<=5);assert.equal(new Set(x).size,x.length);assert.ok(!x.includes('#DailyDropsWithHeather'))}
});
test('posted deal: saved for the shop, sent to Telegram once',async()=>{
 const log=[];globalThis.fetch=fakeFetch(log);const e=env(TG);
 const deal={asin:'B0SCAN0001',title:'Air Fryer',price:39.99,imageUrl:'https://m.media-amazon.com/images/I/x.jpg',prime:true,caption:'🔥 $39.99 Air Fryer\n👉 https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20'};
 const a=await T.recordPosted(e,deal);assert.equal(a.telegram.status,'sent');
 const b=await T.recordPosted(e,deal);assert.equal(b.telegram.status,'already_sent');
 assert.equal(log.filter(x=>x.url.includes('api.telegram.org')).length,1);
 const sent=log.find(x=>x.url.endsWith('/sendPhoto'));assert.equal(sent.body.chat_id,'@dailydrops');assert.equal(sent.body.parse_mode,'HTML');
 const rows=await T.listPosted(e);assert.equal(rows.length,1);assert.equal(rows[0].prime,true);assert.equal(rows[0].id,'B0SCAN0001');assert.equal(rows[0].url,'https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20');
 assert.ok(!JSON.stringify(rows).includes('123:ABC'));
});
test('photo rejected -> falls back to a text message; no secrets -> shop only',async()=>{
 const log=[];globalThis.fetch=fakeFetch(log,{photoOk:false});
 const r=await T.recordPosted(env(TG),{asin:'B0USED0001',title:'Mixer',price:20,imageUrl:'https://m.media-amazon.com/i.jpg',conditionLabel:'Warehouse'});
 assert.equal(r.telegram.status,'sent');assert.ok(log.some(x=>x.url.endsWith('/sendMessage')));
 const log2=[];globalThis.fetch=fakeFetch(log2);const e=env();
 const s=await T.recordPosted(e,{asin:'B0NOTG0001',title:'Lamp',price:9});assert.equal(s.telegram.status,'not_configured');
 assert.equal(log2.filter(x=>x.url.includes('telegram')).length,0);assert.equal((await T.listPosted(e)).length,1);
});
test('HTTP API: public list with CORS, writes need sign-in',async()=>{
 globalThis.fetch=fakeFetch([]);const e=env();const ctx={waitUntil(){}};
 const denied=await worker.fetch(new Request('https://w.example/api/posted',{method:'POST',headers:{origin:'https://w.example','content-type':'application/json'},body:'{"asin":"B0ABCDEF12","title":"x"}'}),e,ctx);assert.equal(denied.status,403);
 const login=await worker.fetch(new Request('https://w.example/api/login',{method:'POST',headers:{origin:'https://w.example','content-type':'application/json'},body:JSON.stringify({secret:'s3cret'})}),e,ctx);
 const cookie=login.headers.get('set-cookie').split(';')[0];
 const ok=await worker.fetch(new Request('https://w.example/api/posted',{method:'POST',headers:{origin:'https://w.example',cookie,'content-type':'application/json'},body:JSON.stringify({asin:'B0ABCDEF12',title:'Desk Lamp',price:12.5})}),e,ctx);
 assert.equal(ok.status,200);assert.equal((await ok.json()).telegram.status,'not_configured');
 const list=await worker.fetch(new Request('https://w.example/api/posted'),e,ctx);assert.equal(list.headers.get('access-control-allow-origin'),'https://nicheflip.github.io');
 assert.equal((await list.json()).deals[0].asin,'B0ABCDEF12');
 const del=await worker.fetch(new Request('https://w.example/api/posted',{method:'DELETE',headers:{origin:'https://w.example',cookie,'content-type':'application/json'},body:'{"id":"B0ABCDEF12"}'}),e,ctx);assert.equal(del.status,200);
 const other=await worker.fetch(new Request('https://w.example/api/posted',{method:'POST',headers:{origin:'https://w.example',cookie,'content-type':'application/json'},body:JSON.stringify({link:'https://www.target.com/p/lamp/-/A-123',title:'Target lamp',price:15,couponCode:' save 5 '})}),e,ctx);
 assert.equal(other.status,200);const tl=(await T.listPosted(e))[0];assert.equal(tl.store,'Target');assert.equal(tl.url,'https://www.target.com/p/lamp/-/A-123');assert.equal(tl.couponCode,'SAVE5');
 await worker.fetch(new Request('https://w.example/api/posted',{method:'DELETE',headers:{origin:'https://w.example',cookie,'content-type':'application/json'},body:JSON.stringify({id:tl.id})}),e,ctx);
 assert.equal((await T.listPosted(e)).length,0);
 const page=await worker.fetch(new Request('https://w.example/posted'),e,ctx);assert.equal(page.status,200);
});
test('Facebook sync: off without secrets; first run fills shop silently; later posts go to Telegram once',async()=>{
 const log=[];globalThis.fetch=fakeFetch(log);
 assert.equal((await T.syncFacebook(env(TG))).status,'not_configured');
 const e=env({...TG,FB_PAGE_ID:'1',FB_PAGE_TOKEN:'tok'});const now=new Date().toISOString();
 await T.recordPosted(e,{asin:'B0SCAN0001',title:'Air Fryer',price:39.99},{sendTelegram:false});   // already added from the dashboard
 const first=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p1',created_time:now,message:'Deal! https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20'},{id:'p0',created_time:now,message:'🔥 $12.99 Cozy throw blanket\nUse code COZY15\nhttps://www.target.com/p/throw/-/A-999',full_picture:'https://scontent.xx.fbcdn.net/p.jpg'}]});
 assert.equal(first.added,1);assert.equal(first.sent,0);
 const tgt=(await T.listPosted(e)).find(r=>r.store==='Target');assert.equal(tgt.couponCode,'COZY15');assert.equal(tgt.price,12.99);assert.equal(tgt.title,'Cozy throw blanket');assert.equal(tgt.imageUrl,'https://scontent.xx.fbcdn.net/p.jpg');
 const second=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p1',created_time:now,message:'same'},{id:'p2',created_time:now,message:'🔥 $5.49 Cute mug set for coffee lovers\nhttps://amzn.to/xyz'}]});
 assert.equal(second.added,1);assert.equal(second.sent,1);
 const again=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p2',created_time:now,message:'x https://amzn.to/xyz'}]});assert.equal(again.added,0);
 const rows=await T.listPosted(e);const mug=rows.find(r=>r.asin==='B0SHORT001');assert.equal(mug.price,5.49);assert.equal(mug.url,'https://amzn.to/xyz');assert.equal(mug.source,'facebook');
 assert.deepEqual(T.postLinks('see https://www.amazon.com/dp/B0ABCDEF12. and https://facebook.com/x https://example.com'),['https://www.amazon.com/dp/B0ABCDEF12','https://example.com']);
 assert.equal(T.postCoupon('Use promo code: SPRING25 at checkout'),'SPRING25');assert.equal(T.postCoupon('no code here'),'');
});
