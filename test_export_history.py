"""Offline checks for public PostgreSQL export contract."""
import unittest
import export_history
class HistoryExportTests(unittest.TestCase):
 def test_export_query_bounded(self):
  self.assertIn('LIMIT 500',export_history.QUERY)
  self.assertIn("p.retailer='Amazon'",export_history.QUERY)
  self.assertIn('MAX(o.observed_at)',export_history.QUERY)
 def test_no_credentials_in_export_sql(self):
  for forbidden in ('DATABASE_URL','password','secret','service_role'):
   self.assertNotIn(forbidden,export_history.QUERY)
if __name__=='__main__':unittest.main()
