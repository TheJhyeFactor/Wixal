"""Small-model request policy: permissions, progressive schemas and whole evidence."""
import copy
import json
import re

CATEGORIES = ('files', 'commands', 'web', 'security', 'memory', 'external')
PROJECT_TOOLS = {'list_files','read_file','search_files','write_file','edit_file','make_directory','run_command','delegate_task','verify_json'}

def requires_project(name):
    return name in PROJECT_TOOLS or name.startswith(('command_', 'network_', 'website_'))

def category(name):
    if name.startswith('addon_'):return 'security'
    if name.startswith('mcp_'): return 'external'
    if name.startswith(('website_', 'network_')) or name == 'security_tools': return 'security'
    if name.startswith('command_') or name == 'run_command': return 'commands'
    if name.startswith('browser_') or name in ('http_request','web_search'): return 'web'
    if name in ('workspace_info','search_history','recall_memory','save_memory','forget_memory','schedule_manage','skill_manage','workflow_manage'): return 'memory'
    return 'files'

def eligible(catalog, enabled, project):
    return [t for t in catalog if t['function']['name'] in enabled and (project and not project.get('syncRootRequired') or not requires_project(t['function']['name']))]

def select_tools(available, prompt='', requested=(), load_category=None, load_name=None):
    names = {t['function']['name'] for t in available}
    if load_name and load_name not in names: raise ValueError('That tool is not enabled or available in this workspace')
    if load_category and load_category not in CATEGORIES: raise ValueError('Choose a supported tool category')
    if len(available) <= 8 and not load_name and not load_category: return available
    chosen = {'workspace_info', 'recall_memory', 'load_skill', *requested}
    if re.search(r'\b(workflow|workflows|pipeline)\b',prompt,re.I):chosen.add('workflow_manage')
    if re.search(r'\b(schedule|scheduled|recurring|routine|routines|calendar)\b',prompt,re.I):chosen.add('schedule_manage')
    if re.search(r'\b(skill|skills|procedure|procedures)\b',prompt,re.I):
        chosen.add('skill_manage');chosen.discard('save_memory')
    if re.search(r'\b(addon|add-on|install|download|toolkit|nuclei|ffuf|wireshark|metasploit)\b',prompt,re.I):chosen.update(('addon_catalog','addon_discover','addon_install','addon_job','addon_run','addon_workflow','command_read','command_stop'))
    if re.search(r'\b(report|artifact|verify|verified|verification)\b',prompt,re.I) and re.search(r'\bjson\b|\.json\b',prompt,re.I):chosen.add('verify_json')
    value = load_category
    if load_name: chosen.add(load_name)
    elif not value:
        explicit = next((n for n in requested if n != 'workspace_info'), None)
        if explicit:
            # Named requests need their schemas, with command lifecycle follow-ups.
            # Other categories remain discoverable through workspace_info.
            if any(category(n) in ('commands','security') for n in requested):
                chosen.update(('command_read','command_stop','command_save_output'))
            return [t for t in available if t['function']['name'] in chosen]
        else:
            routing_prompt = re.sub(r"\b(?:do not|don't|without)\s+(?:inspect|read|write|edit|search)\s+(?:(?:the|any|project|unrelated)\s+)?files\b", "", prompt, flags=re.I)
            for candidate, pattern in (
                ('external', r'\b(mcp|connected|connector|integration)\b'),
                ('security', r'\b(nmap|rustscan|discover(?:y)?|scan|ports|tls|assessment|security|vulnerab\w*)\b'),
                ('commands', r'\b(run|build|test|command|shell|terminal|execute)\b'),
                ('web', r'https?://|\b(browse|website|web|online|internet|url|links?)\b'),
                ('files', r'\b(file|files|folder|source|code|read|write|edit)\b'),
                ('memory', r'\b(remember|memory|recall|previous|earlier|prefer)\b')):
                if re.search(pattern, routing_prompt, re.I): value=candidate;break
    if value:
        matching=[t['function']['name'] for t in available if category(t['function']['name']) == value]
        inspection_request=re.sub(r"\b(?:do not|don't|without|no|avoid|skip)\s+(?:service\s+)?(?:inspect\w*|enumerat\w*)\b",'',prompt,flags=re.I)
        if value=='security' and not load_category and not load_name and re.search(r'\bstandalone\s+(?:tcp\s+)?discovery\b',prompt,re.I) and not re.search(r'\b(?:inspect\w*|enumerat\w*)\b',inspection_request,re.I):
            # Progressive discovery starts with its own adapter, not every
            # service probe/installer in the security catalogue. Other schemas
            # remain explicitly discoverable through workspace_info.
            discovery={'network_discover','network_read','network_stop','security_tools','addon_catalog'}
            matching=[name for name in matching if name in discovery]
            chosen={name for name in chosen if name in requested or category(name)!='security' or name in discovery}
        chosen.update(matching[:8] if value == 'external' else matching)
        if value in ('commands','security'): chosen.update(('command_read','command_stop','command_save_output'))
    return [t for t in available if t['function']['name'] in chosen]

