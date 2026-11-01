import importlib.util
from datetime import datetime,timezone
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('bridge',Path(__file__).resolve().parents[1]/'signalroom-airtable-bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class PublicationDates(unittest.TestCase):
 def test_publication_boundary_and_private_episode(self):
  e={'id':123,'title':'Episode | Guest','published_at':'2026-11-04T01:00:00-05:00','private':False}
  for now,published in [(datetime(2026,11,4,5,59,tzinfo=timezone.utc),False),(datetime(2026,11,4,6,tzinfo=timezone.utc),True)]:
   fields=bridge.build_pe_create(e,now=now)
   self.assertEqual(fields['Target Publish Date'],'2026-11-04')
   self.assertEqual('Published Date' in fields,published)
   self.assertNotIn('Publish Date',fields)
  e['private']=True
  self.assertNotIn('Published Date',bridge.build_pe_create(e,now=datetime(2026,11,5,tzinfo=timezone.utc)))
 def test_missing_or_ambiguous_date(self):
  e={'id':123,'title':'Episode | Guest'}
  self.assertNotIn('Published Date',bridge.build_pe_create(e))
  e['published_at']='2026-11-04T01:00:00'
  with self.assertRaises(ValueError):bridge.build_pe_create(e)
