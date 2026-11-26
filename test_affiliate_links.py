"""Shared Amazon/Walmart affiliate link helper: tag every Amazon URL; wrap Walmart only when Impact IDs are set."""
import json, pathlib, re, shutil, subprocess, unittest

ROOT = pathlib.Path(__file__).parent
HELPER = ROOT / 'affiliate-links.js'
INDEX = (ROOT / 'index.html').read_text()
SHOP = (ROOT / 'shop.html').read_text()
WORKER = (ROOT / 'cloudflare' / 'daily-drops-publisher-worker.js').read_text()

@unittest.skipUnless(HELPER.is_file() and shutil.which('node'), 'node or helper missing')
class AffiliateHelper(unittest.TestCase):
    def run_js(self, body):
        code = "const h=require('./affiliate-links.js');\n" + body
        out = subprocess.run(['node', '-e', code], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_amazon_search_and_product_always_tagged(self):
        r = self.run_js(r"""
const {amazonAffiliateUrl,AFFILIATE_TAG}=h;
const cases=[
 amazonAffiliateUrl('https://www.amazon.com/s?k=toys'),
 amazonAffiliateUrl('https://www.amazon.com/s?k=toys&tag=other-20'),
 amazonAffiliateUrl('https://www.amazon.com/deals'),
 amazonAffiliateUrl('https://www.amazon.com/outlet'),
 amazonAffiliateUrl('https://www.amazon.com/coupons'),
 amazonAffiliateUrl('https://www.amazon.com/amazonwarehouse'),
 amazonAffiliateUrl('https://amazon.com/dp/B0ABCDEF12'),
 amazonAffiliateUrl('https://www.amazon.com/dp/B0ABCDEF12?tag=other-20&th=1'),
 amazonAffiliateUrl('','B0ABCDEF12'),
 amazonAffiliateUrl('http://www.amazon.com/s?k=x')
];
const short=amazonAffiliateUrl('https://link.amazon/abc');
const counts=cases.map(u=>(u.match(/[?&]tag=/g)||[]).length);
console.log(JSON.stringify({cases,tag:AFFILIATE_TAG,short,counts,allTagged:cases.every(u=>u.includes('tag='+AFFILIATE_TAG)&&!u.includes('other-20'))}));
""")
        self.assertEqual(r['tag'], 'dealstoday0b3-20')
        self.assertTrue(r['allTagged'], r['cases'])
        self.assertEqual(r['counts'], [1]*len(r['cases']))
        self.assertEqual(r['short'], 'https://link.amazon/abc')
        self.assertTrue(r['cases'][2].startswith('https://www.amazon.com/deals'))
        self.assertIn('th=1', r['cases'][7])

    def test_walmart_unchanged_without_ids_and_wraps_when_set(self):
        r = self.run_js(r"""
const {walmartAffiliateUrl,affiliateUrl,WALMART_IMPACT}=h;
const search='https://www.walmart.com/search?q=clearance';
const product='https://www.walmart.com/ip/Kids-Bike/1234567';
const deals='https://www.walmart.com/shop/deals';
const already='https://goto.walmart.com/c/1/2/3?u='+encodeURIComponent(product);
const before={empty:WALMART_IMPACT.accountId===''&&!WALMART_IMPACT.adId&&!WALMART_IMPACT.campaignId,
 search:walmartAffiliateUrl(search), product:walmartAffiliateUrl(product), deals:walmartAffiliateUrl(deals), already:walmartAffiliateUrl(already),
 target:affiliateUrl('https://www.target.com/p/x')};
WALMART_IMPACT.accountId='111';WALMART_IMPACT.adId='222';WALMART_IMPACT.campaignId='333';
const wrapped=walmartAffiliateUrl(search);
const still=walmartAffiliateUrl(already);
WALMART_IMPACT.accountId='';WALMART_IMPACT.adId='';WALMART_IMPACT.campaignId='';
console.log(JSON.stringify({before,wrapped,still,expected:'https://goto.walmart.com/c/111/222/333?u='+encodeURIComponent(search)}));
""")
        self.assertTrue(r['before']['empty'])
        self.assertEqual(r['before']['search'], 'https://www.walmart.com/search?q=clearance')
        self.assertEqual(r['before']['product'], 'https://www.walmart.com/ip/Kids-Bike/1234567')
        self.assertEqual(r['before']['deals'], 'https://www.walmart.com/shop/deals')
        self.assertTrue(r['before']['already'].startswith('https://goto.walmart.com/'))
        self.assertEqual(r['before']['target'], 'https://www.target.com/p/x')
        self.assertEqual(r['wrapped'], r['expected'])
        self.assertEqual(r['still'], r['before']['already'])

class HelperIsWiredIn(unittest.TestCase):
    def test_pages_and_worker_use_the_shared_helpers(self):
        self.assertIn('src="./affiliate-links.js"', INDEX)
        self.assertIn('src="./affiliate-links.js"', SHOP)
        for src, name in [(INDEX, 'index'), (SHOP, 'shop'), (WORKER, 'worker')]:
            self.assertIn('amazonAffiliateUrl', src, name)
            self.assertIn('walmartAffiliateUrl', src, name)
        # Dashboard search builders go through the helper instead of returning a raw href.
        for fn in ('amazonDealUrl', 'amazonUsedUrl', 'searchUrl'):
            self.assertRegex(INDEX, fn + r'\([^)]*\)\{[^}]*return amazonAffiliateUrl\(')
        for fn in ('walmartDealUrl', 'walmartUrl'):
            self.assertRegex(INDEX, fn + r'\([^)]*\)\{[^}]*return walmartAffiliateUrl\(')
        self.assertIn("function postingLink(asin){return amazonAffiliateUrl('',asin)}", INDEX)
        self.assertIn("const link=asin=>amazonAffiliateUrl('',asin)", SHOP)
        self.assertIn("function dealHref(d){if(d.offsite){const u=walmartAffiliateUrl(offsiteUrl(d.url)||'')", SHOP)
        # No leftover hardcoded Amazon search hrefs without the helper.
        self.assertNotRegex(INDEX, r"return u\.href\}\nfunction amazonUsedUrl|return u\.href\}\nfunction walmartDealUrl|return url\.href\}\nfunction walmartLinks|return u\.href\}\nfunction link\(")

    def test_tag_lives_in_one_config_spot(self):
        text = HELPER.read_text()
        self.assertIn("const AFFILIATE_TAG='dealstoday0b3-20'", text)
        self.assertIn("accountId:''", text)
        self.assertIn("adId:''", text)
        self.assertIn("campaignId:''", text)
        self.assertIn('goto.walmart.com/c/', text)

if __name__ == '__main__':
    unittest.main()
