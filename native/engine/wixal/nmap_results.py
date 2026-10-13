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
                row=dict(host=address.get('addr',''),port=str(number),protocol=port.get('protocol',''),
                                     state=state.get('state','unknown') if state is not None else 'unknown',
                                     service=dict(service.attrib) if service is not None else {})
                scripts=port.findall('script')
                if scripts:
                    row['scripts']=[dict(id=s.get('id',''),output=s.get('output','')[:16000],
                                         truncated=len(s.get('output',''))>16000) for s in scripts[:32]]
                if service is not None and service.findall('cpe'):row['cpe']=[c.text or '' for c in service.findall('cpe')[:16]]
                services.append(row)
        finished=root.find('runstats/finished')
        if finished is None or finished.get('exit')!='success':raise ValueError('Scanner XML has no successful completion record')
        return services
    except (ET.ParseError,TypeError) as error:
        raise ValueError('Complete valid Nmap XML was not present') from error


async def finish(job):
    evidence=job['evidence'];assessment=job['assessment']
    result=dict(kind='nmap',coverage='partial',services=[],invocation=assessment,evidence=evidence,
                interpretation='Scanner observations are evidence of port state; service labels alone do not establish vulnerabilities.')
    if assessment.get('profile')=='rdp':
        result['interpretation']+=' RDP script SUCCESS reports supported protocol negotiation only. It does not establish that NLA is required, authentication succeeded, exploitation was tested, or the device is secure. Certificate trust requires separate validation.'
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
