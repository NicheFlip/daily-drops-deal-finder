// Offline tests for the publisher Worker: posted deals, Telegram dedupe, captions, optional Facebook sync.
// Run: node --test cloudflare/worker.test.mjs   (needs Node 22.13+ for node:sqlite)
import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,writeFileSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const src=readFileSync(new URL('./daily-drops-publisher-worker.js',import.meta.url),'utf8')
 +'\nexport const __t={buildTelegramCaption,recordPosted,listPosted,syncFacebook,amazonRefs,amazonLink,asinFromUrl};';
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
 assert.equal(T.buildTelegramCaption({asin:'B0ABCDEF12',caption:'a <b> & c'}).split('\n')[0],'a &lt;b&gt; &amp; c');
 const built=T.buildTelegramCaption({asin:'B0ABCDEF12',title:'Lamp',price:5,prime:true});assert.ok(built.includes('tag=dealstoday0b3-20')&&built.includes('Prime'));
});
test('affiliate links always carry the tag',()=>{
 assert.equal(T.amazonLink('B0ABCDEF12','https://www.amazon.com/dp/B0ABCDEF12?tag=someoneelse-20'),'https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20');
 assert.equal(T.amazonLink('B0ABCDEF12','javascript:alert(1)'),'https://www.amazon.com/dp/B0ABCDEF12?tag=dealstoday0b3-20');
 assert.equal(T.amazonLink('B0ABCDEF12','https://link.amazon/abc'),'https://link.amazon/abc');
});
test('posted deal: saved for the shop, sent to Telegram once',async()=>{
 const log=[];globalThis.fetch=fakeFetch(log);const e=env(TG);
 const deal={asin:'B0SCAN0001',title:'Air Fryer',price:39.99,imageUrl:'https://m.media-amazon.com/images/I/x.jpg',prime:true,caption:'🔥 $39.99 Air Fryer\n👉 https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20'};
 const a=await T.recordPosted(e,deal);assert.equal(a.telegram.status,'sent');
 const b=await T.recordPosted(e,deal);assert.equal(b.telegram.status,'already_sent');
 assert.equal(log.filter(x=>x.url.includes('api.telegram.org')).length,1);
 const sent=log.find(x=>x.url.endsWith('/sendPhoto'));assert.equal(sent.body.chat_id,'@dailydrops');assert.equal(sent.body.parse_mode,'HTML');
 const rows=await T.listPosted(e);assert.equal(rows.length,1);assert.equal(rows[0].prime,true);assert.equal(rows[0].url,'https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20');
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
 const del=await worker.fetch(new Request('https://w.example/api/posted',{method:'DELETE',headers:{origin:'https://w.example',cookie,'content-type':'application/json'},body:'{"asin":"B0ABCDEF12"}'}),e,ctx);assert.equal(del.status,200);
 assert.equal((await T.listPosted(e)).length,0);
 const page=await worker.fetch(new Request('https://w.example/posted'),e,ctx);assert.equal(page.status,200);
});
test('Facebook sync: off without secrets; first run fills shop silently; later posts go to Telegram once',async()=>{
 const log=[];globalThis.fetch=fakeFetch(log);
 assert.equal((await T.syncFacebook(env(TG))).status,'not_configured');
 const e=env({...TG,FB_PAGE_ID:'1',FB_PAGE_TOKEN:'tok'});const now=new Date().toISOString();
 const first=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p1',created_time:now,message:'Deal! https://www.amazon.com/dp/B0SCAN0001?tag=dealstoday0b3-20'}]});
 assert.equal(first.added,1);assert.equal(first.sent,0);
 const second=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p1',created_time:now,message:'same'},{id:'p2',created_time:now,message:'🔥 $5.49 Cute mug set for coffee lovers\nhttps://amzn.to/xyz'}]});
 assert.equal(second.added,1);assert.equal(second.sent,1);
 const again=await T.syncFacebook(e,{fetchPosts:async()=>[{id:'p2',created_time:now,message:'x https://amzn.to/xyz'}]});assert.equal(again.added,0);
 const rows=await T.listPosted(e);const mug=rows.find(r=>r.asin==='B0SHORT001');assert.equal(mug.price,5.49);assert.equal(mug.url,'https://amzn.to/xyz');assert.equal(mug.source,'facebook');
 assert.deepEqual(T.amazonRefs('see https://www.amazon.com/dp/B0ABCDEF12. and https://example.com'),['https://www.amazon.com/dp/B0ABCDEF12']);
});
