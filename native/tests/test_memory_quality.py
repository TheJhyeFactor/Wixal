import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store

class MemoryQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name);self.store.add_project(self.temp.name)
    def tearDown(self):self.store.close();self.temp.cleanup()
    def test_unrelated_preference_is_not_injected(self):
        self.store.memory.save('Always use PostgreSQL for the invoice database')
        self.assertEqual(self.store.memory.recall('How do volcanoes form?',include_history=False),[])
    def test_changed_session_index_and_deleted_session(self):
        s=self.store.session();s['messages']=[dict(role='user',content='The database is PostgreSQL')];self.store.save()
        self.store.memory.sync();self.assertEqual(self.store.db.execute('SELECT count(*) FROM memory_search').fetchone()[0],1)
        self.store.memory.sync();self.assertEqual(self.store.memory.index_metrics['changedSessions'],0)
        s['messages'][0]['content']='The database is SQLite';self.store.save();self.store.memory.sync()
        self.assertEqual(self.store.db.execute('SELECT content FROM memory_search').fetchone()[0],'The database is SQLite')
        self.store.data['sessions']=[];self.store.memory.sync();self.assertEqual(self.store.db.execute('SELECT count(*) FROM memory_search').fetchone()[0],0)
    def test_correction_retains_sources_and_suppresses_old_history(self):
        s=self.store.session();s['messages']=[dict(role='user',content='Use PostgreSQL for the database')];self.store.save()
        n=self.store.memory.save(s['messages'][0]['content'],source_session=s['id'],source_message=s['messages'][0]['id'])
        self.store.memory.save('Use SQLite for the database instead',replace=n['id'])
        self.assertEqual(n['revisions'][0]['content'],'Use PostgreSQL for the database')
        self.assertFalse(any(x['kind']=='history' for x in self.store.memory.recall('PostgreSQL database')))
    def test_suggestion_replace_and_stale_guard(self):
        old=self.store.memory.save('We decided to use PostgreSQL for the database')
        s=self.store.session();s['messages']=[dict(role='user',content='We decided to use SQLite for the database instead')];self.store.save()
        self.store.memory.suggest(s['messages'][0]['content'],s)
        suggestion=self.store.memory.snapshot()['suggestions'][0];self.assertEqual(suggestion['relatedId'],old['id'])
        self.store.memory.dispatch('memory-suggestion',dict(id=suggestion['id'],accept=True,consolidate=True))
        self.assertEqual(len(self.store.memories()),1);self.assertIn('SQLite',old['content'])
    def test_review_correction_rejects_stale_evidence_and_retains_pending(self):
        old=self.store.memory.save('We decided to use PostgreSQL for invoices')
        session=self.store.session();session['messages']=[dict(role='user',content='We decided to use SQLite for invoices instead')];self.store.save()
        self.store.memory.suggest(session['messages'][0]['content'],session)
        suggestion=self.store.memory.snapshot()['suggestions'][0]
        self.assertEqual(suggestion['previousContent'],old['content'])
        self.assertEqual(suggestion['sourceMessage'],session['messages'][0]['id'])
        self.store.memory.save('We decided to use MariaDB for invoices',replace=old['id'])
        with self.assertRaisesRegex(ValueError,'related note changed'):
            self.store.memory.dispatch('memory-suggestion',dict(id=suggestion['id'],accept=True,consolidate=True,operation='replace'))
        self.assertIn('MariaDB',self.store.memories()[0]['content'])
        self.assertEqual(self.store.memory.snapshot()['suggestions'][0]['id'],suggestion['id'])

    def test_review_combine_preserves_both_texts_and_original_source_after_restart(self):
        old=self.store.memory.save('We decided to use PostgreSQL for invoices')
        session=self.store.session();session['messages']=[dict(role='user',content='We decided to use SQLite for invoices instead')];self.store.save()
        self.store.memory.suggest(session['messages'][0]['content'],session)
        suggestion=self.store.memory.snapshot()['suggestions'][0]
        self.store.memory.dispatch('memory-suggestion',dict(id=suggestion['id'],accept=True,consolidate=True,operation='merge'))
        directory=self.store.directory;self.store.close();self.store=Store(directory)
        saved=self.store.memories()[0]
        self.assertEqual(len(self.store.memories()),1)
        self.assertEqual(saved['content'],'We decided to use PostgreSQL for invoices\nWe decided to use SQLite for invoices instead')
        self.assertEqual(saved['sourceSession'],session['id']);self.assertEqual(saved['sourceMessage'],session['messages'][0]['id'])
        self.assertEqual(self.store.memory.snapshot()['suggestions'],[])

    def test_replacement_excludes_derived_answer_and_restart_keeps_index(self):
        note=self.store.memory.save('Invoices use PostgreSQL')
        s=self.store.session();s['messages']=[dict(role='assistant',content='Billing data is stored in PostgreSQL',memoryReferences=[note['id']])];self.store.save()
        self.store.memory.sync();self.store.memory.save('Invoices use SQLite instead',replace=note['id'])
        self.assertFalse(any(r['kind']=='history' for r in self.store.memory.recall('billing data')))
        directory=self.store.directory;self.store.close();self.store=Store(directory);self.store.memory.sync()
        self.assertEqual(self.store.memory.index_metrics['changedSessions'],0)
    def test_changed_database_value_is_a_conflict_without_instead(self):
        self.store.memory.save('The project invoice database is PostgreSQL')
        relation=self.store.memory.related('The project invoice database is SQLite','project')
        self.assertEqual(relation['action'],'replace')
    def test_single_changed_value_does_not_merge_opposite_decisions(self):
        self.store.memory.save('Python will be the engine language and SwiftUI will remain the desktop interface.')
        relation=self.store.memory.related('Rust will be the engine language and SwiftUI will remain the desktop interface.','project')
        self.assertEqual(relation['action'],'replace')
        self.assertEqual(relation['reason'],'Possible superseded decision')

    def test_past_questions_do_not_serve_as_answer_evidence(self):
        self.store.memory.save('Wixal should use small models with relevant recalled notes')
        previous=self.store.session();previous['messages']=[dict(role='user',content='What is my preference for small models and memory?')];self.store.save()
        current=self.store.new_session()
        text,sources=self.store.memory.context('What is my preference for small models and memory?',current,2400)
        self.assertTrue(sources);self.assertTrue(all(s['kind']=='saved' for s in sources))
        self.assertTrue(any(r['kind']=='history' for r in self.store.memory.recall('previous questions about small models')))

    def test_exact_dedup_retains_both_source_links(self):
        n=self.store.memory.save('Use SQLite for invoices',source_session='one',source_message='a')
        again=self.store.memory.save('Use SQLite for invoices',source_session='two',source_message='b')
        self.assertEqual(n['id'],again['id']);self.assertEqual({s['message'] for s in again['sources']},{'a','b'})

    def test_forgetting_consolidated_note_excludes_retired_derived_history(self):
        first=self.store.memory.save('Use SQLite for invoices.')
        second=self.store.memory.save('Use SQLite for invoices!')
        self.store.session()['messages']=[dict(role='assistant',content='Billing storage is local',memoryReferences=[first['id']])];self.store.save()
        pending=self.store.memory.dispatch('memory-consolidate',{})['suggestions'][0]
        self.store.memory.dispatch('memory-suggestion',dict(id=pending['id'],accept=True,consolidate=True))
        target=self.store.memories()[0];self.assertEqual(len(self.store.memories()),1)
        self.store.memory.forget(target['id'])
        self.assertEqual(self.store.memory.recall('billing storage'),[])

    def test_fresh_tool_request_does_not_receive_old_execution_evidence(self):
        prior=self.store.session();prior['messages']=[dict(role='tool',tool_name='read_file',content='read_file native returned an error: this is a directory')];self.store.save()
        current=self.store.new_session();text,sources=self.store.memory.context('Use @read_file with path native and report the actual error.',current,2400)
        self.assertEqual(sources,[])
        self.assertTrue(self.store.memory.recall('previous read_file native error'))

    def test_source_roles_and_identity(self):
        s=self.store.session();s['messages']=[dict(role='tool',tool_name='read_file',content='Verified invoice schema uses customer_id')];self.store.save()
        result=self.store.memory.recall('invoice schema')[0]
        self.assertEqual(result['sourceRole'],'tool');self.assertEqual(result['tool'],'read_file')
        s['memoryOwner']='account:another';self.store.save();self.store.memory.sync();self.assertEqual(self.store.memory.recall('invoice schema'),[])
    def test_fresh_natural_scan_excludes_previous_task_constraints(self):
        prior=self.store.session();prior['messages']=[dict(role='user',content='Discover TCP ports on 127.0.0.1. Do not inspect services.'),dict(role='assistant',content='TCP discovery completed. No inspection requested.')];self.store.save()
        self.store.memory.save('I prefer careful TCP discovery for owned hosts')
        current=self.store.new_session()
        text,sources=self.store.memory.context('For my host 127.0.0.1, discover TCP ports 18795 and then inspect the discovered ports.',current,2400)
        self.assertTrue(sources);self.assertTrue(all(source['kind']=='saved' for source in sources));self.assertNotIn('Do not inspect services',text)
        self.assertTrue(any(source['kind']=='history' for source in self.store.memory.recall('previous TCP discovery')))

    def test_literal_repeat_excludes_recall_but_retains_searchable_history(self):
        prior=self.store.session();prior['messages']=[dict(role='user',content='Reply with exactly: Wixal background scheduling works.'),dict(role='assistant',content='My background scheduling system is functional.')];self.store.save()
        current=self.store.new_session()
        self.assertEqual(self.store.memory.context('Reply with exactly: Wixal background scheduling works.',current,2400),('',[]))
        self.assertTrue(self.store.memory.recall('previous background scheduling'))
