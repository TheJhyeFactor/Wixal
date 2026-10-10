"""Check explicit port-state and inspection claims against current owned tool evidence.

This conservative check covers direct contradictions, not every possible natural
language claim or vulnerability inference. It never starts or repeats a tool.
"""
import hashlib
import json
import re


def facts(task):
    hosts={};sources=[]
    def observed_time(checkpoint):
        try:result=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):result={}
        timestamp=result.get('finished') if isinstance(result,dict) else None
        if isinstance(timestamp,(int,float)):return timestamp
        fallback=checkpoint.get('finished',checkpoint.get('created',0))
        return fallback if isinstance(fallback,(int,float)) else 0
    candidates=[c for c in task.get('checkpoints',[]) if c.get('status')=='finished' and c.get('name') in ('network_read','network_scan')]
    for checkpoint in sorted(candidates,key=observed_time):
        if checkpoint.get('status')!='finished' or checkpoint.get('name') not in ('network_read','network_scan'):continue
        try:result=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(result,dict) or result.get('error') or result.get('state')!='completed' or result.get('exitCode') not in (None,0):continue
        structured=result.get('structuredResult',result)
        if not isinstance(structured,dict) or structured.get('error'):continue
        if checkpoint['name']=='network_read' and not (structured.get('handoffEligible') or structured.get('coverage')=='complete'):continue
        services=structured.get('services',[])
        if not isinstance(services,list):continue
        observed=False
        if structured.get('handoffEligible'):
            invocation=structured.get('invocation',{})
            selected=invocation.get('ports',[]) if invocation.get('coverage')=='selected' else []
            for address in invocation.get('addresses',[])[:64]:
                if isinstance(address,str):hosts[address]={int(port):'unobserved' for port in selected[:4096] if isinstance(port,int) and 1<=port<=65535};observed=True
        for service in services[:4096]:
            if not isinstance(service,dict) or service.get('protocol','tcp')!='tcp':continue
            host=service.get('host');port=str(service.get('port',''));state=service.get('state')
            if not isinstance(host,str) or not re.fullmatch(r'[0-9]{1,5}',port) or not 1<=int(port)<=65535 or state not in ('open','closed','filtered','open|filtered','closed|filtered'):continue
            hosts.setdefault(host,{})[int(port)]=state;observed=True
        if observed:sources.append(dict(checkpointId=checkpoint['id'],sessionId=result.get('session_id'),sourceSessionId=result.get('sourceSessionId'),sha256=hashlib.sha256(checkpoint['result'].encode()).hexdigest()))
    return hosts,sources


def inspection_claim(answer):
    for sentence in re.split(r'[\n.!?]',answer):
        if re.search(r"\b(?:not|never|unable|cannot|can't|declined|failed|unavailable|only)\b",sentence,re.I):continue
        if re.search(r'\b(?:I|we)\s+(?:have\s+)?inspected\b|\b(?:ports|services)\s+(?:were|are|have been)\s+inspected\b|\bused\s+for\s+inspection\b',sentence,re.I):return True
        if re.search(r'\binspection(?:\s+step)?\s+(?:(?:was|is|has been|had been)\s+)?(?:performed|conducted|carried out)\b',sentence,re.I):return True
        if re.search(r'\binspection\b',sentence,re.I) and re.search(r'\b(?:completed?|finished|successful(?:ly)?|done)\b',sentence,re.I):return True
    return False

def availability_claim(task,available):
    """Check explicit adapter-enabled claims against controller-owned scope.

    This does not infer executable installation, readiness or authorization
    from a schema name. It covers only a named native tool being disabled.
    """
    contradictions=[]
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        if re.search(r"\b(?:cannot|can't)\s+(?:say|claim|establish)\b|\bnot\s+saying\b",sentence,re.I):continue
        if re.search(r'\b(?:if|whether|earlier|previous|historical|quoted|example)\b',sentence,re.I):continue
        for name in sorted(set(available)&{'network_discover','network_scan'}):
            label=r'`?'+re.escape(name)+r'`?(?:\s+tool)?'
            if re.search(label+r"\s+(?:is\s+)?(?:disabled|not\s+enabled)\b",sentence,re.I) or re.search(r"\b(?:not|doesn't|does\s+not)\s+have\s+(?:the\s+)?"+label+r'\s+enabled\b',sentence,re.I):contradictions.append(name)
    if not contradictions:return None
    return dict(check=dict(kind='tool_scope_claim'),status='failed',availableTools=sorted(set(contradictions)),error='These named native tools are enabled in the current controller scope. Installation, readiness and action approval remain separate; do not claim that an available adapter is disabled. Use its native schema or report the actual readiness/review error.')


