"""Fast static smoke checks for public shop and private research UI.
No third-party dependencies; run before publishing site data.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parent
class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:
            if a['id'] in self.ids: raise AssertionError('Duplicate element id: '+a['id'])
            self.ids.add(a['id'])
        if tag=='a': self.links.append(a.get('href',''))

def parse(name):
    text=(ROOT/name).read_text(encoding='utf-8')
    elements=Elements()
    elements.feed(text)
    return text,elements

class FrontendSmoke(unittest.TestCase):
    def test_shop_buttons_have_handlers(self):
        html,el=parse('shop.html')
        for name in ('search','category','sort','refresh','savePreferences','shareShop','installApp','preferences','status','results','featuredResults'):
            self.assertIn(name,el.ids)
        for name in ('refresh','savePreferences','shareShop','installApp'):
            self.assertIn("$('"+name+"').addEventListener",html)
        self.assertIn('data-pref',html)
        self.assertIn('amazon-deals.json',html)
        self.assertIn('featured-finds.json',html)
    def test_shop_affiliate_and_product_validation(self):
        html,_=parse('shop.html')
        self.assertIn('affiliate-links.js',html)
        self.assertIn('dealstoday0b3-20',(ROOT/'affiliate-links.js').read_text())
        self.assertIn('validAsin(d.asin)',html)
        self.assertIn("d.retailer==='Amazon'",html)
        self.assertIn('rel="sponsored noopener noreferrer"',html)
        self.assertIn('As an Amazon Associate',html)
    def test_app_files(self):
        html,_=parse('shop.html')
        self.assertIn('manifest.webmanifest',html)
        self.assertIn('shop-sw.js',html)
        for name in ('manifest.webmanifest','app-icon.svg','shop-sw.js'):
            self.assertTrue((ROOT/name).is_file())
    def test_dashboard_navigation_and_queue(self):
        html,el=parse('index.html')
        for name in ('tab-posting','panel-posting','postingResults','postingCount','copyShopLink','copyShopStatus','tab-deals','tab-history','tab-walmart'):
            self.assertIn(name,el.ids)
        for action in ('caption','comment','graphic','remove'):
            self.assertIn("data-post-action=\""+action+"\"",html)
        self.assertIn('function renderPostingQueue()',html)
        self.assertIn("selectTab('posting')",html)
        self.assertIn('postingLinkFor',html)
        self.assertIn('./shop.html',html)
        self.assertIn("'posting','watch','history','walmart'",html)
        self.assertIn('data-price-history',html)
        self.assertIn('function compactCard(',html)
        self.assertIn('function compactReview(',html)
        self.assertIn('id="newOnly"',html)
        self.assertIn('id="showAllScanned"',html)
        self.assertIn('amazon-all-products.json',html)
        self.assertIn("candidateAsins.has(String(d.asin))",html)
        self.assertIn("name='deals';$('newOnly').checked=true",html)
        self.assertIn('amazon-discovery-archive.json',html)
    def test_dashboard_quick_deal_finds(self):
        html,el=parse('index.html')
        self.assertIn('quickFinds',el.ids)
        for mode in ('best','drops','lows','clearance','deep','under15','essentials','gifts','used'):
            self.assertIn('data-quick="'+mode+'"',html)
            self.assertIn(mode+':{label:',html)
        # History-window labels must come from tracked price points, never from list prices.
        self.assertIn("e.windowDays=days>=365?365:days>=90?90:days>=30?30:0",html)
        self.assertIn('used prices are never new-item history lows',html)
        self.assertIn("'p_8:'+pct+'-99'",html)
        self.assertIn('special_offers:Clearance',html)

    def test_public_shop_excludes_admin_controls(self):
        html,_=parse('shop.html')
        self.assertNotIn('DATABASE_URL',html)
        self.assertNotIn('JUDGMENT_KEY',html)
        self.assertNotIn('data-judgment=',html)
        self.assertNotIn('postingResults',html)

if __name__=='__main__':unittest.main()
