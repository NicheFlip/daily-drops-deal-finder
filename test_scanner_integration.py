"""Offline checks for scanner parsing, image provenance and archive retention."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import amazon_scan
import candidate_queue

class ScannerChecks(unittest.TestCase):
    def test_amazon_image_and_price(self):
        item={'asin':'B012345678','itemInfo':{'title':{'displayValue':'Test kitchen item'}},
              'images':{'primary':{'medium':{'url':'https://m.media-amazon.com/images/I/example.jpg'}}},
              'offersV2':{'listings':[{'condition':{'value':'New'},
                'price':{'money':{'amount':12},'savingBasis':{'money':{'amount':40}}}}]}}
        deal=amazon_scan.parse(item,'HomeAndKitchen','kitchen')
        self.assertIsNotNone(deal)
        self.assertEqual(deal['imageUrl'],'https://m.media-amazon.com/images/I/example.jpg')
        self.assertEqual(deal['discountPercent'],70)
        self.assertIsNone(amazon_scan.parse({**item,'asin':'bad'},'HomeAndKitchen','kitchen'))
    def test_archive_keeps_older_discoveries_and_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(candidate_queue,'STATE',root/'state.json'),patch.object(candidate_queue,'QUEUE',root/'queue.json'),patch.object(candidate_queue,'ARCHIVE',root/'archive.json'):
                old={'asin':'B012345678','title':'Old find','url':'https://www.amazon.com/dp/B012345678','price':10,'reason':'First observation','checkedAt':'2025-01-01T00:00:00+00:00'}
                candidate_queue.ARCHIVE.write_text(json.dumps({'events':[old]}))
                stamp='2026-11-13T00:00:00+00:00'
                deal={'asin':'B000000001','title':'New find','url':'https://www.amazon.com/dp/B000000001','price':15,'referencePrice':50,'discountPercent':70,'category':'HomeAndKitchen','checkedAt':stamp,'imageUrl':'https://m.media-amazon.com/images/I/example.jpg'}
                candidate_queue.build_queue({'B000000001':deal},stamp)
                saved=json.loads(candidate_queue.ARCHIVE.read_text())['events']
                self.assertEqual(len(saved),2)
                self.assertEqual(saved[0]['imageUrl'],deal['imageUrl'])
                self.assertEqual(saved[1]['title'],'Old find')

if __name__=='__main__':
    unittest.main()
