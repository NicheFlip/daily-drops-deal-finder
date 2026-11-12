"""Offline regression tests for the free deal-intelligence engine."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import candidate_queue
import price_history

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.patches=[
            patch.object(candidate_queue,'STATE',root/'candidate-state.json'),
            patch.object(candidate_queue,'QUEUE',root/'candidates.json'),
            patch.object(price_history,'PATH',root/'history.json'),
            patch.object(price_history,'CHANGES',root/'changes.json'),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.stamp='2026-11-12T12:00:00+00:00'

    def deal(self, price):
        return {'asin':'B012345678','title':'Example product','category':'Home',
                'url':'https://www.amazon.com/dp/B012345678',
                'price':price,'referencePrice':100,'discountPercent':round(100-price),
                'checkedAt':self.stamp}

    def test_queue_deduplicates_and_detects_reduction(self):
        first=self.deal(60)
        price_history.enrich({'B012345678':first},self.stamp)
        self.assertEqual(candidate_queue.build_queue({'B012345678':first},self.stamp),1)
        self.assertEqual(candidate_queue.build_queue({'B012345678':first},self.stamp),0)
        reduced=self.deal(45)
        price_history.enrich({'B012345678':reduced},self.stamp)
        self.assertEqual(candidate_queue.build_queue({'B012345678':reduced},self.stamp),1)
        queued=json.loads(candidate_queue.QUEUE.read_text())['candidates']
        self.assertEqual(queued[0]['reason'],'Observed price drop')
        self.assertEqual(queued[0]['previousObservedPrice'],60)
        self.assertTrue(reduced['newObservedLow'])

    def test_history_keeps_observations_and_ignores_unchanged(self):
        first=self.deal(60)
        price_history.enrich({'B012345678':first},self.stamp)
        same=self.deal(60)
        price_history.enrich({'B012345678':same},self.stamp)
        self.assertEqual(same['observationCount'],1)
        self.assertFalse(same['newObservedLow'])
        next_day='2026-11-13T12:00:00+00:00'
        later=self.deal(60)
        price_history.enrich({'B012345678':later},next_day)
        self.assertEqual(later['observationCount'],2)

if __name__=='__main__':
    unittest.main()
