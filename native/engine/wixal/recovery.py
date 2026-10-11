"""Retained uncertain effects are evidence, never permission to replay them."""
import json
import shlex
from .agent_context import READ_TOOLS

READ_ONLY = READ_TOOLS | {'security_tools', 'network_read', 'command_read', 'addon_list', 'skill_list'}
COMMANDS = {'run_command', 'command_start', 'terminal_exec'}

def uncertain(task):
    checkpoints=task.get('checkpoints',[])
    def result(checkpoint):
        try:value=json.loads(checkpoint.get('result','{}'))
        except (ValueError,TypeError):return {}
        return value if isinstance(value,dict) else {}
    completed={value['session_id'] for c in checkpoints
               if c.get('name') in ('command_read','network_read') and c.get('status')=='finished'
               and (value:=result(c)).get('state')=='completed' and value.get('exitCode')==0 and value.get('session_id')}
    pending=[]
    for c in checkpoints:
        if c.get('name') in READ_ONLY:continue
        value=result(c)
        asynchronous=(c.get('name') in COMMANDS | {'network_scan','network_discover'}
                      and value.get('session_id') and value.get('state') in ('running','stopped','failed')
                      and value['session_id'] not in completed)
        if c.get('status') in ('started','interrupted') or c.get('status')=='finished' and asynchronous:pending.append(c)
    return pending

def evidence(checkpoints,argument_limit=1500,limit=8):
    return [dict(id=c['id'],tool=c['name'],status=c['status'],sessionId=c.get('sessionId'),
                 argumentExcerpt=json.dumps(c.get('arguments',{}),ensure_ascii=False)[:argument_limit]) for c in checkpoints[-limit:]]

def replay_key(name,args):
    if name in COMMANDS:
        command=args.get('command','')
        try:command=shlex.split(command) if isinstance(command,str) else command
        except ValueError:pass
        return 'command',json.dumps(command,sort_keys=True)
    return name,json.dumps(args,sort_keys=True)

def replay(checkpoints,name,args):
    key=replay_key(name,args)
    return next((c for c in checkpoints if replay_key(c['name'],c.get('arguments',{}))==key),None)
