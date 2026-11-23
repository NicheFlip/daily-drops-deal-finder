"""Posted-on-Facebook flow: shop section, dashboard button, and the Worker's offline tests (Node 22.13+)."""
import shutil,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).parent
class PostedDeals(unittest.TestCase):
    def test_shop_has_posted_section_with_safe_links(self):
        s=(ROOT/'shop.html').read_text()
        self.assertIn('id="postedSection"',s);self.assertIn("/api/posted",s)
        self.assertIn("!excludedAsins.has(p.asin)",s);self.assertIn("rows=rows.filter(d=>!postedAsins.has(d.asin))",s)
        self.assertIn("url:''",s)  # posted cards always rebuild the tagged Amazon link
    def test_dashboard_never_holds_secrets(self):
        s=(ROOT/'index.html').read_text()
        self.assertIn('data-post-action="posted"',s);self.assertIn("PUBLISHER+'/posted'",s)
        for bad in ('TELEGRAM_BOT_TOKEN','FB_PAGE_TOKEN','GH_DISPATCH_TOKEN','PUBLISH_SECRET'):self.assertNotIn(bad,s)
        self.assertNotIn('api.telegram.org',(ROOT/'shop.html').read_text()+s)
    def test_worker_offline_suite(self):
        node=shutil.which('node')
        if not node:self.skipTest('node not installed')
        if subprocess.run([node,'-e',"require('node:sqlite')"],capture_output=True).returncode:self.skipTest('node:sqlite unavailable')
        r=subprocess.run([node,'--test',str(ROOT/'cloudflare'/'worker.test.mjs')],capture_output=True,text=True,timeout=120)
        self.assertEqual(r.returncode,0,r.stdout[-2000:]+r.stderr[-2000:])
if __name__=='__main__':unittest.main()
