"""Model-facing scanner evidence views. Stored tool results are never modified."""
import json


def port_ranges(ports):
    """Exact compact representation of requested ports, not probe completion."""
    ranges=[]
    for port in sorted(set(ports)):
        if ranges and port==ranges[-1][1]+1:ranges[-1][1]=port
        else:ranges.append([port,port])
    return ','.join(str(a) if a==b else f'{a}-{b}' for a,b in ranges)


def model_view(name, content):
    if name not in ('network_read','network_scan','network_discover'):return content
    try:value=json.loads(content)
    except (ValueError,TypeError):return content
    if not isinstance(value,dict):return content
    structured=value.get('structuredResult',{})
    if not (structured.get('scanner')=='RustScan' or value.get('sourceSessionId') or value.get('evidenceReport') or
            name=='network_read' and value.get('session_id') and value.get('evidence')):return content
    def view(result):
        source=result.get('structuredResult',{})
        result_view={k:result[k] for k in ('session_id','state','exitCode','reason','error','sourceSessionId','sourceRunId','sourceResultSha256','skipped') if k in result}
        if source:
            result_view['structuredResult']={k:source[k] for k in ('scanner','handoffEligible','resultSha256','coverage','coverageMeaning','evidenceStatus','termination') if k in source}
            invocation=source.get('invocation',{})
            request={k:invocation[k] for k in ('target','coverage','argv') if k in invocation}
            if len(json.dumps(request.get('argv',[])))>2000:
                request.pop('argv',None);request['argvOmitted']=True
            ports=invocation.get('ports',[])
            if ports:
                exact=port_ranges(ports)
                request.update(requestedPortCount=len(ports),requestedPorts=exact if len(exact)<=1000 else None,
                               requestedPortsOmitted=len(exact)>1000)
            result_view['structuredResult']['invocation']=request
            if 'coverageDetail' in source:result_view['structuredResult']['coverageDetail']=source['coverageDetail']
        services=source.get('services',result.get('services',[]))
        result_view['services']=[{k:s[k] for k in ('host','port','protocol','state','service','product','version') if k in s} for s in services[:24]]
        result_view['omittedServices']=max(0,len(services)-24)
        if 'evidenceReport' in result:
            reports=result['evidenceReport'];single=isinstance(reports,dict)
            rows=[reports] if single else reports
            compact=[]
            for row in rows[:2]:
                row=dict(row);endpoints=row.get('observedEndpoints',[])
                row.update(observedEndpoints=endpoints[:24],omittedEndpoints=max(0,len(endpoints)-24))
                compact.append(row)
            result_view['evidenceReport']=compact[0] if single else compact
        result_view['inspectionSessions']=result.get('inspectionSessions',[])[:8]
        evidence=result.get('evidence',{})
        rows=evidence if isinstance(evidence,list) else [evidence]
        result_view['evidence']=[{k:r[k] for k in ('stdoutSha256','stderrSha256','incomplete') if k in r} for r in rows[:8]]
        output=result.get('output','')
        if output:
            excerpt=output[:1600]
            result_view.update(output=excerpt,outputExcerpt=len(excerpt)<len(output))
            if result.get('session_id'):
                offset=result.get('offset',0)
                result_view['outputRange']=dict(offset=offset,next_offset=offset+len(excerpt.encode('utf-16-le'))//2,
                                               more=len(excerpt)<len(output) or result.get('more',False))
        if isinstance(result.get('discovery'),dict):result_view['discovery']=view(result['discovery'])
        result_view['modelView']=True
        result_view['fullResultRetained']=True
        return result_view
    return json.dumps(view(value),ensure_ascii=False)


def fit_view(value, limit):
    """Keep essential scanner facts readable when even the normal view is too big."""
    essential={k:value[k] for k in ('session_id','state','exitCode','sourceSessionId','skipped') if k in value}
    source=value.get('structuredResult',{})
    for key in ('coverage','evidenceStatus'):
        if key in source:essential[key]=source[key]
    coverage=source.get('coverageDetail',{})
    if coverage:
        essential['coverageDetail']={k:coverage[k] for k in ('requestedPortCount','examinedPortCount') if k in coverage}
    if 'handoffEligible' in source:essential['handoffEligible']=source['handoffEligible']
    essential.update(modelView=True,fullResultRetained=True,excerpt=True)
    # Whole endpoint records only. Explicit omission counts prevent an excerpt
    # from looking like an empty scan or a complete set of observations.
    services=value.get('services',[])
    essential.update(services=[],omittedServices=len(services)+value.get('omittedServices',0))
    def fits(candidate):return len(json.dumps(candidate,ensure_ascii=False))<=limit
    for entry in services:
        candidate=dict(essential,services=essential['services']+[entry],omittedServices=essential['omittedServices']-1)
        if not fits(candidate):break
        essential=candidate
    for key in ('evidence','inspectionSessions','evidenceReport','discovery'):
        if key in value and fits(dict(essential,**{key:value[key]})):essential[key]=value[key]
    return json.dumps(essential,ensure_ascii=False) if fits(essential) else None
