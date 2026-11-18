"""Dashboard logic (watch list parsing, 'new or dropped since last scan', history line) run in Node."""
import json,re,shutil,subprocess,unittest
from pathlib import Path
HTML=Path(__file__).with_name('index.html').read_text()
def fn(name):
    start=HTML.index('function '+name+'(')
    m=re.compile(r'\n(?! )').search(HTML,start+1)
    return HTML[start:m.start()]
@unittest.skipUnless(shutil.which('node'),'node not installed')
class DashboardLogic(unittest.TestCase):
    def run_js(self,body):
        src='\n'.join(fn(n) for n in ['cleanWatch','parseWatchInput','historyFacts','freshInfo','freshRank','shortDate','previousPriceLine'])
        prelude="const esc=s=>String(s);const cash=n=>'$'+Number(n).toFixed(2);let trackedHistory=null,data=null;function latestScanTime(){return Date.parse(data&&data.updated||'')||0}\n"
        out=subprocess.run(['node','-e',prelude+src+'\nconsole.log(JSON.stringify((()=>{'+body+'})()))'],capture_output=True,text=True,timeout=30)
        self.assertEqual(out.returncode,0,out.stderr);return json.loads(out.stdout)
    def test_watch_input(self):
        r=self.run_js("return ['https://www.amazon.com/Some-Thing/dp/B0ABC12345?ref=x','b0abc12345','air  fryer','headphones','https://example.com/x','a'].map(parseWatchInput)")
        self.assertEqual(r[0],{'asin':'B0ABC12345'});self.assertEqual(r[1],{'asin':'B0ABC12345'})
        self.assertEqual(r[2],{'keyword':'air fryer'});self.assertEqual(r[3],{'keyword':'headphones'})
        self.assertIn('error',r[4]);self.assertIn('error',r[5])
    def test_clean_watch(self):
        r=self.run_js("return cleanWatch({asins:['b0abc12345','B0ABC12345','<x>'],keywords:['Lego','lego',' x ']})")
        self.assertEqual(r,{'asins':['B0ABC12345'],'keywords':['Lego']})
    def test_fresh_kinds(self):
        r=self.run_js("""const T='2026-11-18T18:11:14+00:00',O='2026-11-17T10:00:00+00:00';data={updated:T};
         trackedHistory={A000000001:{points:[[T,10]],checks:1},A000000002:{points:[[O,20],[T,15]],checks:5},A000000003:{points:[[O,15]],checks:9},A000000004:{points:[[O,10],[T,12]],checks:4}};
         const k=(asin,price,at)=>freshInfo({asin,price,checkedAt:at||T});
         return [k('A000000001',10),k('A000000002',15),k('A000000003',15),k('A000000004',12),k('A000000001',10,O),
           freshInfo({asin:'U1',conditionLabel:'Used',price:8,previousPrice:10,priceChangedAt:T,checkedAt:T}),
           freshInfo({asin:'U2',conditionLabel:'Used',price:8,firstSeenAt:T,checkedAt:T}),
           freshInfo({asin:'U3',conditionLabel:'Used',price:8,firstSeenAt:O,checkedAt:T})]""")
        self.assertEqual([x.get('kind') for x in r],['new','drop','','','','drop','new',''])
        self.assertAlmostEqual(r[1]['pct'],0.25)
    def test_history_line_only_from_real_history(self):
        r=self.run_js("""trackedHistory={A000000002:{points:[['2026-11-15T10:00:00Z',20],['2026-11-17T10:00:00Z',15]],checks:5},A000000003:{points:[['2026-11-15T10:00:00Z',15]],checks:3}};
          return [previousPriceLine({asin:'A000000002',price:15}),previousPriceLine({asin:'A000000003',price:15}),previousPriceLine({asin:'NOHISTORY1',price:15})]""")
        self.assertIn('Down $5.00 from $20.00',r[0]);self.assertIn('Tracked low $15.00',r[0]);self.assertIn('high $20.00',r[0])
        self.assertIn('Same price since',r[1]);self.assertNotIn('Down',r[1])
        self.assertEqual(r[2],'')
if __name__=='__main__':unittest.main()
