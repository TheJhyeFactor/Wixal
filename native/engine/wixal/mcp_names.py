"""Stable tool identity across discovery order changes."""
import hashlib

def prefix(server_id):return 'mcp_'+server_id.replace('-','')[:12]+'_'
def tool_name(server_id,original):return prefix(server_id)+hashlib.sha256(original.encode()).hexdigest()[:16]
