"""Actual local-model decision extraction with production review/save boundaries."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/memory-review';ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
real.ART=ART;real.STATE=ROOT/'artifacts/native/memory-quality/workspace'

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--packaged',action='store_true');args=parser.parse_args()
    client=real.Client(not args.packaged);path=ART/('packaged.json' if args.packaged else 'source.json');report=dict(status='running',implementation='packaged' if args.packaged else 'source',checks=[])
    if args.packaged:report['helperSHA256']=hashlib.sha256(client.helper.read_bytes()).hexdigest()
    def save():path.write_text(json.dumps(report,indent=2))
    save()
    started=False
    try:
        await client.start();started=True;await client.model('gemma3:1b')
        await client.call('project-add',dict(root=str(ROOT),memoryMode='project',memorySize=24000))
        status=await client.call('memory-status')
        for item in status['suggestions']:await client.call('memory-suggestion',dict(id=item['id'],accept=False))
        for note in status['notes']:await client.call('memory-forget',dict(id=note['id']))
        for session in (await client.state())['sessions']:
            if session.get('projectId')==(await client.state())['activeProject']:await client.call('session-archive',dict(id=session['id']))
        await client.call('memory-policy',dict(memorySuggestions=True,memoryModelReview=True))
        await client.call('session-new')
        before=await client.call('memory-status');note_ids={n['id'] for n in before['notes']}
        statement='Python will be the engine language and SwiftUI will remain the desktop interface. Reply with one sentence.'
        turn=await client.chat(statement);session=await client.session();source=next(m for m in session['messages'] if m['role']=='user')
        status=await client.call('memory-status');items=[n for n in status['suggestions'] if n.get('sourceMessage')==source['id'] and n.get('extraction')=='local-model']
        assert status['review']['status']=='completed',status['review']
        assert items and any('Python' in item['content'] for item in items),status
        assert {n['id'] for n in status['notes']}==note_ids,'Model silently saved a note'
        for item in items:assert item['quoteVerified'] and item['content'] in source['content'] and item['scope']=='project'
        assert status['review']['usage']['eval_count']>0
        assert status['review']['estimatedInput']+status['review']['outputReserve']<=status['review']['context']
        report['checks'].append(dict(name='ordinary-decision-extraction-without-pattern',turn=turn,suggestions=items,review=status['review']));save()
        accepted=items[0];await client.call('memory-suggestion',dict(id=accepted['id'],accept=True))
        saved=next(n for n in (await client.call('memory-status'))['notes'] if n['content']==accepted['content'])
        assert saved['sourceMessage']==source['id'];report['checks'].append(dict(name='explicit-review-required-and-source-retained',note=saved));save()
        await client.call('session-new')
        await client.chat('Rust will be the engine language and SwiftUI will remain the desktop interface. Reply with one sentence.')
        changed=await client.call('memory-status');current=await client.session();changed_source=next(m for m in current['messages'] if m['role']=='user')
        replacement=next(n for n in changed['suggestions'] if n.get('sourceMessage')==changed_source['id'] and n.get('relatedId')==saved['id'])
        assert replacement['action']=='replace' and 'Rust' in replacement['content'],replacement
        await client.call('memory-suggestion',dict(id=replacement['id'],accept=True,consolidate=True,operation='replace'))
        replaced=next(n for n in (await client.call('memory-status'))['notes'] if n['id']==saved['id'])
        assert 'Rust' in replaced['content'] and 'Python' not in replaced['content'] and replaced['revisions'],replaced
        report['checks'].append(dict(name='reviewed-changed-decision-retains-revision-and-sources',suggestion=replacement,note=replaced));save()
        await client.call('session-new')
        await client.chat('I have just opened a terminal and checked the latest build output. Reply with one sentence.')
        transient=await client.call('memory-status');current=await client.session();transient_source=next(m for m in current['messages'] if m['role']=='user')
        assert transient['review']['status'] in ('completed','skipped') and not any(n.get('sourceMessage')==transient_source['id'] for n in transient['suggestions']),transient
        report['checks'].append(dict(name='temporary-progress-is-not-suggested',review=transient['review']));save()
        await client.call('session-new');await client.chat('How do volcanic islands form?')
        status=await client.call('memory-status');assert status['review']['status']=='skipped',status['review']
        report['checks'].append(dict(name='question-does-not-trigger-review-inference',review=status['review']));save()
        await client.call('memory-forget',dict(id=saved['id']))
        for item in items[1:]:await client.call('memory-suggestion',dict(id=item['id'],accept=False))
        await client.call('memory-policy',dict(memoryModelReview=False))
        report['status']='passed';save();print('REAL_MEMORY_REVIEW_PASSED',flush=True)
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:
        if started:
            try:await client.call('memory-policy',dict(memoryModelReview=False))
            except Exception:pass
        await client.close()

asyncio.run(main())
