"""Check explicit port-state and inspection claims against current owned tool evidence.

This conservative check covers direct contradictions, not every possible natural
language claim or vulnerability inference. It never starts or repeats a tool.
"""
import hashlib
import json
import re


def reference_claim(task):
    """A reported handle must remain copyable; never repair a tool argument."""
    known=set()
    canonical=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
    for checkpoint in task.get('checkpoints',[]):
        if checkpoint.get('status')!='finished' or checkpoint.get('name') not in ('network_discover','network_read','network_scan'):continue
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict):continue
        for key in ('session_id','sourceSessionId'):
            reference=value.get(key)
            if isinstance(reference,str) and re.fullmatch(canonical,reference):known.add(reference)
        handles=value.get('inspectionSessions',[])
        for handle in handles if isinstance(handles,list) else []:
            reference=handle.get('session_id') if isinstance(handle,dict) else None
            if isinstance(reference,str) and re.fullmatch(canonical,reference):known.add(reference)
    if not known:return None
    separators='-\u2010\u2011\u2012\u2013\u2014\u2212\ufe63\uff0d'
    pattern=r'\b[0-9a-f]{8}(?:['+separators+r'][0-9a-f]{4}){3}['+separators+r'][0-9a-f]{12}\b'
    translate=str.maketrans({separator:'-' for separator in separators})
    incorrect=[];references=set()
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        if re.search(r'\b(?:example|invalid|malformed|incorrect|not\s+(?:a\s+)?(?:valid|exact)|do\s+not\s+use)\b',sentence,re.I):continue
        for match in re.finditer(pattern,sentence,re.I):
            reported=match.group();normal=reported.translate(translate).lower()
            if normal in known and reported!=normal:
                incorrect.append(reported);references.add(normal)
    if not incorrect:return None
    return dict(check=dict(kind='network_reference_claim'),status='failed',incorrectReferences=sorted(set(incorrect)),canonicalReferences=sorted(references),error='Reported scanner references changed punctuation or case. Copy the exact recorded IDs in code spans; tool arguments are never normalised or repaired.')


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
            if re.search(label+r"\s+(?:is\s+)?(?:(?:currently|presently)\s+)?(?:disabled|not\s+enabled)\b",sentence,re.I) or re.search(r"\b(?:not|doesn't|does\s+not)\s+have\s+(?:the\s+)?"+label+r'\s+enabled\b',sentence,re.I):contradictions.append(name)
    if not contradictions:return None
    return dict(check=dict(kind='tool_scope_claim'),status='failed',availableTools=sorted(set(contradictions)),error='These named native tools are enabled in the current controller scope. Installation, readiness and action approval remain separate; do not claim that an available adapter is disabled. Use its native schema or report the actual readiness/review error.')


def execution_claim(task):
    """Reject explicit scan completion claims after only unsuccessful attempts.

    Restricted to current-task native scanner checkpoints. A completed empty
    scan is still completion; this check does not reinterpret its port states.
    """
    attempts=[c for c in task.get('checkpoints',[]) if c.get('name') in ('network_discover','network_scan','network_read')]
    if not attempts:return None
    for checkpoint in attempts:
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if checkpoint.get('status')=='finished' and isinstance(value,dict) and not value.get('error') and value.get('state')=='completed' and value.get('exitCode') in (None,0):return None
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        # A cancelled invocation records requested ports, not a completed
        # per-port probe ledger. Table headings can make the same unsupported
        # claim as prose even when another paragraph admits partial coverage.
        if re.search(r'\bports\s+(?:examined|tested|probed)\s*\*?\*?\s*\|',sentence,re.I) and not re.search(r'\b(?:unknown|undetermined|not established|not recorded)\b|examinedPortCount\s*:\s*null',sentence,re.I):
            return dict(check=dict(kind='network_execution_claim'),status='failed',checkpointIds=[c['id'] for c in attempts],error='Requested invocation ports do not establish which ports were examined before cancellation. No completed per-port probe ledger is retained. Describe requested coverage separately and mark actual examined coverage unknown.')
        if re.search(r'\bno\s+ports?\s+(?:(?:could|would)\s+have\s+been|(?:was|were))\s+(?:tested|examined|probed)\b|\bbefore\s+any\s+probes?\s+(?:finished|completed)\b',sentence,re.I) and not re.search(r'\b(?:unknown|whether|cannot establish|cannot say)\b',sentence,re.I):
            return dict(check=dict(kind='network_execution_claim'),status='failed',checkpointIds=[c['id'] for c in attempts],error='Cancelled scan evidence has no per-port completion ledger. Elapsed duration or configured timeouts cannot prove that zero ports were examined. Report actual examined coverage as unknown.')
        if re.search(r"\b(?:not|never|unable|cannot|can't|failed|error|declined|stopped|halted|cancelled|running|unfinished|incomplete|pending|if|whether|would|could|example|historical|previous|earlier)\b",sentence,re.I):continue
        if re.search(r'\b(?:no|neither)\s+(?:(?:native|scanner|network)\s+)?(?:scan|discovery|inspection)\b|\b(?:returned|produced)\s+no\s+(?:results|evidence|output)\b',sentence,re.I):continue
        if re.search(r'\b(?:returned|produced)\s+no\s+(?:warnings|errors)\b',sentence,re.I) and not re.search(r'\b(?:completed|finished|scanned|inspected)\b',sentence,re.I):continue
        if re.search(r'\b(?:scan|discovery|inspection)\b.{0,100}\b(?:completed|finished|found|observed|returned|produced)\b|\b(?:I|we)\s+(?:have\s+)?(?:scanned|inspected)\b|\b(?:complete|actual|retained|verified)\s+(?:Nmap\s+)?XML\b',sentence,re.I):
            return dict(check=dict(kind='network_execution_claim'),status='failed',checkpointIds=[c['id'] for c in attempts],error='No current-task native scanner attempt completed successfully. Do not describe completed scans, observed port results or retained XML evidence. Report the actual failed or unfinished attempt; do not replay an action to justify this answer.')
    return None


