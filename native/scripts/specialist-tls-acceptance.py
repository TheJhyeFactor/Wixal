"""Real testssl.sh invocation and cancellation against an owned TLS fixture.

This validates a bounded partial execution, not a completed TLS assessment.
The generated fixture key is temporary and is never included in the report.
"""
import argparse
import asyncio
import datetime
import hashlib
import importlib.util
import ipaddress
import json
import ssl
import tempfile
import time
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(options):
    base=options.output.resolve();base.mkdir(parents=True,exist_ok=False);project=base/'project';project.mkdir()
    real.ART=base;real.STATE=base/'workspace';helper=options.helper.resolve()
    client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434');server=None;ledger=[]
    report=dict(status='running',helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),started=time.time(),scope='Owned loopback TLS fixture; intentional cancellation, not a completed TLS assessment')
    try:
        with tempfile.TemporaryDirectory(prefix='wixal-tls-fixture-') as temporary:
            directory=Path(temporary);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Wixal disposable TLS fixture')]);now=datetime.datetime.now(datetime.timezone.utc)
            cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
            key_path=directory/'key.pem';key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
            cert_path=directory/'certificate.pem';cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(cert_path,key_path)
            async def serve(reader,writer):
                connection=writer.get_extra_info('ssl_object');ledger.append(dict(time=time.time(),protocol=connection.version(),cipher=connection.cipher()[0]))
                try:
                    await asyncio.wait_for(reader.read(8192),2)
                    writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK');await writer.drain()
                except (TimeoutError,ConnectionError):pass
                finally:writer.close()
            server=await asyncio.start_server(serve,'127.0.0.1',0,ssl=context,ssl_handshake_timeout=3)
            target=f'https://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            client.review_policy=lambda details:details.get('name')=='command_start' and details.get('assessment',{}).get('capability')=='addon:testssl' and details['assessment'].get('target')==target
            await client.start();await client.call('project-add',dict(root=str(project)))
            started=await client.call('tool',dict(name='addon_run',arguments=dict(id='testssl',target=target,timeout_seconds=60)))
            deadline=time.monotonic()+30
            while not ledger and time.monotonic()<deadline:
                result=await client.call('tool',dict(name='command_read',arguments=dict(session_id=started['session_id'],wait_ms=200,max_chars=100000)))
                if result['state']!='running':break
            assert ledger,dict(error='No actual TLS handshake observed',result=result)
            await client.call('tool',dict(name='command_stop',arguments=dict(session_id=started['session_id'])))
            while True:
                result=await client.call('tool',dict(name='command_read',arguments=dict(session_id=started['session_id'],wait_ms=200,max_chars=100000)))
                if result['state']!='running':break
            assert result['state']=='stopped',result
            report.update(status='passed',target=target,certificateSha256=cert.fingerprint(hashes.SHA256()).hex(),ledger=ledger,result=result,reviews=client.reviews,completedTLSAssessment=False)
    except BaseException as error:report.update(status='failed',error=str(error),ledger=ledger);raise
    finally:
        if server:server.close();await server.wait_closed()
        if hasattr(client,'child'):await client.close()
        report['finished']=time.time();(base/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status=report['status'],handshakes=len(ledger),completedTLSAssessment=False)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
