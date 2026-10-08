"""Persisted catch-up policy and optional macOS LaunchAgent execution."""
import asyncio
import hashlib
import json
import os
import plistlib
import signal
import subprocess
import sys
from pathlib import Path
from .storage import now
from .memory import owner


def due(schedule, stamp):
    if not schedule.get('enabled') or schedule.get('nextRun',stamp+1)>stamp:return None
    if schedule.get('timing') in ('Every weekday','Every day','Every Monday','Every hour'):
        from .agents import next_calendar
        following=next_calendar(schedule,schedule['nextRun'])
        missed=following<=stamp
        return dict(scheduledFor=schedule['nextRun'],missed=int(missed),skip=schedule.get('missedRunPolicy','latest')=='skip' and missed,nextRun=next_calendar(schedule,stamp))
    interval=schedule['intervalSeconds']*1000
    missed=max(0,(stamp-schedule['nextRun'])//interval)
    return dict(scheduledFor=schedule['nextRun'],missed=int(missed),skip=schedule.get('missedRunPolicy','latest')=='skip' and missed>0,
                nextRun=schedule['nextRun']+(missed+1)*interval)


async def run_due(service, background=False):
    if getattr(service,'security_workspace',None) and service.security_workspace.busy:return False
    if service.active and not service.active.done() or service.manual_tools or service.model_manager.busy or getattr(service,"sync",None) and service.sync.lock.locked():return False
    for schedule in service.store.data['schedules']:
        item=due(schedule,now())
        if not item or schedule.get('owner','guest')!=owner(service.store):continue
        previous=dict(project=service.store.data['activeProject'],session=service.store.data['activeSession'],model=service.store.data['model'],mode=service.store.data['mode'])
        schedule.update(nextRun=item['nextRun'],lastRun=dict(**item,status='skipped' if item['skip'] else 'running',started=now(),background=background))
        service.store.save()  # Claim before work; never replay uncertain effects after a crash.
        if item['skip']:return True
        denied=[]
        original=service.tools.approve;original_host=service.tools.host
        async def unavailable(method,params):raise ValueError("This action requires the Wixal desktop")
        async def review(details):
            denied.append(details.get('name','action'));return False
        try:
            service.store.select_project(schedule.get('projectId'));service.store.data['mode']='agent';service.store.new_session()
            if schedule.get('model'):service.store.data['model']=schedule['model']
            if background:service.tools.approve=review;service.tools.host=unavailable
            if schedule.get('agentID'):
                service.agents.routine_authority=schedule.get('authority',{})
                job=service.agents.workflow(schedule['workflowID'],schedule.get('projectId'),source='Background schedule' if background else 'Schedule') if schedule.get('workflowID') else service.agents.run(schedule['agentID'],schedule['prompt'],schedule.get('projectId'),'Background schedule' if background else 'Schedule',checks=schedule.get('successCriteria'),authority=schedule.get('authority',{}))
                service.active=asyncio.create_task(job)
                result=await service.active
            else:result=await service.dispatch('chat',dict(text=schedule['prompt']))
            task=next((t for t in service.store.data['tasks'] if t['id']==result['id']),result)
            task.update(source='Background schedule' if background else 'Schedule',scheduleId=schedule['id'])
            if denied:
                task.update(status='paused',error='This scheduled task needs action review. Open Wixal and retry it to review the requested actions.')
            schedule['lastRun'].update(status=task['status'],taskId=task['id'],verification=task.get('verification'),finished=now(),reviewsRequired=list(dict.fromkeys(denied)))
        except asyncio.CancelledError:
            schedule['lastRun'].update(status='interrupted',finished=now());raise
        except Exception as error:
            schedule['lastRun'].update(status='failed',error=str(error)[:500],finished=now())
            service.emit('error',dict(message=str(error)))
        finally:
            service.tools.approve=original;service.tools.host=original_host
            service.agents.routine_authority=None
            service.store.data.update(activeProject=previous['project'],activeSession=previous['session'],model=previous['model'],mode=previous['mode'])
            last=schedule.get('lastRun',{})
            policy=schedule.get('notification','Completion, failure or review')
            if policy!='No notifications' and (policy!='Only when attention is needed' or last.get('status')!='completed'):
                service.store.data.setdefault('notifications',[]).append(dict(id=__import__('uuid').uuid4().hex,scheduleId=schedule['id'],name=schedule.get('name','Scheduled task'),owner=owner(service.store),status=last.get('status'),taskId=last.get('taskId'),created=now(),read=False))
                service.store.data['notifications']=service.store.data['notifications'][-200:]
            service.store.save();service.emit('state',service.store.data)
        return True
    return False


class Background:
    def __init__(self,service):
        self.service=service
        suffix=hashlib.sha256(str(service.store.directory.resolve()).encode()).hexdigest()[:12]
        self.label='app.wixal.native.scheduler.'+suffix
        self.path=Path.home()/'Library/LaunchAgents'/ (self.label+'.plist')
    def snapshot(self):
        return dict(enabled=self.path.exists(),label=self.label,intervalSeconds=60,
                    policy='Runs once for the latest missed interval after login or wake. The Mac must be awake. Actions needing review pause for Wixal.')
    async def configure(self,enabled):
        domain='gui/'+str(os.getuid())
        if not enabled:
            await asyncio.to_thread(subprocess.run,['launchctl','bootout',domain,str(self.path)],capture_output=True)
            self.path.unlink(missing_ok=True)
        else:
            if sys.platform!='darwin' or not getattr(sys,'frozen',False):raise ValueError('Enable background schedules from the installed macOS app')
            command=[sys.executable,'--background','--data',str(self.service.store.directory),'--runtime',str(self.service.runtime.payload)]
            if self.service.runtime.external:command+=['--endpoint',self.service.runtime.url]
            self.path.parent.mkdir(parents=True,exist_ok=True)
            logs=self.service.store.directory/'background.log'
            content=dict(Label=self.label,ProgramArguments=command,StartInterval=60,RunAtLoad=True,ProcessType='Background',LowPriorityIO=True,StandardOutPath=str(logs),StandardErrorPath=str(logs))
            temp=self.path.with_suffix('.tmp');temp.write_bytes(plistlib.dumps(content));temp.chmod(0o600);temp.replace(self.path)
            await asyncio.to_thread(subprocess.run,['launchctl','bootout',domain,str(self.path)],capture_output=True)
            result=await asyncio.to_thread(subprocess.run,['launchctl','bootstrap',domain,str(self.path)],capture_output=True)
            if result.returncode:self.path.unlink(missing_ok=True);raise ValueError('macOS could not enable the background scheduler')
        self.service.store.data['backgroundScheduler']=self.snapshot();self.service.store.save()
        return self.snapshot()


async def background(args):
    from .service import Service
    os.environ['WIXAL_BACKGROUND']='1'
    try:service=Service(args.data,args.runtime,lambda *_:None,args.endpoint)
    except RuntimeError as error:
        if 'already open' in str(error):return  # Foreground engine owns scheduling while open.
        raise
    current=asyncio.current_task();loop=asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM,current.cancel)
    try:
        await service.integrations.restore_if_needed()
        async with asyncio.timeout(600):
            if not await run_due(service,True):
                from .agent_jobs import run_next
                await run_next(service,True)
    finally:await service.close()


def main():
    from .service import parser
    os.umask(0o077);args=parser().parse_args()
    try:asyncio.run(background(args))
    except (asyncio.CancelledError,TimeoutError):pass
