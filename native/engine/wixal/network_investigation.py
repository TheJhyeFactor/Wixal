"""Bounded discovery-to-inspection execution and reports from retained evidence.

No model output is used to bind the second stage or construct factual fields.
Both stages use ordinary tool dispatch, authority, review and evidence storage.
"""
import asyncio
import json
import time
from .storage import identity, now


def evidence_views(task):
    """Read-only views of real stage receipts; never insert model checkpoints."""
    for checkpoint in task.get('checkpoints', []):
        stages=checkpoint.get('controllerStages',[]) if checkpoint.get('name')=='network_scan' and checkpoint.get('arguments',{}).get('discover_first') else []
        if stages:
            yield from (stage for stage in stages if stage.get('origin')=='controller_stage' and stage.get('name') in ('network_discover','network_read','network_scan'))
            continue
        if checkpoint.get('name') == 'network_scan' and checkpoint.get('status') == 'finished':
            try:
                result = json.loads(checkpoint.get('result', ''))
            except (ValueError, TypeError):
                result = {}
            discovery = result.get('discovery') if isinstance(result, dict) else None
            if isinstance(discovery, dict) and isinstance(discovery.get('session_id'),str):
                yield dict(checkpoint, name='network_read', origin='controller_stage',
                           result=json.dumps(discovery), arguments=dict(session_id=discovery['session_id']))
        yield checkpoint


def report(result):
    """Lossless factual distinctions, including unknown coverage and empty results."""
    structured = result.get('structuredResult', result)
    discovery = structured.get('scanner') == 'RustScan'
    coverage = structured.get('coverageDetail', {})
    return dict(
        stage='discovery' if discovery else 'inspection',
        state=result.get('state'), exitCode=result.get('exitCode'),
        sessionId=result.get('session_id'), sourceSessionId=result.get('sourceSessionId'),
        requestedPortCount=coverage.get('requestedPortCount') if discovery else None,
        examinedPortCount=coverage.get('examinedPortCount') if discovery else None,
        observedEndpoints=[dict(host=s['host'], port=int(s['port']), state=s['state'])
                           for s in structured.get('services', [])],
        skipped=bool(result.get('skipped')),
        limitation=coverage.get('limitation') if discovery else
            'Inspection observations apply only to the source-bound addresses and ports. They do not establish vulnerability or safety.',
    )


async def run(tools, args, session, checkpoint=None):
    if args.get('source_run_id') or args.get('source_session_id'):
        raise ValueError('discover_first cannot also supply an existing discovery source')
    if args.get('profile', 'services') == 'discovery':
        raise ValueError('discover_first requires an inspection profile; use network_discover for discovery alone')
    if checkpoint is not None:
        task=next((task for task in tools.store.data['tasks'] if any(c is checkpoint for c in task.get('checkpoints',[]))),None)
        previous=next((c for c in (task or {}).get('checkpoints',[]) if c is not checkpoint and c.get('name')=='network_scan' and c.get('arguments')==args and c.get('controllerStages')),None)
        if previous:
            raise ValueError('This investigation already started in this task. Inspect retained controllerStages and continue from its source_session_id; do not restart discovery.')
    async def dispatch(name,arguments):
        receipt=dict(id=identity(),name=name,arguments=arguments,status='started',origin='controller_stage',created=now(),sessionId=session,projectId=(tools.store.project() or {}).get('id'))
        if checkpoint is not None:
            checkpoint.setdefault('controllerStages',[]).append(receipt);tools.store.save()
        try:
            value=await tools.execute(name,arguments,session)
            receipt.update(status='finished',result=json.dumps(value),finished=now())
            return value
        except BaseException as error:
            receipt.update(status='interrupted' if not isinstance(error,Exception) else 'error',result=json.dumps(dict(error=str(error))),finished=now())
            raise
        finally:
            if checkpoint is not None:tools.store.save()
    deadline = time.monotonic() + args.get('timeout_seconds', 180)
    # Validate both switches before starting either stage. Normal dispatch below
    # still enforces read-only profiles, target restrictions and action review.
    from .agent_context import available_names
    if 'network_discover' not in available_names(tools, tools.store):
        raise ValueError('network_discover is switched off or outside this agent task boundary')
    try:
        started = await dispatch('network_discover',
            {key: args[key] for key in ('target', 'ports', 'timeout_seconds') if key in args})
    except ValueError as error:
        if str(error).startswith('User declined'):return str(error)
        raise
    await tools.jobs[started['session_id']]['collector']
    discovery = await dispatch('network_read', dict(session_id=started['session_id'], wait_ms=0, max_chars=100000))
    structured = discovery.get('structuredResult', {})
    if discovery['state'] != 'completed' or not structured.get('handoffEligible'):
        return dict(state='failed', error='Discovery did not produce eligible completed evidence; inspection was not started.',
                    discovery=discovery, services=[], evidenceReport=[report(discovery)])
    remaining = int(deadline - time.monotonic())
    if remaining < 1:
        return dict(state='failed', error='Shared investigation deadline has insufficient time for inspection.',
                    discovery=discovery, services=[], evidenceReport=[report(discovery)])
    try:
        async with asyncio.timeout(deadline-time.monotonic()):
            inspection = await dispatch('network_scan', dict(target=args['target'],
                source_session_id=discovery['session_id'], profile=args.get('profile', 'services'),
                timeout_seconds=max(10,remaining)))
    except ValueError as error:
        if str(error).startswith('User declined'):return str(error)
        raise
    return dict(inspection, discovery=discovery, evidenceReport=[report(discovery), report(inspection)])
