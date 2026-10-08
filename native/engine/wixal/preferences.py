"""Appearance validation is shared by idle and in-task settings updates."""

UI_DEFAULTS=dict(theme='sakura',textSize=13,reduceMotion=False,launchAnimation=True,launchSound=True,sidebarCollapsed=False,appIcon='theme')

def validate_ui(ui):
    if not isinstance(ui,dict) or set(ui)-set(UI_DEFAULTS):raise ValueError('Invalid appearance settings')
    for key,choices in (('theme',('sakura','midnight','paper','forest')),('textSize',(11,13,15,17)),('appIcon',('theme','sakura','midnight','pearl','copper'))):
        if key in ui and (ui[key] not in choices or key=='textSize' and type(ui[key]) is not int):raise ValueError('Invalid '+key+' preference')
    for key in ('reduceMotion','launchAnimation','launchSound','sidebarCollapsed'):
        if key in ui and not isinstance(ui[key],bool):raise ValueError('Invalid interface preference')
    return dict(ui)


def server_config(params):
    name=params.get('name','MCP server')
    if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('Enter a server name using up to 120 characters')
    transport=params.get('transport','stdio')
    if transport=='http':
        from .remote_mcp import validate_url
        if type(params.get('oauth',False)) is not bool:raise ValueError('Choose OAuth enabled or disabled')
        client=params.get('clientId','');scope=params.get('scope','')
        if not isinstance(client,str) or len(client)>500 or not isinstance(scope,str) or len(scope)>500:raise ValueError('Invalid OAuth client configuration')
        return dict(name=name.strip(),transport='http',url=validate_url(params.get('url','')),oauth=params.get('oauth',False),clientId=client,scope=scope)
    if transport!='stdio':raise ValueError('Choose local executable or remote HTTPS')
    command=params.get('command');args=params.get('args',[])
    if not isinstance(command,str) or not command.strip() or len(command)>4096 or '\x00' in command:raise ValueError('Enter a local executable')
    if not isinstance(args,list) or len(args)>100 or any(not isinstance(a,str) or len(a)>4096 or '\x00' in a for a in args):raise ValueError('Enter up to 100 arguments, each below 4,096 characters')
    return dict(name=name.strip(),transport='stdio',command=command.strip(),args=args)