def thinking_options(metadata):
    if 'thinking' not in metadata.get('capabilities',[]):return {}
    config=metadata.get('thinking') or {}
    values=config.get('values',[])
    return dict(think='low' if 'low' in values else True if True in values else config.get('default',True))

def bounded_evidence(content, limit):
    if len(content) <= limit: return content
    try: value=json.loads(content)
    except (ValueError, TypeError):
        room=max(0,limit-100);head=room//3
        return content[:head]+'\n[Excerpt; full evidence saved in conversation]\n'+content[-(room-head):]
    def shrink(item, room):
        if isinstance(item,str):
            if len(item)<=room:return item
            half=max(0,(room-60)//2)
            return item[:half]+'\n[Excerpt; full evidence saved]\n'+(item[-half:] if half else '')
        if isinstance(item,list):
            result=[]
            for entry in item:
                candidate=shrink(entry,max(100,room-len(json.dumps(result))))
                if len(json.dumps(result+[candidate],ensure_ascii=False))>room:break
                result.append(candidate)
            if len(result)<len(item):result.append({'excerpt':True,'omittedItems':len(item)-len(result)})
            return result
        if isinstance(item,dict):
            # IDs, refs, pagination and status remain whole before large text fields.
            result={k:v for k,v in item.items() if not isinstance(v,(dict,list,str)) or isinstance(v,str) and len(v)<200}
            large=[(k,v) for k,v in item.items() if k not in result]
            allocation=max(80,(room-len(json.dumps(result)))//max(1,len(large)))
            for k,v in large:result[k]=shrink(v,allocation)
            result['excerpt']=True
            return result
        return item
    return json.dumps(shrink(value,max(150,limit-60)),ensure_ascii=False)

def token_estimate(messages, definitions):
    text=sum((len(json.dumps({k:v for k,v in m.items() if k not in ('images','imageIds')},ensure_ascii=False))+3)//4+8 for m in messages)
    images=sum((len(m.get('images',[]))+len(m.get('imageIds',[])))*1024 for m in messages)
    tools=(len(json.dumps(definitions,ensure_ascii=False))+3)//4 if definitions else 0
    return text+images+tools, text, images, tools

def thinking_reserve(metadata,context):
    forced='thinking' in metadata.get('capabilities',[]) and thinking_options(metadata).get('think') is not False
    return min(4096,max(1024,context//2)) if forced else None

def fit_request(messages, definitions, limit, output_reserve=None):
    """Retain the latest complete tool chain; reject rather than silently truncate user input."""
    messages=copy.deepcopy(messages)
    reserve=min(limit-256,output_reserve) if output_reserve else min(2048,max(256,limit//5))
    ceiling=limit-reserve
    def count(): return token_estimate(messages,definitions)[0]
    groups=[]
    for index,message in enumerate(messages[1:],1):
        if message['role']=='user' or not groups:groups.append([])
        groups[-1].append(index)
    omitted=0
    while count()>ceiling and len(groups)>1:
        end=groups[1][0];omitted+=end-1
        messages=messages[:1]+messages[end:]
        groups=[[i-(end-1) for i in group] for group in groups[1:]]
    tools=[i for i,m in enumerate(messages) if m['role']=='tool']
    for allowance in (6000,2400,1000,400):
        if count()<=ceiling:break
        for index in tools:messages[index]['content']=bounded_evidence(messages[index].get('content',''),allowance if index==tools[-1] else max(250,allowance//3))
    if count()>ceiling:
        raise ValueError('This message, images, memory and selected tools exceed the safe context budget. Shorten the message, remove attachments or choose a larger supported context.')
    return messages,reserve,omitted
