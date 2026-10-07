"""Real public remote MCP discovery/call. No fabricated endpoint or tool response."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.mcp import MCP
ROOT=Path(__file__).resolve().parents[2]
async def main():
    client=MCP();report=dict(status='running',endpoint='https://mcp.deepwiki.com/mcp')
    try:
        definitions=await client.connect(dict(id='remote-acceptance',name='DeepWiki',transport='http',url=report['endpoint']),None)
        tool=next(t for t in definitions if t['function']['original']=='read_wiki_structure')
        result=await client.execute(tool['function']['name'],dict(repoName='modelcontextprotocol/python-sdk'))
        assert 'client' in result.lower() and len(result)>100,result
        report.update(status='passed',tools=[t['function']['original'] for t in definitions],result=result,resultSHA256=hashlib.sha256(result.encode()).hexdigest())
    except BaseException as error:report.update(status='failed',error=str(error));raise
    finally:
        await client.close();report['disconnected']=not client.connections
        (ROOT/'artifacts/native/remote-mcp-real.json').write_text(json.dumps(report,indent=2))
    print('REAL_REMOTE_MCP_PASSED')
asyncio.run(main())
