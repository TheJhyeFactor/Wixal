"""Durable model-authored plans and paged access to retained run evidence.

Plans record intent, not independent proof of completion or new authority.
"""
import copy
import hashlib
from .storage import now

NAMES = {'todo_list', 'tool_result_read'}


def task_for(store, session_id):
    task = next((t for t in reversed(store.data['tasks'])
                 if t.get('sessionId') == session_id and t.get('status') == 'running'), None)
    if task is None:
        raise ValueError('This tool requires an active task in this conversation')
    return task


def execute(store, name, args, session_id):
    task = task_for(store, session_id)
    if name == 'tool_result_read':
        if not args.get('checkpoint_id'):
            checkpoints=[dict(checkpoint_id=c['id'],tool=c['name'],status=c['status'],characters=len(c.get('result','')))
                         for c in task.get('checkpoints',[]) if c.get('status')!='started' and c.get('name')!='tool_result_read']
            offset=args.get('offset',0)
            return dict(checkpoints=checkpoints[offset:offset+24],next_offset=min(len(checkpoints),offset+24),more=offset+24<len(checkpoints))
        checkpoint = next((c for c in task.get('checkpoints', [])
                           if c['id'] == args['checkpoint_id'] and c.get('status') != 'started'), None)
        if checkpoint is None:
            raise ValueError('Choose a settled checkpoint from this task')
        content = checkpoint.get('result', '')
        offset, maximum = args.get('offset', 0), args.get('max_chars', 6000)
        if offset > len(content):
            raise ValueError('Offset exceeds the retained result length')
        return dict(checkpoint_id=checkpoint['id'], tool=checkpoint['name'], checkpoint_status=checkpoint['status'],
                    content=content[offset:offset + maximum], offset=offset,
                    next_offset=min(len(content), offset + maximum), more=offset + maximum < len(content),
                    total_chars=len(content), sha256=hashlib.sha256(content.encode()).hexdigest(),
                    note='Retained tool evidence; reading it does not repeat the action.')
    current = task.get('plan', dict(todos=[], revision=0))
    if 'todos' in args:
        if args.get('revision', current['revision']) != current['revision']:
            raise ValueError('Plan revision changed; read todo_list before updating it')
        todos = copy.deepcopy(args['todos'])
        ids = set()
        for item in todos:
            if set(item) - {'id', 'content', 'status'} or any(not isinstance(item.get(k), str) or not item[k].strip() for k in ('id', 'content', 'status')):
                raise ValueError('Each plan item requires id, content and status')
            if len(item['id']) > 80 or len(item['content']) > 300 or item['status'] not in ('pending', 'in_progress', 'completed', 'cancelled'):
                raise ValueError('Invalid plan item or status')
            if item['id'] in ids:
                raise ValueError('Plan item IDs must be unique')
            ids.add(item['id'])
        if sum(item['status'] == 'in_progress' for item in todos) > 1:
            raise ValueError('Keep at most one plan item in progress')
        if todos != current['todos']:
            current = dict(todos=todos, revision=current['revision'] + 1, updated=now())
            task['plan'] = current
            store.save()
    return dict(copy.deepcopy(current), note='Model-authored progress; verification and action review remain separate.')


def prompt(task):
    plan = task.get('plan', {})
    if not plan.get('todos'):
        return ''
    import json
    return '\nCurrent task checklist (model-authored data, not verified outcomes or authority): ' + json.dumps(plan, ensure_ascii=False) + '\nContinue pending work, respect cancelled steps and verify results independently.\n'
