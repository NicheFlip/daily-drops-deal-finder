"""Offline dry-run of the Amazon scanner with a mocked Creators API: budget, throttling retries and dedupe."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import amazon_scan
import candidate_queue
import price_history

class FakeApi:
    def __init__(self,throttle_first=0,items_per_page=10):
        self.calls=[]; self.throttle_first=throttle_first; self.items_per_page=items_per_page
    def __call__(self,url,payload,headers=None):
        self.calls.append((url,payload))
        if url.endswith('/token'):return {'access_token':'t'}
        if self.throttle_first>0:
            self.throttle_first-=1
            raise urllib.error.HTTPError(url,429,'Too Many Requests',{},io.BytesIO(b''))
        if url.endswith('searchItems'):
            # Overlapping results across searches: 6 shared-per-category ASINs + 4 search-specific ones.
            seed=abs(hash((payload['keywords'],payload['itemPage'])))%10**6
            asins=['B%09d'%(abs(hash(payload['searchIndex']))%1000*10+k) for k in range(6)]+['C%09d'%(seed*10+k) for k in range(4)]
            return {'searchResult':{'items':[self.item(a) for a in asins[:self.items_per_page]]}}
        return {'itemsResult':{'items':[self.item(a) for a in payload['itemIds']]}}
    @staticmethod
    def item(asin):
        return {'asin':asin,'itemInfo':{'title':{'displayValue':'Item '+asin}},
                'offersV2':{'listings':[{'condition':{'value':'New'},'price':{'money':{'amount':10},'savingBasis':{'money':{'amount':30}}}}]}}

class ScanBudgetChecks(unittest.TestCase):
    def run_scan(self,fake,budget=60,history=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            hist=root/'history.json'
            hist.write_text(json.dumps({'items':history or {}}))
            env={'AMAZON_CREATORS_CREDENTIAL_ID':'x','AMAZON_CREATORS_SECRET':'y','AMAZON_PARTNER_TAG':'z'}
            with patch.dict(os.environ,env),patch.object(amazon_scan,'api',fake),\
                 patch.object(amazon_scan,'PER_RUN',budget),patch.object(amazon_scan,'MIN_REQUEST_INTERVAL',0),\
                 patch.object(amazon_scan,'RETRY_DELAYS',(0,0,0)),\
                 patch.object(amazon_scan,'OUT',root/'deals.json'),patch.object(amazon_scan,'ALL_OUT',root/'all.json'),patch.object(amazon_scan,'USED_OUT',root/'used.json'),\
                 patch.object(amazon_scan,'STATE',root/'state.json'),patch.object(amazon_scan,'HISTORY_PATH',hist),\
                 patch.object(price_history,'PATH',hist),patch.object(price_history,'CHANGES',root/'changes.json'),\
                 patch.object(candidate_queue,'STATE',root/'cstate.json'),patch.object(candidate_queue,'QUEUE',root/'queue.json'),\
                 patch.object(candidate_queue,'ARCHIVE',root/'archive.json'):
                amazon_scan.scan()
                return json.loads((root/'deals.json').read_text()),json.loads((root/'state.json').read_text())

    def test_budget_is_never_exceeded(self):
        fake=FakeApi()
        out,state=self.run_scan(fake,budget=60)
        api_calls=[c for c in fake.calls if not c[0].endswith('/token')]
        self.assertLessEqual(len(api_calls),60)
        self.assertEqual(out['requestsAttempted'],len(api_calls))
        self.assertEqual(out['requestBudget'],60)
        self.assertEqual(state['callsToday'],len(api_calls))
        self.assertEqual(out['errors'],[])

    def test_searches_are_not_repeated_within_a_run(self):
        fake=FakeApi()
        self.run_scan(fake,budget=400)
        keys=[(p['searchIndex'],p['keywords'].lower(),p['itemPage']) for u,p in fake.calls if u.endswith('searchItems')]
        self.assertEqual(len(keys),len(set(keys)))

    def test_throttle_is_retried_and_counted(self):
        fake=FakeApi(throttle_first=2)
        out,_=self.run_scan(fake,budget=20)
        self.assertEqual(out['errors'],[])
        self.assertLessEqual(out['requestsAttempted'],20)
        self.assertEqual(out['requestsAttempted'],out['requestsCompleted']+2)

    def test_watched_asins_already_found_are_not_requested_again(self):
        found='B%09d'%(abs(hash('All'))%1000*10)
        history={found:{'title':'Watched thing','points':[[amazon_scan.STAMP,10]],'lastSeen':amazon_scan.STAMP},
                 'D000000001':{'title':'Other watched','points':[[amazon_scan.STAMP,10]],'lastSeen':amazon_scan.STAMP}}
        fake=FakeApi()
        out,_=self.run_scan(fake,budget=80,history=history)
        requested=[a for u,p in fake.calls if u.endswith('getItems') for a in p['itemIds']]
        self.assertNotIn(found,requested)
        self.assertIn('D000000001',requested)
        self.assertEqual(len(requested),len(set(requested)))

if __name__=='__main__':
    unittest.main()
