"""Versioned engagement authority, checked at dispatch and each scoped connection."""
import asyncio
import ipaddress
import socket
from contextvars import ContextVar
from urllib.parse import urlsplit
from .agent_authority import target_allowed, validate as validate_authority
from .storage import now

current = ContextVar('wixal_engagement', default=None)
simulation_origin = ContextVar('wixal_simulation_origin', default=None)
CAPABILITIES = ('analysis', 'planner', 'software_inventory', 'website_assess', 'website_simulate', 'network_scan', 'network_discover', 'linux_network_scan','api_observe','api_mutate')


def text(value, label, maximum=8000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{label} requires text below {maximum} characters')
    return value.strip()


def strings(value, label, maximum=64):
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(v, str) or not v or len(v) > 2000 for v in value):
        raise ValueError('Invalid ' + label)
    return list(dict.fromkeys(value))


def policy(value, target_ids):
    if not isinstance(value, dict) or set(value) - {'targetIds','exclusions','capabilities','starts','ends','maxRuns','maxSeconds','contacts','dataHandling','abortConditions','threatProfile'}:
        raise ValueError('Invalid engagement scope fields')
    selected = strings(value.get('targetIds', target_ids), 'scope targets')
    if not selected or set(selected) != set(target_ids):
        raise ValueError('Scope must explicitly include every engagement target')
    exclusions = strings(value.get('exclusions', []), 'exclusions', 30)
    validate_authority(dict(targets=exclusions))
    capabilities = strings(value.get('capabilities', ['analysis','planner','software_inventory','website_assess','website_simulate']), 'capabilities')
    if not capabilities or any(c not in CAPABILITIES for c in capabilities):
        raise ValueError('Engagements require supported directly scoped capabilities; generic commands and external controllers are unavailable')
    starts, ends = value.get('starts', now()), value.get('ends', now()+86400000)
    if type(starts) is not int or type(ends) is not int or not starts < ends or ends-starts > 31*86400000:
        raise ValueError('Testing window must be ordered and no longer than 31 days')
    runs, seconds = value.get('maxRuns',32), value.get('maxSeconds',180)
    if type(runs) is not int or not 1 <= runs <= 128 or type(seconds) is not int or not 10 <= seconds <= 600:
        raise ValueError('Choose 1–128 runs and a 10–600 second run deadline')
    result = dict(targetIds=selected,exclusions=exclusions,capabilities=capabilities,starts=starts,ends=ends,maxRuns=runs,maxSeconds=seconds)
    for key in ('contacts','dataHandling','abortConditions','threatProfile'):
        val = value.get(key,'')
        if not isinstance(val,str) or len(val)>8000:raise ValueError('Invalid '+key)
        result[key]=val
    return result


def live():
    context = current.get()
    if context:
        context['manager'].authorize_run(context['run'])
    return context


def excluded(value, rules):
    if target_allowed(value, rules):return True
    host = urlsplit(value).hostname if '://' in value else value
    if host and target_allowed(host, rules):return True
    try:
        network=ipaddress.ip_network(host,strict=False)
        return any(network.overlaps(ipaddress.ip_network(rule,strict=False)) for rule in rules if '/' in rule)
    except ValueError:return False


def tool_gate(name, args):
    context=live()
    if not context:return
    capability=context['run']['capability']
    allowed={'analysis':set(),'planner':set(),'software_inventory':{'list_files','read_file'},
             'website_assess':{'website_assess'},'website_simulate':{'website_simulate'},
             'network_scan':{'network_scan'},'network_discover':{'network_discover'},'linux_network_scan':set(),'api_observe':set(),'api_mutate':set()}[capability]
    if name not in allowed:raise ValueError('Tool is outside this engagement capability')
    target=args.get('url') or args.get('target')
    if target:
        expected=context['run']['address']
        if target != expected:raise ValueError('Engagement target binding cannot change')
        if excluded(target,context['manager'].scope(context['engagement'])['exclusions']):raise ValueError('Destination is excluded by the engagement scope')


async def addresses(target, port=None):
    context=live()
    host=urlsplit(target).hostname if '://' in target else target
    if not context:return None
    rules=context['manager'].scope(context['engagement'])['exclusions']
    if excluded(target,rules):raise ValueError('Destination is excluded by the engagement scope')
    if '/' in host:
        # scan_plan separately bounds supported private subnet sizes.
        return [host]
    try:values=[str(ipaddress.ip_address(host))]
    except ValueError:
        resolved=await asyncio.get_running_loop().getaddrinfo(host,port,type=socket.SOCK_STREAM)
        values=sorted({row[4][0] for row in resolved})
    if not 1<=len(values)<=4 or any(excluded(v,rules) for v in values):
        raise ValueError('Resolved destination is excluded or exceeds the address bound')
    live()  # scope may have changed while DNS was pending
    return values


async def connection(url):
    context=live()
    if not context:return None
    if context['run']['capability']=='website_simulate':
        origin=simulation_origin.get()
        if not origin or not target_allowed(url,[origin]) or urlsplit(url).hostname!='127.0.0.1':raise ValueError('Simulation connection is outside the owned loopback fixture')
        return '127.0.0.1'
    if context['run']['capability'] not in ('website_assess','api_observe','api_mutate') or not target_allowed(url,[context['run']['address']]):
        raise ValueError('HTTP destination is outside the engagement origin')
    parsed=urlsplit(url)
    values=await addresses(url,parsed.port or (443 if parsed.scheme=='https' else 80))
    return values[0]
