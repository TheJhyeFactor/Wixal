"""Deterministic sanitization before evidence reaches a local model or public draft."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

class Scrubber:
    def __init__(self,store,salt):
        self.counts=Counter();self.salt=salt
        account=store.data.get('account',{}).get('profile') or {}
        self.known=[str(Path.home()), *[p.get('root','') for p in store.data.get('projects',[])], *[account.get(k,'') for k in ('name','email','id')]]
        self.known=sorted({s for s in self.known if isinstance(s,str) and len(s)>2},key=len,reverse=True)

    def replace(self,kind):
        def apply(match):self.counts[kind]+=1;return '[REDACTED:'+kind+']'
        return apply

    def text(self,value):
        for secret in self.known:
            count=value.count(secret)
            if count:self.counts['known_identity_or_path']+=count;value=value.replace(secret,'[REDACTED:identity_or_path]')
        patterns=[
            ('private_key',r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----'),
            ('credential',r'(?i)\b(?:authorization["\x27]?\s*:\s*["\x27]?(?:bearer|basic)\s+|(?:api[_-]?key|password|passwd|secret|access[_-]?token|refresh[_-]?token)["\x27]?\s*[=:]\s*)["\x27]?[^\s"\x27,;}]+'),
            ('token',r'\b(?:gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]{15,}|sk-[A-Za-z0-9_-]{15,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})\b'),
            ('jwt',r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
            ('identifier',r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'),
            ('email',r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
            ('url',r'(?i)https?://[^\s<>"\x27]+'),
            ('local_path',r'(?:/(?:Users|home|Volumes|private|var|tmp)/|[A-Za-z]:\\)[^\s"\x27<>]+'),
            ('ip_address',r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            ('phone',r'(?<![\w])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-])\d{3,4}[\s.-]\d{3,4}(?![\w])'),
        ]
        for kind,pattern in patterns:value=re.sub(pattern,self.replace(kind),value)
        return value

    def alias(self,value):
        if not isinstance(value,str):return value
        return hashlib.sha256((self.salt+value).encode()).hexdigest()[:12]

    def events(self,rows):
        # Allowlist metadata only. Omit source URLs, content and arbitrary nested payloads.
        fields=('timestamp','sequence','event','status','tool','method','elapsedMs','elapsedSeconds','errorCategory','errorFingerprint','resultCharacters','contentCharacters','thinkingCharacters','toolCalls','turn','estimatedInput','context','retries','exitCode','httpStatus','sessionCount')
        ids=('bootId','requestId','taskId','actionId','sessionId','id')
        out=[]
        for row in rows:
            item={k:self.text(row[k]) if isinstance(row[k],str) else row[k] for k in fields if isinstance(row.get(k),(str,int,float,bool))}
            for key in ids:
                if isinstance(row.get(key),str):item[key]=self.alias(row[key])
            if isinstance(row.get('unresolved'),list):item['unresolved']=[self.alias(s) for s in row['unresolved'] if isinstance(s,str)]
            out.append(item)
        return out

    def result(self):return dict(redactions=dict(self.counts),policyVersion=1,note='Detected credentials, account identifiers, emails, URLs, local paths, IP addresses and phone patterns were removed. Automatic removal cannot recognize every personal fact; inspect the entire draft before public submission.')
