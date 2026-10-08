"""Durable serial job queue; effectful failures require inspection, never blind retry."""
import asyncio
import copy
from .storage import identity, now
from .memory import owner

def enqueue(agents,params):
    from .agents import text
    from .outcomes import criteria
    profile=copy.deepcopy(agents.find('agentProfiles',params['agentID']))
    delay=params.get('delaySeconds',0);priority=params.get('priority',0)
    if type(delay)!=int or not 0<=delay<=86400 or type(priority)!=int or not -10<=priority<=10:raise ValueError('Invalid job timing or priority')
    job=dict(id=identity(),owner=owner(agents.store),agentId=profile['id'],profile=profile,prompt=text(params.get('prompt'),'job brief'),projectId=params.get('projectId',agents.store.data['activeProject']),status='queued',created=now(),notBefore=now()+delay*1000,priority=priority,successCriteria=criteria(params.get('successCriteria',profile.get('successCriteria'))))
    if job['projectId'] is not None and not any(p['id']==job['projectId'] for p in agents.store.data['projects']):raise ValueError('Choose an existing project')
    agents.store.data['agentJobs'].append(job);agents.store.save();agents.service.emit('state',agents.store.data);return job

async def run_next(service,background=False):
    if service.active and not service.active.done() or service.manual_tools or service.model_manager.busy or service.sync.lock.locked() or service.security_workspace.busy:return False
    available=[j for j in service.store.data.get('agentJobs',[]) if j['status']=='queued' and j['notBefore']<=now() and j['owner']==owner(service.store)]
    if not available:return False
    job=sorted(available,key=lambda j:(-j['priority'],j['created']))[0]
    job.update(status='running',started=now(),attempts=job.get('attempts',0)+1);service.store.save()
    original=service.tools.approve;original_host=service.tools.host
    async def unavailable(*args):raise ValueError('This queued action requires the desktop')
    async def deny(*args):return False
    if background:service.tools.approve=deny;service.tools.host=unavailable
    try:
        service.active=asyncio.create_task(service.agents.run(job['agentId'],job['prompt'],job.get('projectId'),'Background queue' if background else 'Queued job',snapshot=job['profile'],checks=job['successCriteria'],authority=job['profile'].get('authority',{})))
        result=await service.active;job.update(status=result['status'],taskId=result['id'],verification=result.get('verification'))
        job.setdefault('history',[]).append(dict(taskId=result['id'],status=result['status'],finished=now()))
        from .agent_context import READ_TOOLS
        if result['status']=='failed' and job['attempts']<3 and all(c['name'] in READ_TOOLS for c in result.get('checkpoints',[])):
            job.update(status='queued',notBefore=now()+30000*2**(job['attempts']-1),error='Read-only attempt failed; retained evidence is available. Retry is bounded.')
    except asyncio.CancelledError:job.update(status='interrupted',error='Execution stopped; inspect retained task evidence before continuing.');raise
    except Exception as error:
        job.update(status='failed',error=str(error))
        # Only provider/setup failures before any modifying action may be retried.
        task=next((t for t in reversed(service.store.data['tasks']) if t.get('agentId')==job['agentId'] and t.get('created',0)>=job['started']),None)
        if task:job['taskId']=task['id'];job.setdefault('history',[]).append(dict(taskId=task['id'],status=task['status'],finished=now()))
        from .agent_context import READ_TOOLS
        if job['attempts']<3 and (task is None or all(c['name'] in READ_TOOLS for c in task.get('checkpoints',[]))):job.update(status='queued',notBefore=now()+30000*2**(job['attempts']-1))
    finally:
        service.tools.approve=original;service.tools.host=original_host
        job['updated']=now();service.store.save();service.emit('state',service.store.data)
    return True