def coverage_claim(task):
    """A completed discovery is not a per-port probe-completion ledger."""
    sources=[]
    for checkpoint in task.get('checkpoints',[]):
        if checkpoint.get('name')!='network_read' or checkpoint.get('status')!='finished':continue
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict):continue
        structured=value.get('structuredResult',{})
        detail=structured.get('coverageDetail',{}) if isinstance(structured,dict) else {}
        if isinstance(structured,dict) and structured.get('scanner')=='RustScan' and isinstance(detail,dict) and detail.get('examinedPortCount','absent') is None:sources.append(value.get('session_id'))
    if not sources:return None
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        if re.search(r'\b(?:did|does)\s+not\s+(?:finish|complete)\s+(?:probing|testing|examining)\s+(?:all|every)\b',sentence,re.I) and not re.search(r'\b(?:whether|unknown|cannot|example|historical)\b',sentence,re.I):
            return dict(check=dict(kind='network_coverage_claim'),status='failed',sourceSessions=sources,error='A stopped run or partial coverage label does not establish whether zero, some or all requested probes completed. The actual examined count is unknown without a probe-completion ledger; report termination without inferring probe completion.')
        if re.search(r"\b(?:unknown|which|whether|not|cannot|can't|never|example|historical|inspection|nmap)\b",sentence,re.I):continue
        if re.search(r'\b(?:single|all|every|\d+)\s+(?:(?:requested|selected|TCP)\s+)?ports?\s+(?:was|were|have been|has been)\s+(?:examined|tested|probed)\b',sentence,re.I):
            return dict(check=dict(kind='network_coverage_claim'),status='failed',sourceSessions=sources,error='Discovery records requested coverage and observed open endpoints, not a completed per-port probe ledger. Even after a completed empty run, the actual examined count remains unknown; do not assert that requested ports were examined.')
    return None


def evidence_invocation_claim(task):
    """Check explicit invocation option claims against the retained argv.

    Controller presets are not CLI switches. This covers named long options
    in invocation prose, not arbitrary examples or all command semantics.
    """
    options=set()
    for checkpoint in task.get('checkpoints',[]):
        if checkpoint.get('status')!='finished' or checkpoint.get('name')!='network_read':continue
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict) or value.get('error'):continue
        structured=value.get('structuredResult')
        if not isinstance(structured,dict):continue
        invocation=structured.get('invocation')
        if not isinstance(invocation,dict):continue
        argv=invocation.get('argv',[])
        if isinstance(argv,list):options.update(a for a in argv if isinstance(a,str) and re.fullmatch(r'--[a-z][a-z0-9-]*',a))
    if not options:return None
    invalid=set()
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        if not re.search(r'\b(?:invocation|command[- ]line|executed|arguments|parameters)\b',sentence,re.I):continue
        if re.search(r"\b(?:not|never|example|illustrative|hypothetical|previous|historical)\b",sentence,re.I):continue
        invalid.update(flag for flag in re.findall(r'--[a-z][a-z0-9-]*',sentence) if flag not in options)
    if not invalid:return None
    return dict(check=dict(kind='network_invocation_claim'),status='failed',unsupportedOptions=sorted(invalid),actualOptions=sorted(options),error='These claimed invocation options are absent from retained argv. Describe controller metadata separately; copy executable options only from actual argv.')


