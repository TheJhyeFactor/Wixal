import json,sys
for line in sys.stdin:
 request=json.loads(line)
 if 'id' not in request:continue
 method=request['method']
 if method=='initialize':result=dict(protocolVersion='2024-11-05',capabilities=dict(tools={}),serverInfo=dict(name='fixture',version='1'))
 elif method=='tools/list':result=dict(tools=[dict(name='echo',description='Fixture echo',inputSchema=dict(type='object',properties=dict(text=dict(type='string')),required=['text'],additionalProperties=False))])
 elif method=='tools/call':result=dict(content=[dict(type='text',text=request['params']['arguments']['text'])])
 else:result={}
 print(json.dumps(dict(jsonrpc='2.0',id=request['id'],result=result)),flush=True)
