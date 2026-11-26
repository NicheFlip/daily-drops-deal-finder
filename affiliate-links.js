// Shared Amazon / Walmart outgoing-link helpers for the dashboard and the follower shop.
// Amazon Associates tag is already in use across the project. Do not change it here
// without updating the Worker and the publisher as well.
const AFFILIATE_TAG='dealstoday0b3-20';

// Walmart / Impact deep links use:
//   https://goto.walmart.com/c/<AccountID>/<AdID>/<CampaignID>?u=<encoded walmart url>
// Official docs: https://help.impact.com/partner/.../create-a-deep-link-for-an-ad
// Leave these blank until Heather pastes the three IDs from an existing Walmart
// tracking link in Impact (see comments below). Never invent IDs — untagged
// Walmart URLs are returned unchanged when any ID is missing.
// Where to find them: sign in at impact.com → the Walmart program → Links / Create Link.
// Open (or create) a tracking link. The path is /c/{Account ID}/{Ad ID}/{Campaign ID}.
// Account ID is also shown on the Impact account/profile. Campaign ID is the Walmart
// campaign (sometimes called Program ID). Ad ID is the specific ad used for the link.
const WALMART_IMPACT={accountId:'',adId:'',campaignId:''};

function amazonAffiliateUrl(value,asinHint){
 const asin=/^[A-Z0-9]{10}$/i.test(String(asinHint||''))?String(asinHint).toUpperCase():'';
 const raw=String(value||'').trim();
 try{
  const u=new URL(raw);
  const host=u.hostname.toLowerCase();
  if(host==='link.amazon'||host==='amzn.to'||host==='a.co')return u.href;
  if(u.protocol!=='http:'&&u.protocol!=='https:')throw new Error('skip');
  if(/(^|\.)amazon\.com$/.test(host)){
   u.protocol='https:';
   u.searchParams.delete('tag');
   u.searchParams.set('tag',AFFILIATE_TAG);
   return u.toString();
  }
 }catch{}
 if(asin)return 'https://www.amazon.com/dp/'+encodeURIComponent(asin)+'?tag='+AFFILIATE_TAG;
 return raw;
}

function walmartAffiliateUrl(value){
 const raw=String(value||'').trim();
 try{
  const u=new URL(raw);
  if(u.protocol!=='http:'&&u.protocol!=='https:')return raw;
  const host=u.hostname.toLowerCase();
  if(host==='goto.walmart.com'||host.endsWith('.goto.walmart.com'))return u.href;
  if(!/(^|\.)walmart\.com$/.test(host))return raw;
  u.protocol='https:';
  const {accountId,adId,campaignId}=WALMART_IMPACT;
  if(!accountId||!adId||!campaignId)return u.href;
  return 'https://goto.walmart.com/c/'+encodeURIComponent(accountId)+'/'+encodeURIComponent(adId)+'/'+encodeURIComponent(campaignId)+'?u='+encodeURIComponent(u.href);
 }catch{}
 return raw;
}

function affiliateUrl(value,asinHint){
 const raw=String(value||'').trim();
 let host='';
 try{host=new URL(raw).hostname.toLowerCase()}catch{}
 if(!raw&&asinHint)return amazonAffiliateUrl('',asinHint);
 if(/(^|\.)amazon\.com$/.test(host)||host==='link.amazon'||host==='amzn.to'||host==='a.co')return amazonAffiliateUrl(raw,asinHint);
 if(/(^|\.)walmart\.com$/.test(host)||host==='goto.walmart.com')return walmartAffiliateUrl(raw);
 if(asinHint)return amazonAffiliateUrl(raw,asinHint);
 return raw;
}

function stampAffiliateAnchors(root){
 if(typeof document==='undefined')return;
 const box=root||document;
 box.querySelectorAll('a[href]').forEach(a=>{
  const href=a.getAttribute('href');if(!href||!/^https?:/i.test(href))return;
  const next=affiliateUrl(href);
  if(next&&next!==href)a.setAttribute('href',next);
 });
}

if(typeof document!=='undefined'){
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>stampAffiliateAnchors());
 else stampAffiliateAnchors();
}
if(typeof module!=='undefined'&&module.exports){
 module.exports={AFFILIATE_TAG,WALMART_IMPACT,amazonAffiliateUrl,walmartAffiliateUrl,affiliateUrl,stampAffiliateAnchors};
}
