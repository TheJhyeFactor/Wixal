"""Run installed TShark through Wixal's bounded saved-capture adapter.

The capture is a declared generated Ethernet/IPv4/UDP fixture. This suite
does not sniff live traffic, grant capture permissions or qualify other tools.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import struct
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(options):
    base=options.output.resolve();base.mkdir(parents=True,exist_ok=False)
    real.ART=base;real.STATE=base/'workspace';project=base/'project';project.mkdir()
    # Independent oracle: one Ethernet frame containing one IPv4 UDP datagram.
    packet=bytes.fromhex('00112233445566778899aabb08004500001c0000000040110000c0000201c633640104d2162e00080000')
    capture=project/'one-udp.pcap'
    capture.write_bytes(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)+struct.pack('<IIII',0,0,len(packet),len(packet))+packet)
    helper=options.helper.resolve();client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434')
    client.review_policy=lambda details: details.get('name')=='command_start' and details.get('assessment',{}).get('capability')=='addon:wireshark'
    report=dict(status='running',helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),captureSha256=hashlib.sha256(capture.read_bytes()).hexdigest(),fixture='Generated one-packet Ethernet/IPv4/UDP capture; no live capture',started=time.time())
    try:
        await client.start();await client.call('project-add',dict(root=str(project)))
        report['catalogue']=await client.call('tool',dict(name='addon_catalog',arguments=dict(query='wireshark')))
        started=await client.call('tool',dict(name='addon_run',arguments=dict(id='wireshark',path=capture.name,timeout_seconds=30)))
        while True:
            result=await client.call('tool',dict(name='command_read',arguments=dict(session_id=started['session_id'],wait_ms=1000,max_chars=100000)))
            if result['state']!='running':break
        assert result['exitCode']==0,result
        assert all(protocol in result['output'].lower() for protocol in ('eth','ip','udp')),result
        assert hashlib.sha256(capture.read_bytes()).hexdigest()==report['captureSha256']
        report.update(status='passed',command=started,result=result,reviews=client.reviews)
    except BaseException as error:report.update(status='failed',error=str(error));raise
    finally:
        await client.close();report['finished']=time.time();(base/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status=report['status'],adapter='saved-capture TShark',captureUnchanged=True)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
