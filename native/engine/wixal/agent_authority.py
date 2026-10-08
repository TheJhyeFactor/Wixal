"""Authority over effects and targets, independent of model tool selection."""
import ipaddress
import urllib.parse
from pathlib import Path
from .tools import safe_path

def validate(value):
    value=value or {}
    if not isinstance(value,dict):raise ValueError('Invalid task authority')
    result={}
    for key in ('writePaths','commands','targets'):
        rows=value.get(key,[])
        if not isinstance(rows,list) or len(rows)>30 or any(not isinstance(x,str) or not x.strip() or len(x)>8000 for x in rows):raise ValueError('Invalid authority '+key)
        result[key]=list(dict.fromkeys(x.strip() for x in rows))
    for path in result['writePaths']:
        if Path(path).is_absolute() or '..' in Path(path).parts or any(c in path for c in '*?[]'):raise ValueError('Use exact project files or a directory ending in / for permitted writes')
    for target in result['targets']:
        if '://' in target:
            parsed=urllib.parse.urlsplit(target)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Use a target origin without credentials or query')
        elif '/' in target:ipaddress.ip_network(target,strict=False)
        elif any(c in target for c in '*?@\\ \n\r'):raise ValueError('Use exact target hosts or IP ranges')
    return result

def target_allowed(target,allowed):
    parsed=urllib.parse.urlsplit(target) if '://' in target else None
    host=parsed.hostname if parsed else target
    for rule in allowed:
        if '://' in rule:
            expected=urllib.parse.urlsplit(rule)
            if parsed and (parsed.scheme,host,parsed.port or (443 if parsed.scheme=='https' else 80))==(expected.scheme,expected.hostname,expected.port or (443 if expected.scheme=='https' else 80)):return True
        elif '/' in rule:
            try:
                if '/' in host and ipaddress.ip_network(host,strict=False).subnet_of(ipaddress.ip_network(rule,strict=False)):return True
                if '/' not in host and ipaddress.ip_address(host) in ipaddress.ip_network(rule,strict=False):return True
            except ValueError:pass
        elif host and host.lower()==rule.lower():return True
    return False

def enforce_target(profile,name,args):
    if not profile or not profile.get('restrictTargets'):return
    if name in ('http_request','website_assess','browser_open','browser_inspect','network_scan','nmap_scan'):
        target=args.get('url') or args.get('target')
        if not target or not target_allowed(target,profile.get('authority',{}).get('targets',[])):raise ValueError('Target is outside the agent authorised scope')
    if name in ('run_command','command_start') and args.get('command') not in profile.get('authority',{}).get('commands',[]):raise ValueError('Commands in target-restricted runs require an exact approved command')
    if name in ('web_search','browser_action','terminal_run','delegate_task') or name.startswith('mcp_'):raise ValueError('This target-restricted agent requires a directly scoped tool')

def permits(details,authority,project):
    authority=validate(authority);root=(project or {}).get('root')
    def write_allowed(value):
        if not root:return False
        try:
            base=Path(root).resolve();relative=Path(value).relative_to(base) if Path(value).is_absolute() else Path(value)
            actual=safe_path(root,str(relative),writing=True)
            for approved in authority['writePaths']:
                boundary=safe_path(root,approved.rstrip('/'),writing=True)
                if actual==boundary or approved.endswith('/') and actual.is_relative_to(boundary):return True
        except (ValueError,OSError):pass
        return False
    name=details.get('name')
    if name in ('write_file','edit_file','make_directory'):return write_allowed(details.get('path',''))
    if name=='save_website_evidence':return bool(details.get('paths')) and all(write_allowed(p) for p in details['paths'])
    if name=='command_start':
        if details.get('networkTarget') and target_allowed(details['networkTarget'],authority['targets']):return True
        return details.get('command') in authority['commands'] and details.get('root')==root
    if name in ('http_request','website_assess'):return target_allowed(details.get('url',''),authority['targets'])
    return False
