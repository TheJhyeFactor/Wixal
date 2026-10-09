"""Application-owned selected HTTP template profile; Nuclei verifies signatures.

Content never supplies code protocols, arbitrary hosts, variables or workflows.
The bounded profile deliberately supports GET/HEAD evidence collection only.
"""
import re
import yaml

class TemplateLoader(yaml.SafeLoader):
    def compose_node(self,parent,index):
        if self.check_event(yaml.AliasEvent):raise ValueError('Template aliases are unsupported')
        self.node_count=getattr(self,'node_count',0)+1
        if self.node_count>8000:raise ValueError('Template has too many YAML nodes')
        self.depth=getattr(self,'depth',0)+1
        if self.depth>32:raise ValueError('Template nesting exceeds the profile limit')
        try:return super().compose_node(parent,index)
        finally:self.depth-=1
    def construct_mapping(self,node,deep=False):
        keys=[self.construct_object(key,deep=deep) for key,_ in node.value]
        if len(set(keys))!=len(keys):raise ValueError('Duplicate template keys are unsupported')
        return super().construct_mapping(node,deep=deep)

def validate(raw):
    if not raw or len(raw)>1024*1024:raise ValueError('Select a template below 1 MB')
    try:value=yaml.load(raw,Loader=TemplateLoader)
    except (yaml.YAMLError,TypeError) as error:raise ValueError('Malformed selected HTTP template') from error
    if not isinstance(value,dict) or not {'id','info','http'}<=value.keys() or not value.keys()<={'id','info','http'}:raise ValueError('This profile permits HTTP templates only, without code, workflows or variables')
    requests=value['http']
    if not isinstance(requests,list) or not 1<=len(requests)<=4:raise ValueError('Select at most four bounded HTTP request definitions')
    allowed={'method','path','matchers','matchers-condition','extractors','host-redirects','redirects','max-redirects','stop-at-first-match','req-condition'}
    total=0
    for request in requests:
        if not isinstance(request,dict) or not request.keys()<=allowed or request.get('method') not in ('GET','HEAD'):raise ValueError('Selected HTTP profile requires GET/HEAD paths without payloads, raw requests or dynamic execution')
        paths=request.get('path',[])
        if not isinstance(paths,list) or not paths:raise ValueError('Template requires explicit target-relative paths')
        total+=len(paths)
        for path in paths:
            if not isinstance(path,str) or len(path)>2000 or not re.fullmatch(r'\{\{(?:BaseURL|RootURL)\}\}(?:/[A-Za-z0-9._~!$&\x27()*+,;=:@%/?-]*)?',path):raise ValueError('Template paths must stay on the selected target, without other variables or hosts')
    if total>16:raise ValueError('Template exceeds sixteen target-relative requests')
    return value['id']
