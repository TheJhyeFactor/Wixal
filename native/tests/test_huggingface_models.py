import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal import huggingface_models as hub


class Response(io.BytesIO):
    def __init__(self,data,status=200,headers=None):super().__init__(data);self.status=status;self.headers=headers or {}


class HuggingFaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.body=b'GGUF'+b'bounded model fixture'*100
        self.sha=hashlib.sha256(self.body).hexdigest()
        self.selection=dict(repo='Owner/Model',file='sub/model.gguf',revision='a'*40,sha256=self.sha,size=len(self.body))
    def test_repository_pin_and_no_executable_files(self):
        metadata=dict(sha='a'*40,cardData={'license':'apache-2.0'},siblings=[dict(rfilename='model.gguf',lfs=dict(sha256=self.sha,size=len(self.body))),dict(rfilename='model.py'),dict(rfilename='split-00001-of-00002.gguf',lfs=dict(sha256=self.sha,size=100)),dict(rfilename='mmproj.gguf',lfs=dict(sha256=self.sha,size=100))])
        with patch.object(hub,'open_hub',return_value=Response(json.dumps(metadata).encode())):
            result=hub.repository('Owner/Model')
        self.assertEqual(len(result['files']),1);self.assertEqual(result['files'][0]['revision'],'a'*40)
        self.assertEqual(result['files'][0]['license'],'apache-2.0')
    def test_range_resume_and_verified_atomic_activation(self):
        partial=Path(self.tmp.name)/(self.sha+'.part');partial.write_bytes(self.body[:40]);requests=[]
        def response(url,headers):
            requests.append((url,headers));return Response(self.body[40:],206,{'Content-Range':f'bytes 40-{len(self.body)-1}/{len(self.body)}'})
        with patch.object(hub,'open_hub',response):result=hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None)
        self.assertEqual(result.read_bytes(),self.body);self.assertFalse(partial.exists());self.assertEqual(requests[0][1]['Range'],'bytes=40-')
        self.assertIn('/resolve/'+'a'*40+'/',requests[0][0])
    def test_server_ignores_range_starts_from_zero(self):
        (Path(self.tmp.name)/(self.sha+'.part')).write_bytes(self.body[:40])
        with patch.object(hub,'open_hub',return_value=Response(self.body)):
            result=hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None)
        self.assertEqual(result.read_bytes(),self.body)
    def test_wrong_range_hash_magic_and_oversize_rejected(self):
        for body in (b'NOPE'+self.body[4:],b'GGUF'+b'x'*(len(self.body)-4),self.body+b'x'):
            with patch.object(hub,'open_hub',return_value=Response(body)):
                with self.assertRaises(ValueError):hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None)
            self.assertFalse((Path(self.tmp.name)/(self.sha+'.gguf')).exists())
            (Path(self.tmp.name)/(self.sha+'.part')).unlink(missing_ok=True)
        (Path(self.tmp.name)/(self.sha+'.part')).write_bytes(self.body[:40])
        with patch.object(hub,'open_hub',return_value=Response(self.body[40:],206,{'Content-Range':'bytes 0-20/21'})):
            with self.assertRaisesRegex(ValueError,'range'):hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None)
    def test_pause_leaves_partial_without_installation(self):
        event=threading.Event();event.set()
        with patch.object(hub,'open_hub',return_value=Response(self.body)):
            with self.assertRaises(InterruptedError):hub.download(self.selection,self.tmp.name,event,lambda *_:None)
        self.assertFalse((Path(self.tmp.name)/(self.sha+'.gguf')).exists())
    def test_cache_reuse_still_verifies_bytes(self):
        final=Path(self.tmp.name)/(self.sha+'.gguf');final.write_bytes(self.body)
        with patch.object(hub,'open_hub',side_effect=AssertionError('Network should not repeat')):
            self.assertEqual(hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None),final)
            final.write_bytes(b'GGUFbad')
            with self.assertRaises(ValueError):hub.download(self.selection,self.tmp.name,threading.Event(),lambda *_:None)
    def test_input_and_redirect_boundaries(self):
        for value in ('../Repo','Owner/../Bad','https://huggingface.co/owner/repo','owner/repo;cmd'):
            with self.assertRaises(ValueError):hub.repo_id(value)
        for value in ('../model.gguf','/model.gguf','x//model.gguf','mmproj.gguf','x-00001-of-00002.gguf'):
            with self.assertRaises(ValueError):hub.file_name(value)
        for value in ('http://huggingface.co/x','https://huggingface.co.evil/x','https://user:secret@huggingface.co/x','https://127.0.0.1/x'):
            with self.assertRaises(ValueError):hub.safe_url(value)
        self.assertEqual(hub.safe_url('https://cas-bridge.xethub.hf.co/file'),'https://cas-bridge.xethub.hf.co/file')

if __name__=='__main__':unittest.main()
