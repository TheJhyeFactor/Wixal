"""Normalize complete scanner stdout before exposing a terminal command result."""
import asyncio
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def parse(raw):
    if len(raw)>16*1024*1024 or b'<!ENTITY' in raw.upper():
        raise ValueError('Scanner XML exceeds the evidence bound or contains entities')
    try:
        root=ET.fromstring(raw)
        if root.tag!='nmaprun':raise ValueError('Expected Nmap XML')
        services=[]
        for host in root.findall('host'):
            if host.get('timedout')=='true':raise ValueError('Scanner timed out on a host; coverage is partial')
            address=next((a for a in host.findall('address') if a.get('addrtype') in ('ipv4','ipv6')),None)
            if address is None:continue
            for port in host.findall('ports/port'):
                number=int(port.get('portid','0'))
                if not 1<=number<=65535:raise ValueError('Invalid scanner port')
                state=port.find('state');service=port.find('service')
                services.append(dict(host=address.get('addr',''),port=str(number),protocol=port.get('protocol',''),
                                     state=state.get('state','unknown') if state is not None else 'unknown',
                                     service=dict(service.attrib) if service is not None else {}))
        finished=root.find('runstats/finished')
        if finished is None or finished.get('exit')!='success':raise ValueError('Scanner XML has no successful completion record')
        return services
    except (ET.ParseError,TypeError) as error:
        raise ValueError('Complete valid Nmap XML was not present') from error


async def finish(job):
    evidence=job['evidence'];assessment=job['assessment']
    result=dict(kind='nmap',coverage='partial',services=[],invocation=assessment,evidence=evidence,
                interpretation='Scanner observations are evidence of port state; service labels alone do not establish vulnerabilities.')
    try:
        if job['state']!='completed' or job['exitCode']!=0 or evidence['incomplete']:
            raise ValueError('Scanner failed, stopped or produced incomplete evidence')
        raw=await asyncio.to_thread(Path(evidence['stdoutPath']).read_bytes)
        result.update(services=parse(raw),coverage='complete',stdoutSha256=hashlib.sha256(raw).hexdigest())
    except (OSError,ValueError) as error:
        result['error']=str(error)
    result['summary']=dict(openPorts=sum(s['state']=='open' for s in result['services']),observedPorts=len(result['services']),coverage=result['coverage'],portScanPerformed=assessment.get('profile')!='discovery')
    result['resultSha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    job['structuredResult']=result
