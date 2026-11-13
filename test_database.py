"""Offline checks for PostgreSQL archive schema and safe configuration."""
import os,unittest
from unittest.mock import patch
import database
class DatabaseTests(unittest.TestCase):
 def test_schema_has_history_and_indexes(self):
  for table in ('products','price_observations','discoveries'):
   self.assertIn('CREATE TABLE IF NOT EXISTS '+table,database.SCHEMA)
  self.assertIn('idx_observations_product',database.SCHEMA)
  self.assertNotIn('DELETE FROM',database.SCHEMA.upper())
 def test_no_secret_means_safe_noop(self):
  with patch.dict(os.environ,{'DATABASE_URL':''}):
   self.assertFalse(database.persist([],[]))
if __name__=='__main__':unittest.main()