def check(task):
    hosts,sources=facts(task)
    # A bare port number is ambiguous across multiple hosts; retain their raw
    # evidence without assigning one host's state to another host's statement.
    if len(hosts)!=1:return None
    host,states=next(iter(hosts.items()));ports=[p for p,state in states.items() if state=='open']
    answer=task.get('result','');errors=[]
    for sentence in re.split(r'[\n.!?;,]',answer):
        if re.search(r'\bno\s+open\s+ports(?:\s+detected)?\s+does\s+not\s+establish\b',sentence,re.I):continue
        if re.search(r"\b(?:not necessarily|cannot|can't|could|may|might|outside|other|unscanned|elsewhere)\b",sentence,re.I):continue
        if ports and re.search(r'\b(?:no|zero)\s+open\s+(?:tcp\s+)?ports\b|\ball\s+(?:(?:selected|tested|scanned|specified|requested|tcp)\s+)*(?:ports\s+)?(?:are\s+|were\s+)?(?:closed|filtered)\b',sentence,re.I):errors.append('The answer denies the observed open ports')
        if re.search(r'\b(?:open|closed)\s*\|\s*filtered\b',sentence,re.I):continue
        denies=bool(re.search(r'\bneither\b.*\bopen\b|\bnot\s+open\b',sentence,re.I))
        for port in ports:
            if not re.search(r'(?<!\d)'+str(port)+r'(?!\d)',sentence):continue
            if denies or re.search(r'\b(?:closed|filtered)\b',sentence,re.I) and not re.search(r'\bnot\b',sentence,re.I):errors.append(f'The answer contradicts observed open TCP port {port}')
        if not denies and not re.search(r'\bnot\b',sentence,re.I):
            for port,state in states.items():
                if state=='open':continue
                if re.search(r'(?<!\d)'+str(port)+r'(?!\d)[^0-9]{0,70}\bopen\b|\bopen\s+(?:tcp\s+)?(?:port\s+)?'+str(port)+r'(?!\d)',sentence,re.I):errors.append(f'The answer claims open TCP port {port}, which this evidence did not observe open')
    if not errors:return None
    return dict(check=dict(kind='network_port_claim'),status='failed',errors=errors,observed=dict(host=host,ports=sorted(ports)),sources=sources,error='Use the actual completed scanner observations; a port label does not establish a vulnerability.')


def evidence_quote(task):
    """A purported verbatim XML excerpt must occur in current completed output.

    Explicitly illustrative examples are not quotations. This does not attempt
    to certify arbitrary rewritten summaries or all model prose.
    """
    outputs=[];sources=[]
    for checkpoint in task.get('checkpoints',[]):
        if checkpoint.get('name')!='network_scan' or checkpoint.get('status')!='finished':continue
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict) or value.get('error') or value.get('state')!='completed':continue
        output=value.get('output')
        if isinstance(output,str) and output.strip():
            outputs.append(re.sub(r'\s+',' ',output.strip()))
            sources.append(dict(checkpointId=checkpoint['id'],sha256=hashlib.sha256(output.encode()).hexdigest()))
    if not outputs:return None
    answer=task.get('result','');invalid=[]
    for match in re.finditer(r'```xml\s*\n?(.*?)```',answer,re.I|re.S):
        context=answer[max(0,match.start()-240):match.start()]
        if re.search(r'\b(?:example|illustrative|schematic|simplified)\b',context,re.I):continue
        if not re.search(r'\b(?:output|excerpt|verbatim|verified)\b',context,re.I):continue
        quote=re.sub(r'\s+',' ',match.group(1).strip())
        if quote and not any(quote in output for output in outputs):invalid.append(hashlib.sha256(match.group(1).encode()).hexdigest())
    if not invalid:return None
    return dict(check=dict(kind='network_evidence_quote'),status='failed',error='The purported XML output excerpt does not match completed current-task scanner output. Quote retained evidence exactly, or describe it explicitly as a summary.',quoteSha256=invalid,sources=sources)


def corrected_summary(task):
    hosts,sources=facts(task)
    lines=['The generated interpretation did not pass the controller checks.']
    lines.append('Recorded scanner observations:' if hosts else 'No completed current-task scanner observations support this interpretation.')
    for host,states in hosts.items():
        ports=sorted(port for port,state in states.items() if state=='open')
        lines.append(f"- {host}: observed open TCP ports {', '.join(map(str,ports)) or 'none in this evidence' }.")
    if hosts:lines.append('These are observations from the selected scan coverage. Inspect the retained tool evidence; they do not prove service safety or a vulnerability.')
    for row in task.get('verification',{}).get('checks',[]):
        if row.get('check',{}).get('kind')=='tool_scope_claim' and row['status']=='failed':
            lines.append('The native tool schema is enabled for this task: '+', '.join(row['availableTools'])+'. This does not establish executable readiness or action approval. The requested action still needs completed tool evidence.')
    if any(r.get('check',{}).get('kind')=='requested_discovery_inspection' and r['status']=='failed' for r in task.get('verification',{}).get('checks',[])):lines.append('The requested source-bound inspection did not complete. Discovery alone does not finish that task.')
    return '\n'.join(lines)
