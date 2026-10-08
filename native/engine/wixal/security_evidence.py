"""Structured observations come from tools, never from a model's narrative."""
import hashlib
import json
from .storage import now

def capture(task,name,args,result):
    if name not in ('website_assess','website_simulate','network_read'):return
    if not isinstance(result,dict):return
    report=result.get('report',result)
    if not isinstance(report,dict):return
    if name=='network_read':
        if result.get('state')!='completed' or result.get('exitCode')!=0:return
        import xml.etree.ElementTree as ET
        output=result.get('output','');report=dict(summary=dict(partial=bool(result.get('more') or result.get('offset')),format='Nmap XML'),findings=[])
        if len(output)>1024*1024 or '<!ENTITY' in output:return
        try:
            xml=ET.fromstring(output)
            if xml.tag!='nmaprun':return
            for host in xml.findall('host'):
                address=host.find('address');target=address.get('addr','') if address is not None else ''
                for port in host.findall('ports/port'):
                    state=port.find('state');service=port.find('service')
                    if state is None or state.get('state')!='open':continue
                    report['findings'].append(dict(id='open-port-'+port.get('protocol','tcp')+'-'+port.get('portid',''),title='Open '+port.get('protocol','tcp')+' port '+port.get('portid',''),url=target,severity='info',confidence='Scanner observation',evidence=dict(state=state.attrib,service=service.attrib if service is not None else {}),remediation='Confirm whether this service and its exposure are intended.'))
            report['summary']['openPorts']=len(report['findings'])
        except ET.ParseError:
            report['summary'].update(partial=True,parseError='Complete Nmap XML was not present in this tool response')
        report['rawOutputSha256']=hashlib.sha256(output.encode()).hexdigest()
        for checkpoint in task.get('checkpoints',[]):
            if checkpoint['name']!='network_scan':continue
            try:started=json.loads(checkpoint.get('result',''))
            except (ValueError,TypeError):continue
            if isinstance(started,dict) and started.get('session_id')==result.get('session_id'):args=checkpoint.get('arguments',args);break
    record=dict(tool=name,target=args.get('url') or args.get('target') or ('disposable loopback lab' if name=='website_simulate' else ''),created=now(),paths=result.get('paths',[]),summary=report.get('summary',{}),sourceSha256=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest())
    evidence=task.setdefault('securityEvidence',[]);evidence.append(record)
    findings=task.setdefault('securityFindings',[])
    for finding in report.get('findings',[]):
        if not isinstance(finding,dict):continue
        row={k:v for k,v in finding.items() if k in ('id','severity','title','url','evidence','remediation','confidence')}
        row.update(sourceSha256=record['sourceSha256'],tool=name,observation='tool observation',verifiedExploit=False)
        fingerprint=hashlib.sha256(json.dumps([row.get('id'),row.get('url'),row.get('title')],sort_keys=True).encode()).hexdigest()
        existing=next((f for f in findings if f['fingerprint']==fingerprint),None)
        if existing:existing.update(row,lastObserved=now(),observations=existing.get('observations',1)+1)
        else:findings.append(dict(**row,fingerprint=fingerprint,observations=1,lastObserved=now()))
