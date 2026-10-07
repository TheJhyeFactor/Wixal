import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wixal.storage import Store
from wixal.memory_review import candidates, verified_items, fragments, review


class ReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'state')
        root=Path(self.temp.name)/'project';root.mkdir();self.store.add_project(root)
        self.store.data['model']='fixture';self.session=self.store.session();self.session['messages']=[dict(role='user',content='Python will be the engine language.'),dict(role='assistant',content='Invented assistant decision')];self.store.save()
    async def asyncTearDown(self):self.store.close();self.temp.cleanup()
    def test_only_scoped_human_messages_are_candidates(self):
        self.assertEqual(len(candidates(self.store,self.session)),1)
        self.store.data['forgottenMemorySources']=[self.session['messages'][0]['id']]
        self.assertEqual(candidates(self.store,self.session),[])
        self.store.data['forgottenMemorySources']=[];self.session['memoryOwner']='account:someone-else'
        self.assertEqual(candidates(self.store,self.session),[])
    def test_quotes_must_be_exact_and_from_the_cited_source(self):
        sources=candidates(self.store,self.session);source=sources[0]['id']
        items=[dict(source=source,quote='Python will be the engine language.',kind='decision'),dict(source=source,quote='Use Rust for the engine.',kind='decision'),dict(source=['bad'],quote='Python will be the engine language.',kind='decision'),dict(source=self.session['messages'][1]['id'],quote='Invented assistant decision',kind='decision')]
        self.assertEqual(len(verified_items(items,sources)),1)
    def test_questions_credentials_and_fenced_code_are_excluded(self):
        for text in ('Which language should I use?','api_key=PRIVATE_VALUE','My password is PRIVATE_VALUE','```\nPython will be used\n```'):
            self.session['messages'][0]['content']=text
            self.assertEqual(candidates(self.store,self.session),[])
    def test_fragment_guards_exclude_progress_and_hypothetical_choices(self):
        sources=[dict(id='source',text='I have just opened a terminal. Maybe we will use Rust. Python will be the engine language. Reply with one sentence.')]
        self.assertEqual([item['text'] for item in fragments(sources)],['Python will be the engine language.'])
    async def test_review_creates_suggestion_with_counters_but_never_saves_fact(self):
        source=self.session['messages'][0]['id'];requests=[]
        async def stream(endpoint,body,emit):
            requests.append(body);return dict(content=json.dumps(dict(items=[dict(evidence='q1',kind='decision'),dict(evidence='q999',kind='decision')])),usage=dict(eval_count=30,prompt_eval_count=180))
        class Runtime:
            async def endpoint(self):return 'http://127.0.0.1:1'
        with patch('wixal.agent.stream_chat',stream):result=await review(self.store,self.session,Runtime(),dict(capabilities=['completion']),4096,lambda *_:None)
        self.assertFalse(self.store.data['memories']);self.assertEqual(len(result['suggestions']),1)
        suggestion=result['suggestions'][0];self.assertTrue(suggestion['quoteVerified']);self.assertEqual(suggestion['sourceMessage'],source)
        self.assertEqual(self.store.data['usage'][-1]['kind'],'memory-review')
        self.assertLessEqual(result['review']['estimatedInput']+result['review']['outputReserve'],4096)
        self.assertNotIn('tools',requests[0]);self.assertEqual(candidates(self.store,self.session),[])
        self.store.memory.dispatch('memory-suggestion',dict(id=suggestion['id'],accept=True))
        self.assertEqual(self.store.data['memories'][0]['content'],'Python will be the engine language.')


if __name__=='__main__':unittest.main()
