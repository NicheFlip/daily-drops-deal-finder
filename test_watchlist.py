"""Watch list: data/watchlist.json is read safely, pinned items go first and the request budget is unchanged."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import amazon_scan
from test_amazon_scan_budget import FakeApi,ScanBudgetChecks

class LoadWatchlist(unittest.TestCase):
    def load(self,obj):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'w.json';p.write_text(obj if isinstance(obj,str) else json.dumps(obj))
            return amazon_scan.load_watchlist(p)
    def test_cleans_entries(self):
        a,k=self.load({'asins':['b0abc12345',' B0ABC12345 ','bad','<script>'],'keywords':['  Air   fryer ','air fryer','x','Lego']})
        self.assertEqual(a,['B0ABC12345']);self.assertEqual(k,['Air fryer','Lego'])
    def test_missing_or_broken_file_is_empty(self):
        self.assertEqual(amazon_scan.load_watchlist(Path('/nonexistent/w.json')),([],[]))
        self.assertEqual(self.load('{not json'),([],[]))
        self.assertEqual(self.load([1,2]),([],[]))
    def test_caps(self):
        a,k=self.load({'asins':['B%09d'%i for i in range(80)],'keywords':['kw%d'%i for i in range(20)]})
        self.assertEqual(len(a),amazon_scan.WATCH_MAX_ASINS);self.assertEqual(len(k),amazon_scan.WATCH_MAX_KEYWORDS)
    def test_match(self):
        d={'asin':'B000000001','title':'Ninja 4-Quart Air Fryer, Grey'}
        self.assertEqual(amazon_scan.watch_match(d,{'B000000001'},[]),'ASIN B000000001')
        self.assertEqual(amazon_scan.watch_match(d,set(),['fryer ninja']),'Keyword: fryer ninja')
        self.assertIsNone(amazon_scan.watch_match(d,set(),['instant pot']))

class PinnedScan(unittest.TestCase):
    run_scan=ScanBudgetChecks.run_scan
    def scan_with(self,watch,budget=40):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'watch.json';p.write_text(json.dumps(watch))
            fake=FakeApi()
            with patch.object(amazon_scan,'WATCHLIST',p):
                out,state=self.run_scan(fake,budget=budget)
            return fake,out
    def test_pinned_keywords_searched_first_within_budget(self):
        fake,out=self.scan_with({'asins':[],'keywords':['zebra lamp','otter mug']})
        calls=[c for c in fake.calls if not c[0].endswith('/token')]
        self.assertLessEqual(len(calls),40)
        self.assertEqual([c[1]['keywords'] for c in calls[:2]],['zebra lamp','otter mug'])
        self.assertEqual(out['watchlist']['keywords'],2)
    def test_pinned_asin_checked_and_tagged(self):
        fake,out=self.scan_with({'asins':['Z000000009'],'keywords':[]})
        calls=[c for c in fake.calls if not c[0].endswith('/token')]
        self.assertLessEqual(len(calls),40)
        gets=[c for c in calls if c[0].endswith('getItems')]
        self.assertTrue(gets and gets[0][1]['itemIds'][0]=='Z000000009')
        tagged=[d for d in out['deals'] if d['asin']=='Z000000009']
        self.assertTrue(tagged and tagged[0]['watched'])
        self.assertEqual(tagged[0]['watchReason'],'ASIN Z000000009')
