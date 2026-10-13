"""Operator-enrolled local log monitoring, inspired by Decepticon Blue Cell.

Read-only collection; incidents are leads. Coverage and collector loss are explicit.
"""
import asyncio
import hashlib
import json
import os
import re
from . import engagement_evidence as evidence
from .cyber_reports import clean
from .engagement_policy import text
from .storage import now
from .tools import safe_path

RULES = {'server_error':re.compile(r'\b(?:exception|traceback|panic|fatal)\b',re.I),
         'authentication_failure':re.compile(r'\b(?:authentication failed|invalid credentials|access denied|unauthorized)\b',re.I)}


class Sensors:
    def __init__(self,manager):
        self.manager=manager;self.tasks={}
        for row in manager.store.data['securitySensors']:
            if row.get('status')=='monitoring':row.update(status='paused',gap='Engine restarted; explicitly review and resume collection')

    def snapshot(self,engagement):
        return dict(sources=self.manager.rows('securitySensors',engagement),incidents=self.manager.rows('securityIncidents',engagement)[-100:],
                    limitation='Only enrolled local files are observed. Incidents are unverified leads; no blocking or remediation is performed.')

    def source(self,engagement,identifier):return self.manager.record('securitySensors',identifier,engagement)

    def live(self,engagement,row):
        if row.get('archived'):raise ValueError('Sensor is archived; enroll a new source')
        if (self.manager.store.project() or {}).get('id')!=engagement['projectId']:raise ValueError('Sensor paused because the selected project changed')
        if engagement['status']!='running' or not engagement.get('approval') or row['scopeRevision']!=engagement['scopeRevision']:
            raise ValueError('Sensor requires an approved current-scope running engagement')
        scope=self.manager.scope(engagement)
        if not scope['starts']<=now()<scope['ends']:raise ValueError('Sensor testing window expired')
        if engagement['approval']['digest']!=evidence.digest(scope):raise ValueError('Sensor scope identity changed')

    async def enroll(self,engagement,params):
        if len([r for r in self.manager.rows('securitySensors',engagement) if not r.get('archived')])>=16:raise ValueError('Sixteen log sources are already enrolled for this engagement')
        path=text(params.get('path'),'Project-relative JSONL/text log path',1000)
        source=safe_path(self.manager.store.project()['root'],path)
        if not source.is_file():raise ValueError('Choose an existing regular log file')
        target=self.manager.record('securityTargets',params.get('targetId'),engagement)
        revision=engagement['scopeRevision'];info=source.stat()
        if not await self.manager.workspace.service.ask('review',dict(name='cyber_sensor_enroll',path=path,targetId=target['id'],scopeRevision=revision,access='Read-only local log collection; contents may contain client data')):raise ValueError('Sensor enrollment was not approved')
        if engagement['scopeRevision']!=revision or engagement['status'] in ('completed','closed_incomplete','cancelled'):raise ValueError('Engagement changed during sensor review')
        row=self.manager.add('securitySensors',engagement,targetId=target['id'],path=path,root=self.manager.store.project()['root'],
                             scopeRevision=revision,status='paused',offset=0,device=info.st_dev,inode=info.st_ino,
                             delivered=0,malformed=0,oversized=0,bytes=0,coverageStart=None,coverageEnd=None,gap='Not started',
                             rules=list(RULES)+['http_server_error'],suppressedIncidentRecords=0)
        self.manager.event(engagement,'sensor_enrolled',dict(sensorId=row['id'],path=path));return row

    def collect(self,engagement,row):
        self.live(engagement,row)
        if row['bytes']>=16*1024*1024:
            row.update(status='paused',gap='Sixteen MB collection budget reached; retain and review this source before further collection')
            return row
        source=safe_path(row['root'],row['path']);info=source.stat()
        if not source.is_file() or (info.st_dev,info.st_ino)!=(row['device'],row['inode']) or info.st_size<row['offset']:
            row.update(status='paused',gap='Log rotated or truncated; enroll the new file explicitly')
            return row
        if info.st_size==row['offset']:
            row['lastChecked']=now();return row
        with source.open('rb') as f:
            os_info=os.fstat(f.fileno())
            if (os_info.st_dev,os_info.st_ino)!=(row['device'],row['inode']):raise ValueError('Sensor file identity changed')
            f.seek(row['offset']);raw=f.read(1024*1024)
        end=raw.rfind(b'\n')+1
        if not end:
            if len(raw)==1024*1024:row.update(status='paused',gap='Oversized or unterminated log record; no bytes skipped',oversized=row['oversized']+1)
            return row
        batch=raw[:end];lines=batch.splitlines();events=[];incidents=[];malformed=0
        for index,line in enumerate(lines):
            if not line.strip():continue
            if len(line)>65536:malformed+=1;continue
            try:
                content=line.decode('utf-8',errors='strict')
                item=json.loads(content) if content.lstrip().startswith('{') else dict(message=content)
                if not isinstance(item,dict):raise ValueError('Log record must be an object')
            except (ValueError,UnicodeError):malformed+=1;continue
            message=str(item.get('message',item.get('msg',content)))
            sample=clean(message)[:1000]
            event=dict(line=index,observed=now(),message=sample,sourceTime=clean(item.get('timestamp',item.get('time'))))
            events.append(event)
            enabled=row.get('rules',list(RULES)+['http_server_error'])
            matched=[name for name,pattern in RULES.items() if name in enabled and pattern.search(message)]
            status=item.get('status',item.get('status_code'))
            if type(status) is int and 500<=status<=599 and 'http_server_error' in enabled:matched.append('http_server_error')
            if matched:incidents.append(dict(rules=matched,sample=sample,line=index))
        if len(events)>2000:row.update(status='paused',gap='Batch exceeds 2,000 events; no bytes skipped');return row
        retained=evidence.retain(self.manager,engagement,dict(sensorId=row['id'],targetId=row['targetId'],scopeRevision=row['scopeRevision'],offset=row['offset'],
                   rawSha256=hashlib.sha256(batch).hexdigest(),rawText=batch.decode('utf-8',errors='replace'),events=events,
                   coverage='File byte range only; collection times are not source event times'), 'sensor-batch',row['id'])
        groups={}
        for item in incidents:
            key=tuple(item['rules']);group=groups.setdefault(key,dict(rules=item['rules'],sample=item['sample'],line=item['line'],count=0))
            group['count']+=1
        for item in groups.values():
            self.manager.add('securityIncidents',engagement,sensorId=row['id'],targetId=row['targetId'],scopeRevision=row['scopeRevision'],
                             evidenceId=retained['id'],status='lead',**item)
        row.update(offset=row['offset']+len(batch),delivered=row['delivered']+len(events),malformed=row['malformed']+malformed,
                   bytes=row['bytes']+len(batch),coverageStart=row['coverageStart'] or now(),coverageEnd=now(),lastEvidenceId=retained['id'],
                   gap='Malformed or oversized lines in collected range' if malformed else 'Source coverage unverified; traffic bypass and missing application events are unknown')
        self.manager.workspace.publish();return row

    async def configure(self,engagement,row,rules):
        if row.get('archived'):raise ValueError('Sensor is archived')
        if not isinstance(rules,list) or len(set(rules))!=len(rules) or any(r not in (*RULES,'http_server_error') for r in rules):
            raise ValueError('Choose distinct supported sensor rules')
        await self.stop(row);row['rules']=rules
        self.manager.event(engagement,'sensor_rules_changed',dict(sensorId=row['id'],rules=rules))
        return row

    async def archive(self,engagement,row):
        await self.stop(row);row.update(archived=now(),status='archived',gap='Collection removed; retained evidence remains available for report integrity')
        self.manager.event(engagement,'sensor_archived',dict(sensorId=row['id']))
        return row

    async def start(self,engagement,row):
        self.live(engagement,row)
        if row['id'] in self.tasks and not self.tasks[row['id']].done():return row
        if sum(not task.done() for task in self.tasks.values())>=8:raise ValueError('Eight local log monitors are already running')
        revision=engagement['scopeRevision']
        if not await self.manager.workspace.service.ask('review',dict(name='cyber_sensor_start',path=row['path'],scopeRevision=revision,seconds=600,access='Read-only collection every two seconds, bounded to ten minutes')):raise ValueError('Sensor start was not approved')
        self.live(engagement,row)
        if revision!=engagement['scopeRevision']:raise ValueError('Scope changed during review')
        row.update(status='monitoring',deadline=now()+600000)
        async def monitor():
            try:
                while row['status']=='monitoring' and now()<row['deadline']:
                    self.collect(engagement,row)
                    await asyncio.sleep(2)
            except asyncio.CancelledError:raise
            except (ValueError,OSError) as error:row['gap']=str(error)
            finally:
                row['status']='paused';self.manager.workspace.publish()
        self.tasks[row['id']]=asyncio.create_task(monitor());return row

    async def stop(self,row):
        row['status']='paused';task=self.tasks.pop(row['id'],None)
        if task:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        return row

    async def close(self):
        for row in self.manager.store.data['securitySensors']:
            if row['id'] in self.tasks:await self.stop(row)
