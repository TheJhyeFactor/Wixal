"""Model-selected tools in conversations; retain legacy manual-assessment preferences."""
from contextvars import ContextVar

profile = ContextVar('wixal_agent_profile', default=None)
automatic = ContextVar('wixal_automatic_tools', default=False)
READ_TOOLS = {'workspace_info','list_files','read_file','verify_json','search_files','search_history',
              'recall_memory','todo_list','tool_result_read','load_skill','web_search','http_request','addon_catalog','addon_job','addon_discover'}

def available_names(tools, store):
    active = profile.get()
    # Native scanner execution has explicit global off switches even in
    # automatic Chat/profile selection. Advertise the same scope it enforces.
    def scanner_scope(names):
        return [name for name in names if name not in ('network_scan','network_discover') or name in store.data.get('enabledTools',[])]
    if active is None:
        return scanner_scope([t['function']['name'] for t in tools.catalog()]) if automatic.get() or store.data.get('mode') == 'chat' else store.data['enabledTools']
    names = scanner_scope([t['function']['name'] for t in tools.catalog()])
    if active.get('_delegateTools') is not None:
        names = [n for n in names if n in active['_delegateTools']]
    if active.get('reviewPolicy') == 'Read only':
        return [n for n in names if n in READ_TOOLS]
    return names
