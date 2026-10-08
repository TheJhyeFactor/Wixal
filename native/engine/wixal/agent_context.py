"""Run-local profile capabilities; never change the user's legacy tool switches."""
from contextvars import ContextVar

profile = ContextVar('wixal_agent_profile', default=None)
automatic = ContextVar('wixal_automatic_tools', default=False)
READ_TOOLS = {'workspace_info','list_files','read_file','search_files','search_history',
              'recall_memory','load_skill','web_search','http_request'}

def available_names(tools, store):
    active = profile.get()
    if active is None:
        return [t['function']['name'] for t in tools.catalog()] if automatic.get() else store.data['enabledTools']
    names = [t['function']['name'] for t in tools.catalog()]
    if active.get('reviewPolicy') == 'Read only':
        return [n for n in names if n in READ_TOOLS]
    return names
