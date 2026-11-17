"""Free shipping / Prime filter: only offers sold by Amazon reach the public feeds."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import amazon_scan

def listing(price,basis,merchant=None,mid=None,value='New',sub='Unknown',access=None):
    o={'condition':{'value':value,'subCondition':sub},'availability':{'type':'IN_STOCK'},
       'price':{'money':{'amount':price},'savingBasis':{'money':{'amount':basis}}}}
    if merchant or mid:o['merchantInfo']={k:v for k,v in (('name',merchant),('id',mid)) if v}
    if access:o['dealDetails']={'accessType':access,'badge':'With Prime'}
    return o
def item(*ls,asin='B000000001',title='Stand mixer'):
    return {'asin':asin,'itemInfo':{'title':{'displayValue':title}},'offersV2':{'listings':list(ls)}}

class ShippingInfo(unittest.TestCase):
    def test_amazon_sold_is_prime_free_shipping(self):
        for o in (listing(40,100,'Amazon.com'),listing(40,100,mid='ATVPDKIKX0DER'),listing(40,100,'Amazon Resale'),listing(40,100,'Amazon')):
            s=amazon_scan.shipping_info(o)
            self.assertTrue(s['soldByAmazon']);self.assertTrue(s['isPrime']);self.assertTrue(s['freeShipping']);self.assertEqual(s['shippingStatus'],'amazon')
    def test_third_party_and_lookalikes_not_verified(self):
        for name in ('Amazing Deals LLC','Amazon.com Seller Store','Best Buy Co','AmazonBasics Fan Shop'):
            s=amazon_scan.shipping_info(listing(40,100,name))
            self.assertFalse(s['soldByAmazon'],name);self.assertIsNone(s['freeShipping']);self.assertEqual(s['shippingStatus'],'third_party')
    def test_missing_merchant_is_unknown(self):
        s=amazon_scan.shipping_info(listing(40,100))
        self.assertEqual(s['shippingStatus'],'unknown');self.assertFalse(s['soldByAmazon'])
    def test_prime_only_deal_flag(self):
        s=amazon_scan.shipping_info(listing(40,100,'Amazon.com',access='PRIME_EXCLUSIVE'))
        self.assertTrue(s['primeOnlyDeal']);self.assertEqual(s['dealBadge'],'With Prime')

class ParseCarriesShipping(unittest.TestCase):
    def test_parse_math_unchanged_and_fields_added(self):
        d=amazon_scan.parse(item(listing(40,100,'Third Party Co')),'All','x')
        self.assertEqual((d['price'],d['referencePrice'],d['discountPercent']),(40,100,60))
        self.assertEqual(d['seller'],'Third Party Co');self.assertFalse(amazon_scan.ships_free(d))
        d=amazon_scan.parse(item(listing(40,100,'Amazon.com')),'All','x')
        self.assertTrue(amazon_scan.ships_free(d))
    def test_ships_free_legacy_rows(self):
        self.assertFalse(amazon_scan.ships_free({'asin':'B000000001','price':5}))
        self.assertTrue(amazon_scan.ships_free({'merchant':'Amazon Resale'}))
        self.assertFalse(amazon_scan.ships_free({'merchant':'Joe Seller'}))
    def test_used_offer_prefers_amazon_sold(self):
        d=amazon_scan.parse_condition_offer(item(listing(100,100,'Amazon.com'),listing(30,0,'Joe',value='Used',sub='Good'),listing(45,0,'Amazon Resale',value='Used',sub='LikeNew')),'All','x')
        self.assertEqual(d['merchant'],'Amazon Resale');self.assertEqual(d['price'],45);self.assertTrue(d['soldByAmazon'])
    def test_summary_counts(self):
        rows=[amazon_scan.parse(item(listing(40,100,m),asin='B00000000'+str(i)),'All','x') for i,m in enumerate(['Amazon.com','Joe',None])]
        s=amazon_scan.summarize_shipping(rows)
        self.assertEqual((s['kept'],s['excludedThirdParty'],s['excludedUnknownSeller']),(1,1,1))
        self.assertEqual(len(s['examplesExcluded']),2)

class ScanPublishesOnlyAmazonSold(unittest.TestCase):
    def test_feed_filter(self):
        items=[item(listing(40,100,'Amazon.com'),asin='B0000000A1',title='Mixer A'),
               item(listing(30,100,'Pricey Shipping Shop'),asin='B0000000A2',title='Mixer B'),
               item(listing(30,100),asin='B0000000A3',title='Mixer C')]
        def fake_api(url,payload,headers=None):
            if 'token' in url:return {'access_token':'t'}
            if 'searchItems' in url:return {'searchResult':{'items':items}}
            return {'itemsResult':{'items':[]}}
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            env={'AMAZON_CREATORS_CREDENTIAL_ID':'a','AMAZON_CREATORS_SECRET':'b','AMAZON_PARTNER_TAG':'c','AMAZON_SCAN_REQUEST_BUDGET':'3'}
            import price_history,candidate_queue
            with patch.dict('os.environ',env),patch.object(amazon_scan,'api',fake_api),patch.object(amazon_scan,'OUT',t/'d.json'),\
                 patch.object(amazon_scan,'ALL_OUT',t/'a.json'),patch.object(amazon_scan,'USED_OUT',t/'u.json'),patch.object(amazon_scan,'STATE',t/'s.json'),\
                 patch.object(amazon_scan,'HISTORY_PATH',t/'h.json'),patch.object(amazon_scan,'MIN_REQUEST_INTERVAL',0),\
                 patch.object(amazon_scan,'enrich',lambda *a,**k:0),patch.object(amazon_scan,'build_queue',lambda *a,**k:0),patch.object(amazon_scan,'PER_RUN',3):
                amazon_scan.scan()
            j=json.loads((t/'d.json').read_text())
            self.assertEqual([d['asin'] for d in j['deals']],['B0000000A1'])
            self.assertEqual(j['shippingFilter']['excludedThirdParty'],1)
            self.assertEqual(j['shippingFilter']['excludedUnknownSeller'],1)
            a=json.loads((t/'a.json').read_text())
            self.assertEqual(len(a['products']),3)  # full research feed keeps everything, with fields

if __name__=='__main__':unittest.main()
