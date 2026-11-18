"""Used / open-box / Amazon Resale (Warehouse) offer parsing is additive and never changes new-item deals."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import amazon_scan

def listing(value,price,sub='Unknown',merchant='Amazon.com',stock='IN_STOCK',basis=None,note=''):
    p={'money':{'amount':price}}
    if basis:p['savingBasis']={'money':{'amount':basis}}
    return {'condition':{'value':value,'subCondition':sub,'conditionNote':note},'price':p,
            'availability':{'type':stock},'merchantInfo':{'name':merchant},'isBuyBoxWinner':value=='New'}

def item(*listings,asin='B000000001',title='Stand mixer'):
    return {'asin':asin,'itemInfo':{'title':{'displayValue':title}},'images':{'primary':{'medium':{'url':'https://m.media-amazon.com/x.jpg'}}},
            'offersV2':{'listings':list(listings)}}

class ConditionLabels(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(amazon_scan.condition_label('Used','LikeNew','Amazon Resale'),'Warehouse')
        self.assertEqual(amazon_scan.condition_label('Used','VeryGood','Amazon Warehouse'),'Warehouse')
        self.assertEqual(amazon_scan.condition_label('Used','OpenBox','Some Seller'),'Open Box')
        self.assertEqual(amazon_scan.condition_label('Refurbished','Refurbished','Seller'),'Renewed')
        self.assertEqual(amazon_scan.condition_label('Used','Good','Seller'),'Used')
        self.assertEqual(amazon_scan.condition_label('Collectible','Good','Seller'),'Used')
        self.assertIsNone(amazon_scan.condition_label('New','Unknown','Amazon.com'))
        self.assertIsNone(amazon_scan.condition_label('Unknown','Unknown','Seller'))

class ParseConditionOffer(unittest.TestCase):
    def test_warehouse_offer_with_savings_vs_new(self):
        d=amazon_scan.parse_condition_offer(item(listing('New',100,basis=120),listing('Used',62.5,'LikeNew','Amazon Resale',note='Box damaged')),'HomeAndKitchen','mixers')
        self.assertEqual(d['conditionLabel'],'Warehouse')
        self.assertEqual(d['price'],62.5)
        self.assertEqual(d['newPrice'],100)
        self.assertEqual(d['savingsVsNewPercent'],38)
        self.assertEqual(d['merchant'],'Amazon Resale')
        self.assertEqual(d['conditionNote'],'Box damaged')
        self.assertEqual(d['url'],'https://www.amazon.com/dp/B000000001')
        self.assertIn('not a new-item price',d['verification'])

    def test_used_only_listing_has_no_savings_claim(self):
        d=amazon_scan.parse_condition_offer(item(listing('Used',20,'Good','Seller',basis=80)),'All','x')
        self.assertEqual(d['conditionLabel'],'Used')
        self.assertIsNone(d['newPrice'])
        self.assertIsNone(d['savingsVsNewPercent'])

    def test_used_pricier_than_new_has_no_savings(self):
        d=amazon_scan.parse_condition_offer(item(listing('New',50),listing('Used',55,'OpenBox')),'All','x')
        self.assertEqual(d['conditionLabel'],'Open Box')
        self.assertIsNone(d['savingsVsNewPercent'])

    def test_ignores_new_only_out_of_stock_and_bad_items(self):
        self.assertIsNone(amazon_scan.parse_condition_offer(item(listing('New',50)),'All','x'))
        self.assertIsNone(amazon_scan.parse_condition_offer(item(listing('Used',5,stock='OUT_OF_STOCK')),'All','x'))
        self.assertIsNone(amazon_scan.parse_condition_offer(item(listing('Used',5),asin='bad'),'All','x'))
        self.assertIsNone(amazon_scan.parse_condition_offer(item(listing('Used',5),title='Wireless earbuds'),'All','x'))
        self.assertIsNone(amazon_scan.parse_condition_offer({'asin':'B000000001','itemInfo':{'title':{'displayValue':'x'}}},'All','x'))

    def test_new_item_parse_unchanged_by_used_listing(self):
        it=item(listing('Used',10,'Good'),listing('New',40,basis=100))
        d=amazon_scan.parse(it,'All','x')
        self.assertEqual(d['price'],40)
        self.assertEqual(d['discountPercent'],60)
        self.assertNotIn('conditionLabel',d)

class UsedFeed(unittest.TestCase):
    def test_merge_keeps_recent_and_sorts_by_savings(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'used.json'
            old={'asin':'B000000009','checkedAt':amazon_scan.STAMP,'savingsVsNewPercent':10,'merchant':'Amazon Resale'}
            stale={'asin':'B000000008','checkedAt':'2000-01-01T00:00:00+00:00','savingsVsNewPercent':90,'merchant':'Amazon Resale'}
            third={'asin':'B000000007','checkedAt':amazon_scan.STAMP,'savingsVsNewPercent':80,'merchant':'Some Seller'}
            out.write_text(json.dumps({'offers':[old,stale,third]}))
            with patch.object(amazon_scan,'USED_OUT',out):
                n=amazon_scan.write_used_offers({'B000000001':{'asin':'B000000001','checkedAt':amazon_scan.STAMP,'savingsVsNewPercent':40,'soldByAmazon':True}})
            j=json.loads(out.read_text())
            self.assertEqual(n,2)
            self.assertEqual([d['asin'] for d in j['offers']],['B000000001','B000000009'])
            self.assertEqual(j['foundThisScan'],1)
            self.assertEqual(j['excludedNotSoldByAmazon'],1)
            self.assertEqual(j['offers'][0]['firstSeenAt'],amazon_scan.STAMP)   # brand-new offer

    def test_first_seen_is_kept_across_scans(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'used.json'
            out.write_text(json.dumps({'offers':[{'asin':'B000000009','checkedAt':amazon_scan.STAMP,'firstSeenAt':'2026-11-12T00:00:00+00:00','merchant':'Amazon Resale'}]}))
            with patch.object(amazon_scan,'USED_OUT',out):
                amazon_scan.write_used_offers({'B000000009':{'asin':'B000000009','checkedAt':amazon_scan.STAMP,'soldByAmazon':True}})
            self.assertEqual(json.loads(out.read_text())['offers'][0]['firstSeenAt'],'2026-11-12T00:00:00+00:00')

    def test_previous_price_only_when_price_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'used.json'
            row=lambda p:{'asin':'B000000009','checkedAt':amazon_scan.STAMP,'price':p,'soldByAmazon':True}
            out.write_text(json.dumps({'offers':[{**row(30.0),'merchant':'Amazon Resale'}]}))
            with patch.object(amazon_scan,'USED_OUT',out):
                amazon_scan.write_used_offers({'B000000009':row(30.0)})
                self.assertNotIn('previousPrice',json.loads(out.read_text())['offers'][0])
                amazon_scan.write_used_offers({'B000000009':row(24.5)})
                self.assertEqual(json.loads(out.read_text())['offers'][0]['previousPrice'],30.0)
                amazon_scan.write_used_offers({'B000000009':row(24.5)})
                self.assertEqual(json.loads(out.read_text())['offers'][0]['previousPrice'],30.0)

if __name__=='__main__':unittest.main()