def evidence_hash_claim(task):
    """Check explicitly named output hashes against retained evidence metadata.

    Empty bytes have a real SHA-256 digest, not an all-zero digest. This covers
    explicit stdout/stderr hash claims, not arbitrary factual model prose.
    """
    hashes={};inspection_hashes=set();source_hashes=set()
    for checkpoint in task.get('checkpoints',[]):
        if checkpoint.get('status')!='finished' or checkpoint.get('name') not in ('network_read','network_scan'):continue
        try:value=json.loads(checkpoint.get('result',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict) or value.get('error'):continue
        evidence=value.get('evidence',{})
        source_digest=value.get('sourceResultSha256')
        if checkpoint.get('name')=='network_scan' and isinstance(source_digest,str) and re.fullmatch(r'[0-9a-f]{64}',source_digest):
            source_hashes.add(source_digest)
            for item in evidence if isinstance(evidence,list) else [evidence]:
                digest=item.get('stdoutSha256') if isinstance(item,dict) else None
                if isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest):inspection_hashes.add(digest)
        for item in evidence if isinstance(evidence,list) else [evidence]:
            for label in ('stdout','stderr'):
                digest=item.get(label+'Sha256') if isinstance(item,dict) else None
                if isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest):hashes.setdefault(label,set()).add(digest)
    if not hashes and not inspection_hashes:return None
    errors=[]
    for sentence in re.split(r'[.!?\n]',task.get('result','')):
        if inspection_hashes and re.search(r'\binspection\b.{0,60}\b(?:sha|hash|digest)\b',sentence,re.I) and not re.search(r'\b(?:source|discovery|not|example)\b|sourceResultSha256',sentence,re.I):
            for claimed in re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',sentence,re.I):
                if claimed.lower() in source_hashes and claimed.lower() not in inspection_hashes:errors.append('The discovery sourceResultSha256 was labelled as an inspection digest; inspection XML has its own stdout digest')
        if re.search(r'\b(?:stdout|stderr)Sha256\b.{0,100}\b(?:are|is)\s+empty\b',sentence,re.I) and not re.search(r'\b(?:not|cannot|example|historical)\b',sentence,re.I):
            errors.append('Retained output SHA-256 fields contain digests, not empty values')
        if not re.search(r'\b(?:sha[- ]?256|hash|digest)\b',sentence,re.I):continue
        if re.search(r"\b(?:not|never|cannot|can't|example|historical|previous)\b",sentence,re.I):continue
        labels=[label for label in hashes if re.search(r'\b'+label+r'\b',sentence,re.I)]
        expected=set().union(*(hashes[label] for label in labels or hashes))
        if re.search(r'\b(?:zero|all[- ]zero)\s+(?:hash|digest)\b',sentence,re.I) and '0'*64 not in expected:
            errors.append('Empty output does not have an all-zero SHA-256 digest')
        if labels:
            for claimed in re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',sentence,re.I):
                if claimed.lower() not in expected:errors.append('Named output digest differs from retained evidence')
    if not errors:return None
    return dict(check=dict(kind='network_evidence_hash_claim'),status='failed',errors=sorted(set(errors)),
                actualHashes={**{label:sorted(values) for label,values in hashes.items()},**({'inspectionStdout':sorted(inspection_hashes)} if inspection_hashes else {})},
                error='Copy the retained stdout/stderr SHA-256 exactly or omit a digest claim. An empty file has the SHA-256 of empty bytes, not the zero hash.')


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
        reported_denial=re.search(r'\bnot\s+reported\s+(?:as\s+)?open\b',sentence,re.I) and not re.search(r'\b(?:if|whether|example|historical|previous)\b',sentence,re.I)
        denies=bool(re.search(r'\bneither\b.*\bopen\b|\bnot\s+open\b',sentence,re.I) or reported_denial)
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
    for match in re.finditer(r'```([^\n`]*)\n(.*?)```',answer,re.I|re.S):
        language=match.group(1).strip().lower();body=match.group(2)
        if language!='xml' and (language or not re.match(r'\s*<(?:\?xml\b|nmaprun\b|!DOCTYPE\s+nmaprun\b)',body,re.I)):continue
        context=answer[max(0,match.start()-240):match.start()]
        if re.search(r'\b(?:example|illustrative|schematic|simplified)\b',context,re.I):continue
        if not re.search(r'\b(?:output|excerpt|verbatim|verified)\b',context,re.I):continue
        quote=re.sub(r'\s+',' ',body.strip())
        if quote and not any(quote in output for output in outputs):invalid.append(hashlib.sha256(body.encode()).hexdigest())
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
        if row.get('check',{}).get('kind')=='network_coverage_claim' and row['status']=='failed':
            lines.append('Requested coverage and observed endpoints do not establish the actual examined-port count. It remains unknown without a completed per-port probe ledger.')
        if row.get('check',{}).get('kind')=='network_reference_claim' and row['status']=='failed':
            lines.append('Canonical source session references: '+', '.join('`'+reference+'`' for reference in row['canonicalReferences'])+'. Copy these exactly; no tool argument was repaired or retried.')
        if row.get('check',{}).get('kind')=='network_invocation_claim' and row['status']=='failed':
            lines.append('Retained executable options: '+', '.join(row['actualOptions'])+'. Controller presets are separate metadata.')
        if row.get('check',{}).get('kind')=='network_evidence_hash_claim' and row['status']=='failed':
            lines.append('Retained output SHA-256 digests: '+json.dumps(row['actualHashes'],sort_keys=True)+'.')
        if row.get('check',{}).get('kind')=='tool_scope_claim' and row['status']=='failed':
            lines.append('The native tool schema is enabled for this task: '+', '.join(row['availableTools'])+'. This does not establish executable readiness or action approval. The requested action still needs completed tool evidence.')
    if any(r.get('check',{}).get('kind')=='requested_discovery_inspection' and r['status']=='failed' for r in task.get('verification',{}).get('checks',[])):lines.append('The requested source-bound inspection did not complete. Discovery alone does not finish that task.')
    return '\n'.join(lines)
