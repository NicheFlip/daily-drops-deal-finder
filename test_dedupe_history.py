"""Duplicates, 'new deal' flags and price-history timelines."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import amazon_scan
import candidate_queue
import price_history

ASIN='B012345678'
def deal(price,stamp,asin=ASIN,title='Example stand mixer',**extra):
    return {'asin':asin,'title':title,'category':'Home','url':'https://www.amazon.com/dp/'+asin,
            'price':price,'referencePrice':100,'discountPercent':round(100-price),'checkedAt':stamp,**extra}

class Base(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
        for p in (patch.object(candidate_queue,'STATE',root/'s.json'),patch.object(candidate_queue,'QUEUE',root/'q.json'),
                  patch.object(candidate_queue,'ARCHIVE',root/'a.json'),patch.object(price_history,'PATH',root/'h.json'),
                  patch.object(price_history,'CHANGES',root/'c.json')):
            p.start();self.addCleanup(p.stop)
    def history(self):return json.loads(price_history.PATH.read_text())['items']
    def run_scan(self,price,stamp,baseline_only=False):
        d=deal(price,stamp)
        if baseline_only:price_history.enrich({},stamp,baseline={ASIN:d});return d
        price_history.enrich({ASIN:d},stamp);n=candidate_queue.build_queue({ASIN:d},stamp);return d,n

class CompactPoints(unittest.TestCase):
    def test_sorted_no_consecutive_duplicates_keeps_last_checked(self):
        raw=[['2026-11-14T00:00:00+00:00',10],['2026-11-12T00:00:00+00:00',10],['2026-11-13T00:00:00+00:00',10],
             ['2026-11-15T00:00:00+00:00',8],['2026-11-16T00:00:00+00:00',8],['2026-11-17T00:00:00+00:00',10],['bad',1],['2026-11-17T01:00:00+00:00',-1]]
        pts,last,n=price_history.compact_points(raw)
        self.assertEqual([c for _,c in pts],[1000,800,1000])
        self.assertEqual(pts[0][0],'2026-11-12T00:00:00+00:00')
        self.assertEqual(last,'2026-11-17T00:00:00+00:00');self.assertEqual(n,6)
    def test_summary_previous_is_last_different_price(self):
        pts=[('a',1000),('b',800),('c',900)]
        s=price_history.summarize(pts,900)
        self.assertEqual((s['low'],s['high'],s['previous']),(800,1000,('b',800)))

class NewFlagAndHistory(Base):
    def test_same_price_is_not_new_and_adds_no_point(self):
        d,n=self.run_scan(60,'2026-11-12T12:00:00+00:00')
        self.assertEqual(d['priceEvidence'],'first_observation');self.assertEqual(n,1)
        d,n=self.run_scan(60,'2026-11-13T12:00:00+00:00')
        self.assertEqual(d['priceEvidence'],'repeat_observation');self.assertEqual(n,0)
        h=self.history()[ASIN]
        self.assertEqual(len(h['points']),1);self.assertEqual(h['checks'],2);self.assertEqual(h['lastChecked'],'2026-11-13T12:00:00+00:00')
    def test_drop_is_new_with_previous_high_low(self):
        self.run_scan(60,'2026-11-12T12:00:00+00:00');self.run_scan(70,'2026-11-13T12:00:00+00:00')
        d,n=self.run_scan(50,'2026-11-14T12:00:00+00:00')
        self.assertEqual(n,1);self.assertEqual(d['priceEvidence'],'observed_reduction')
        self.assertEqual(d['priorObservedPrice'],70);self.assertEqual(d['previousDifferentPrice'],70)
        self.assertEqual((d['observedLow90d'],d['observedHigh90d']),(50,70));self.assertTrue(d['newObservedLow'])
        self.assertEqual([p[1] for p in self.history()[ASIN]['points']],[60,70,50])
        events=json.loads(candidate_queue.ARCHIVE.read_text())['events']
        self.assertEqual(sorted(e['reason'] for e in events),['First observation','Observed price drop'])
    def test_product_seen_before_as_non_deal_is_not_first_seen(self):
        self.run_scan(80,'2026-11-12T12:00:00+00:00',baseline_only=True)   # seen, not yet a deal
        d,n=self.run_scan(80,'2026-11-13T12:00:00+00:00')
        self.assertEqual(d['priceEvidence'],'repeat_observation');self.assertEqual(n,0)
        d,n=self.run_scan(55,'2026-11-14T12:00:00+00:00')
        self.assertEqual(n,1);self.assertEqual(d['priceEvidence'],'observed_reduction')
    def test_dirty_existing_history_is_cleaned(self):
        price_history.PATH.write_text(json.dumps({'items':{ASIN:{'title':'x','category':'Home','points':[
            ['2026-11-13T00:00:00+00:00',60],['2026-11-12T00:00:00+00:00',60],['2026-11-14T00:00:00+00:00',60],['2026-11-15T00:00:00+00:00',55]]}}}))
        d,_=self.run_scan(55,'2026-11-16T12:00:00+00:00')
        h=self.history()[ASIN]
        self.assertEqual(h['points'],[['2026-11-12T00:00:00+00:00',60],['2026-11-15T00:00:00+00:00',55]])
        self.assertEqual(h['checks'],5);self.assertEqual(d['previousDifferentPrice'],60);self.assertEqual(d['priceEvidence'],'repeat_observation')
    def test_capacity_evicts_least_recent(self):
        with patch.object(price_history,'MAX_ITEMS',2):
            for i,a in enumerate(['B000000001','B000000002','B000000003']):
                price_history.enrich({},'2026-11-1%dT00:00:00+00:00'%(2+i),baseline={a:deal(10,'x',asin=a)})
        self.assertEqual(sorted(self.history()),['B000000002','B000000003'])

class ArchiveDedupe(unittest.TestCase):
    def test_one_first_per_asin_and_only_lower_drops(self):
        ev=[{'asin':'A','reason':'First observation','price':10,'checkedAt':'1'},{'asin':'A','reason':'First observation','price':10,'checkedAt':'3'},
            {'asin':'A','reason':'Observed price drop','price':9,'checkedAt':'2'},{'asin':'A','reason':'Observed price drop','price':9,'checkedAt':'4'},
            {'asin':'B','reason':'First observation','price':5,'checkedAt':'2'}]
        out=candidate_queue.dedupe_events(ev)
        self.assertEqual([(e['asin'],e['reason'],e['checkedAt']) for e in out],[('B','First observation','2'),('A','Observed price drop','2'),('A','First observation','1')])

class OfferDedupe(unittest.TestCase):
    def test_asin_parent_and_title_groups(self):
        rows=[deal(30,'t',asin='B000000001',title='Mixer Pro 5 qt',seller='Joe',soldByAmazon=False,parentAsin='B0000000P1'),
              deal(35,'t',asin='B000000002',title='Mixer Pro 5 qt red',soldByAmazon=True,parentAsin='B0000000P1'),
              deal(20,'t',asin='B000000003',title='Silicone Spatula Set 5 pieces',soldByAmazon=True),
              deal(18,'t',asin='B000000004',title='Silicone spatula set - 5 pieces',soldByAmazon=True),
              deal(25,'t',asin='B000000003',title='Silicone Spatula Set 5 pieces',soldByAmazon=True)]
        out={d['asin']:d for d in amazon_scan.dedupe_offers(rows)}
        self.assertEqual(sorted(out),['B000000002','B000000004'])   # Amazon-sold variant kept; cheapest identical-title kept
    def test_parse_reads_parent_asin(self):
        item={'asin':'B000000001','parentASIN':'B0000000P1','itemInfo':{'title':{'displayValue':'Mixer'}},
              'offersV2':{'listings':[{'condition':{'value':'New'},'availability':{'type':'IN_STOCK'},'merchantInfo':{'name':'Amazon.com'},
              'price':{'money':{'amount':40},'savingBasis':{'money':{'amount':100}}}}]}}
        self.assertEqual(amazon_scan.parse(item,'All','x')['parentAsin'],'B0000000P1')

if __name__=='__main__':unittest.main()
