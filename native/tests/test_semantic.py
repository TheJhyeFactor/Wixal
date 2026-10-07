import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store
from wixal.semantic import Semantic,cosine,digest

class SemanticTests(unittest.TestCase):
 def test_cosine_and_invalid_vectors(self):
  self.assertAlmostEqual(cosine([1,0],[1,0]),1)
  self.assertEqual(cosine([1,0],[0,1]),0)
  self.assertEqual(cosine([],[]),0)
  with self.assertRaises(ValueError):Semantic.validate([float('nan')])
 def test_cached_vectors_never_survive_changed_content_or_weights(self):
  with tempfile.TemporaryDirectory() as root:
   store=Store(root);semantic=store.memory.semantic;semantic.query='q';semantic.vector=[1,0];semantic.version='weights-v1'
   store.db.execute('INSERT INTO memory_vectors VALUES(?,?,?,?)',('n',digest('old'),'weights-v1',json.dumps([1,0])))
   self.assertEqual(semantic.scores('q',[('n','old')]),{'n':1})
   self.assertEqual(semantic.scores('q',[('n','changed')]),{})
   semantic.version='weights-v2';self.assertEqual(semantic.scores('q',[('n','old')]),{})
   store.close()
