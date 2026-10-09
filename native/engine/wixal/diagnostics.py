"""Bounded, local-only event metadata. Never serialize arbitrary IPC payloads."""
import hashlib
import json
import logging
import logging.handlers
import os
import time
import uuid
from collections import deque
from pathlib import Path
from .storage import now


def failure_details(error):
    text = str(error).lower()
    category = 'execution_error'
    for name, terms in (
        ('unknown_tool', ('unknown tool name',)),
        ('timeout', ('timeout', 'timed out', 'deadline')),
        ('invalid_input', ('argument', 'required', 'schema', 'choose', 'unknown tool')),
        ('access_denied', ('permission', 'denied', 'outside', 'not enabled')),
        ('connection', ('connect', 'network', 'unreachable', 'resolve', 'socket')),
        ('http_error', ('http', 'status code')),
        ('interrupted', ('cancel', 'interrupt')),
    ):
        if any(term in text for term in terms):
            category = name
            break
    return dict(errorCategory=category, errorFingerprint=hashlib.sha256(str(error).encode()).hexdigest()[:16])


class PrivateRotatingHandler(logging.handlers.RotatingFileHandler):
    def _open(self):
        descriptor = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, self.mode, encoding=self.encoding)


class Diagnostics:
    def __init__(self, directory, max_bytes=2*1024*1024, backups=4):
        self.directory = Path(directory)/'logs'
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.boot = uuid.uuid4().hex
        self.sequence = 0
        self.handler = PrivateRotatingHandler(self.directory/'engine.jsonl', maxBytes=max_bytes, backupCount=backups, encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.starts = {}
        self.last_state = None
        self.write('engine-start', version=1)

    def write(self, event, **metadata):
        try:
            self.sequence += 1
            row = dict(timestamp=now(), bootId=self.boot, sequence=self.sequence, event=event, **metadata)
            record = logging.LogRecord('wixal.diagnostics', logging.INFO, '', 0, json.dumps(row, ensure_ascii=False), (), None)
            self.handler.emit(record)
        except (OSError, ValueError):
            # Diagnostics must never prevent an action or IPC response.
            pass

    def event(self, event, data, store=None):
        if not isinstance(data, dict): return
        context = dict(sessionId=store.data.get('activeSession')) if store else {}
        if event == 'state':
            sessions = [s for s in data.get('sessions', []) if s.get('id')==data.get('activeSession')]
            summary = dict(sessionId=data.get('activeSession'), sessionCount=len(data.get('sessions', [])), sessions=[dict(id=s.get('id'), messages=len(s.get('messages', [])), responses=sum(m.get('role')=='assistant' for m in s.get('messages', []))) for s in sessions], tasks=[dict(id=t.get('id'), sessionId=t.get('sessionId'), status=t.get('status'), turns=t.get('turns')) for t in data.get('tasks', [])[-100:]])
            if summary != self.last_state:
                self.last_state = summary
                self.write('state-summary', **summary)
        elif event in ('tool-start', 'tool-result'):
            identifier = data.get('id')
            if store:
                task = next((t for t in reversed(store.data.get('tasks', [])) if any(c.get('id')==identifier for c in t.get('checkpoints', []))), None)
                if task: context.update(taskId=task.get('id'), sessionId=task.get('sessionId'))
            details = dict(context, actionId=identifier, tool=data.get('name'), status=data.get('status'))
            if event == 'tool-start':
                self.starts[identifier] = time.monotonic()
                details['inputKeys'] = sorted(data.get('arguments', {})) if isinstance(data.get('arguments'), dict) else []
            else:
                started = self.starts.pop(identifier, None)
                if started is not None: details['elapsedMs'] = round((time.monotonic()-started)*1000)
                result = data.get('result', '')
                details['resultCharacters'] = len(str(result))
                try: result = json.loads(result) if isinstance(result, str) else result
                except ValueError: pass
                if isinstance(result, dict):
                    if result.get('error'): details.update(failure_details(result['error']))
                    for key in ('exitCode', 'status'):
                        if isinstance(result.get(key), int): details[key if key=='exitCode' else 'httpStatus'] = result[key]
                if details.get('errorCategory'): details['status'] = 'failed'
            self.write(event, **details)
        elif event in ('assistant-start', 'operation', 'request-closed'):
            self.write(event, **context, **{key:data[key] for key in ('taskId', 'id', 'running') if key in data})
        elif event in ('model-request', 'assistant-saved'):
            self.write(event, **{key:data[key] for key in ('taskId', 'sessionId', 'turn', 'model', 'estimatedInput', 'context', 'contentCharacters', 'thinkingCharacters', 'toolCalls', 'elapsedSeconds') if key in data})
        elif event == 'verification':
            self.write(event, **{key:data[key] for key in ('taskId', 'sessionId', 'turn', 'status', 'unresolved', 'retries') if key in data})
        elif event == 'response':
            self.write(event, requestId=data.get('id'), status='failed' if data.get('error') else 'completed', **(failure_details(data['error']) if data.get('error') else {}))
        elif event == 'host':
            self.write('host-start', **context, requestId=data.get('id'), method=data.get('method'))
        elif event == 'error':
            self.write(event, **context, **failure_details(data.get('message', '')))

    def snapshot(self, limit=200):
        # Only two segments are needed for a bounded recent view.
        rows = deque(maxlen=limit)
        for path in (self.directory/'engine.jsonl.1', self.directory/'engine.jsonl'):
            try:
                with path.open() as stream:
                    for line in stream:
                        try: rows.append(json.loads(line))
                        except ValueError: pass
            except OSError: pass
        return dict(directory=str(self.directory), events=list(rows), maxBytes=self.handler.maxBytes, retainedFiles=self.handler.backupCount+1)

    def close(self):
        self.write('engine-stop')
        self.handler.close()
