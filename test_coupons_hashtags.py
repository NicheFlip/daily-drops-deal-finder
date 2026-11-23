"""Coupon codes, per-deal hashtags and the 'Add a deal' form (dashboard, shop, worker)."""
import json, pathlib, re, shutil, subprocess, unittest

ROOT = pathlib.Path(__file__).parent
INDEX = (ROOT / 'index.html').read_text()
SHOP = (ROOT / 'shop.html').read_text()
WORKER = (ROOT / 'cloudflare' / 'daily-drops-publisher-worker.js').read_text()

def extract(src, start, end):
    i = src.index(start); return src[i:src.index(end, i)]

SAMPLES = [
    {'title': 'LEGO Star Wars Building Set', 'asin': 'B0ABCDEF12', 'couponCode': 'SAVE20'},
    {'title': 'Ninja Air Fryer 6 qt', 'url': 'https://www.walmart.com/ip/123456789', 'price': 40, 'previousPrice': 60},
    {'title': 'Cozy throw blanket', 'url': 'https://www.target.com/p/x/-/A-1', 'couponCode': 'COZY15'},
    {'title': 'Echo Dot speaker', 'asin': 'B0ABCDEF13', 'conditionLabel': 'Used - Like New', 'price': 10, 'referencePrice': 40},
    {'title': 'Dog chew toy', 'url': 'https://goto.walmart.com/c/1/2/3?u=https%3A%2F%2Fwww.walmart.com%2Fip%2F55555'},
]

@unittest.skipUnless(shutil.which('node'), 'node not installed')
class HashtagParity(unittest.TestCase):
    def run_js(self, code):
        out = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def tags(self, src):
        block = extract(src, 'const HASHTAG_TOPICS', 'function cleanCoupon') + extract(src, 'function cleanCoupon', '\n')
        return self.run_js(block + '\nconsole.log(JSON.stringify(' + json.dumps(SAMPLES) + '.map(dealHashtags)))')

    def test_dashboard_and_worker_generate_identical_tags(self):
        a, b = self.tags(INDEX), self.tags(WORKER)
        self.assertEqual(a, b)
        for tags in a:
            self.assertLessEqual(len(tags), 5)
            self.assertEqual(len({t.lower() for t in tags}), len(tags))
            self.assertNotIn('#DailyDropsWithHeather', tags)
        self.assertEqual(a[0][:2], ['#AmazonDeals', '#ToyDeals'])
        self.assertIn('#CouponCode', a[0])
        self.assertEqual(a[1][0], '#WalmartDeals'); self.assertIn('#PriceDrop', a[1])
        self.assertEqual(a[2][0], '#TargetDeals'); self.assertIn('#CouponCode', a[2])
        self.assertIn('#Clearance', a[3])
        self.assertEqual(a[4][0], '#WalmartDeals')
        self.assertEqual(self.tags(INDEX), a, 'hashtags must be deterministic')

    def test_coupon_line_is_added_and_replaced(self):
        block = extract(INDEX, 'function setCouponLine', '\n')
        r = self.run_js(block + r"""
const base='🔥 $5\n\nTitle\n\n👉 https://x\n\n#AmazonDeals #ToyDeals\nAs an Amazon Associate, I earn from qualifying purchases.';
const a=setCouponLine(base,'SAVE20'),b=setCouponLine(a,'NEW10'),c=setCouponLine(b,'');
console.log(JSON.stringify([a,b,c]))""")
        a, b, c = r
        self.assertIn('🏷 Use code SAVE20', a); self.assertIn('#CouponCode', a)
        self.assertIn('🏷 Use code NEW10', b); self.assertNotIn('SAVE20', b); self.assertEqual(b.count('#CouponCode'), 1)
        self.assertNotIn('Use code', c); self.assertNotIn('#CouponCode', c)

class NoOldHashtag(unittest.TestCase):
    def test_brand_hashtag_removed_everywhere(self):
        self.assertNotIn('#DailyDropsWithHeather', INDEX)
        self.assertNotIn('#DailyDropsWithHeather', SHOP)
        # The worker only mentions it inside the regex that strips it from older saved captions.
        self.assertEqual(WORKER.count('#DailyDropsWithHeather'), WORKER.count("replace(/#DailyDropsWithHeather"))

class CouponAndForm(unittest.TestCase):
    def test_shop_coupon_box(self):
        for s in ['class="coupon"', 'data-coupon=', 'Tap to copy code', 'Copied!', 'border:2px dashed', "Get deal at '"]:
            self.assertIn(s, SHOP)

    def test_dashboard_coupon_field_and_add_form(self):
        for s in ['data-post-coupon', "set('coupon'", 'id="fbAdd"', 'id="fbLink"', 'id="fbCoupon"', "/api/og?url=", 'fbDealLink']:
            self.assertIn(s, INDEX)
        self.assertNotRegex(INDEX, r'TELEGRAM_BOT_TOKEN|FB_PAGE_TOKEN|api\.telegram\.org|graph\.facebook\.com')

    def test_ready_to_post_mobile_css(self):
        css = re.search(r'@media\(max-width:760px\)\{\.post-card[^\n]*', INDEX).group(0)
        for s in ['flex-direction:column', '.fb-photo{max-height:220px}', 'minmax(0,1fr)']:
            self.assertIn(s, css)
        self.assertIn('overflow-wrap:anywhere', INDEX)

if __name__ == '__main__':
    unittest.main()
