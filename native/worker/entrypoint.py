"""Trusted Linux bootstrap: apply destination/port egress before an unprivileged scan."""
import hashlib
import ipaddress
import json
import subprocess
import sys


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def validate(value):
    if not isinstance(value,dict) or set(value)!={'addresses','ports','profile','seconds','engagementId','runId','scopeRevision'}:raise ValueError('Invalid worker contract')
    addresses=value['addresses'];ports=value['ports']
    if not isinstance(addresses,list) or not 1<=len(addresses)<=4:raise ValueError('Invalid address count')
    for address in addresses:
        parsed=ipaddress.ip_address(address)
        if parsed.is_loopback or parsed.is_multicast or parsed.is_unspecified or parsed.is_link_local:raise ValueError('Worker requires explicit reachable lab destinations')
    if not isinstance(ports,list) or not 1<=len(ports)<=1024 or any(type(p) is not int or not 1<=p<=65535 for p in ports):raise ValueError('Invalid port set')
    if value['profile'] not in ('ports','services') or type(value['seconds']) is not int or not 10<=value['seconds']<=600:raise ValueError('Invalid bounded scan profile')
    return value


def rules(value):
    value=validate(value)
    portset=', '.join(str(p) for p in sorted(set(value['ports'])))
    lines=['table inet wixal {','chain input { type filter hook input priority 0; policy drop; ct state established,related accept; }','chain output { type filter hook output priority 0; policy drop;']
    for version,keyword in ((4,'ip'),(6,'ip6')):
        addresses=[str(ipaddress.ip_address(a)) for a in value['addresses'] if ipaddress.ip_address(a).version==version]
        if addresses:lines.append(keyword+' daddr { '+', '.join(addresses)+' } tcp dport { '+portset+' } accept;')
    lines+=['}','}'];return '\n'.join(lines)+'\n'


def main():
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536:raise ValueError('Worker configuration too large')
    value=validate(json.loads(raw));script=rules(value)
    subprocess.run(['nft','-f','-'],input=script.encode(),check=True,timeout=5,capture_output=True)
    applied=subprocess.run(['nft','-j','list','table','inet','wixal'],check=True,timeout=5,capture_output=True).stdout
    print(json.dumps(dict(kind='enforcement-receipt',configSha256=hashlib.sha256(canonical(value)).hexdigest(),rulesSha256=hashlib.sha256(applied).hexdigest(),engagementId=value['engagementId'],runId=value['runId'],scopeRevision=value['scopeRevision'])),flush=True)
    # Child cannot change nftables or regain privileges. No shell, tool installation,
    # inherited credentials, host mounts, Docker socket or arbitrary command text.
    argv=['setpriv','--reuid=65534','--regid=65534','--clear-groups','--bounding-set=-all','--no-new-privs','nmap','-sT','-Pn','-n','--max-parallelism','16','--max-retries','1','--host-timeout',str(max(5,value['seconds']-5))+'s','-p',','.join(str(p) for p in sorted(set(value['ports']))),'-oX','-']
    if value['profile']=='services':argv+=['-sV','--version-light']
    argv+=value['addresses']
    result=subprocess.run(argv,timeout=value['seconds'],check=False)
    raise SystemExit(result.returncode)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(error=str(error),execution='refused-or-failed')),file=sys.stderr)
        raise SystemExit(1)
