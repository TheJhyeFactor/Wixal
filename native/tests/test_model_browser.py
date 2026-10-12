import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal import model_browser as browser
from wixal.model_manager import estimate, GIB


class Response(io.BytesIO):
    def __init__(self,data,headers=None):super().__init__(data);self.headers=headers or {}


class BrowserTests(unittest.TestCase):
    def test_display_identity_and_parameter_count_are_separate_from_bytes(self):
        row=browser.metadata(dict(name='hf/tag:abc',size=1000,provenance=dict(repo='Publisher/Coder-7B-GGUF',file='coder-Q4_K_M.gguf')))
        self.assertEqual(row['publisher'],'Publisher');self.assertEqual(row['parameters'],7e9)
        self.assertEqual(row['displayName'],'Coder-7B');self.assertEqual(row['quantization'],'Q4_K_M')
        self.assertIn('coding',row['types']);self.assertNotIn('tools',row.get('capabilities',[]))

    def test_unknown_metadata_stays_unknown(self):
        row=browser.metadata(dict(name='arbitrary:model',size=1000))
        self.assertNotIn('parameters',row);self.assertEqual(row['publisher'],'Unknown');self.assertEqual(row['types'],[])
        fit=estimate({},dict(memoryBudget=12*GIB),8192)
        self.assertIsNone(fit['required']);self.assertIsNone(fit['recommended']);self.assertFalse(fit['fits'])

    def test_ram_recommendation_and_context_effect(self):
        model=dict(size=5*GIB,contextLength=32768,kvBytesPerToken=128*1024)
        device=dict(memoryBudget=18*GIB)
        low=estimate(model,device,4096);high=estimate(model,device,32768)
        self.assertGreater(high['required'],low['required']);self.assertGreaterEqual(high['recommended']*.75,high['required'])
        self.assertFalse(high['cacheEstimated'])

    def test_search_filters_pagination_and_gated_metadata(self):
        rows=[dict(id='Owner/Example',sha='a'*40,gguf={'total':7e9,'context_length':32768},pipeline_tag='text-generation',cardData={'license':'mit'},gated=True)]
        calls=[]
        def opened(url):calls.append(url);return Response(json.dumps(rows).encode(),{'Link':'<https://huggingface.co/api/models?cursor=abc>; rel="next"'})
        with patch.object(browser.hub,'open_hub',opened):result=browser.search_page(dict(search='Example',publisher='Owner',parameters='8',type='chat'))
        self.assertIn('author=Owner',calls[0]);self.assertIn('num_parameters=min%3A2B%2Cmax%3A8B',calls[0])
        self.assertEqual(result['models'][0]['parameters'],7e9);self.assertTrue(result['models'][0]['gated'])
        self.assertEqual(result['nextPage'],'https://huggingface.co/api/models?cursor=abc')

    def test_page_redirect_and_input_boundaries(self):
        for url in ('https://evil.test/api/models','https://huggingface.co/api/datasets','http://huggingface.co/api/models'):
            with self.assertRaises(ValueError):browser.page_url(url)
        for params in (dict(search='x'*161),dict(publisher='bad/name'),dict(type='invalid'),dict(parameters='invalid')):
            with self.assertRaises(ValueError):browser.search_page(params)

    def test_oversized_search_and_untrusted_repository_rejected(self):
        with patch.object(browser.hub,'open_hub',return_value=Response(b' '* (4*1024*1024+1))):
            with self.assertRaises(ValueError):browser.search_page({})
        with patch.object(browser.hub,'open_hub',return_value=Response(json.dumps([{'id':'../../escape'}]).encode())):
            self.assertEqual(browser.search_page({})['models'],[])


class BrowserAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_files_cached_without_mutable_result_aliases(self):
        instance=browser.Browser();row=browser.metadata(dict(name='Owner/Model',repo='Owner/Model',revision='a'*40))
        file=dict(repo='Owner/Model',revision='a'*40,name='hf/tag:hash',file='model.gguf',size=1000,sha256='b'*64)
        with patch.object(browser,'search_page',return_value=dict(models=[row],nextPage='')),patch.object(browser.hub,'repository',return_value=dict(files=[file])) as repo:
            result=await instance.search({});result['models'][0]['files'].clear()
            second=await instance.search({})
        self.assertEqual(len(second['models'][0]['files']),1);self.assertEqual(repo.call_count,1)
        self.assertEqual(second['models'][0]['files'][0]['revision'],'a'*40)

    async def test_gated_and_failed_inspection_never_offer_download_files(self):
        instance=browser.Browser()
        rows=[dict(name='Owner/Gated',repo='Owner/Gated',revision='a'*40,gated=True),dict(name='Owner/Failure',repo='Owner/Failure',revision='a'*40)]
        with patch.object(browser,'search_page',return_value=dict(models=rows,nextPage='')),patch.object(browser.hub,'repository',side_effect=ValueError('No access')):
            result=await instance.search({})
        self.assertTrue(all(not row['files'] and row['unavailable'] for row in result['models']))

if __name__=='__main__':unittest.main()
