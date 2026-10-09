"""Create a local signed repository from measured controlled-source Go candidates.

The corresponding source remains a separate retained build artifact. This does
not publish packages or grant release/model qualification.
"""
import argparse
import hashlib
import json
import platform
import re
import sys
import tarfile
import io
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal import VERSION
from wixal.managed_tools import PROFILES,digest,descriptor,inspect_payload
from tuf.api.metadata import Metadata,Root,Targets,Snapshot,Timestamp,TargetFile,MetaFile
from securesystemslib.signer import CryptoSigner

def build(candidates,lock_path,destination,key_directory,base_url,rustscan_repository=None):
    destination=Path(destination).resolve();keys=Path(key_directory).resolve()
    if keys.is_relative_to(destination) or destination.is_relative_to(keys):raise ValueError('Keys must remain outside served output')
    destination.mkdir(parents=True,exist_ok=False);keys.mkdir(mode=0o700,parents=True,exist_ok=False)
    metadata=destination/'metadata';targets=destination/'targets';metadata.mkdir();targets.mkdir()
    signers={role:CryptoSigner.generate_ed25519() for role in ('root','targets','snapshot','timestamp')}
    for role,signer in signers.items():
        file=keys/(role+'.pem');file.write_bytes(signer.private_bytes);file.chmod(0o600)
    expiry=lambda days:datetime.now(timezone.utc)+timedelta(days=days)
    def publish(role,value):
        row=Metadata(value);row.sign(signers[role]);row.to_file(str(metadata/(role+'.json')))
    root=Root(expires=expiry(365),consistent_snapshot=False)
    for role,signer in signers.items():root.add_key(signer.public_key,role)
    publish('root',root);rows=[];lock=json.loads(Path(lock_path).read_text())
    for folder in sorted(Path(candidates).iterdir()):
        if not (folder/'provenance.json').is_file():continue
        provenance=json.loads((folder/'provenance.json').read_text());tool=provenance['tool'];profile=PROFILES.get(tool)
        if not profile or tool=='rustscan':continue
        source=next(r for r in lock['tools'] if r['id']==tool)
        if provenance['sourceCommit']!=source['sourceCommit'] or provenance['sourceRepository']!=source['fork']:raise ValueError('Candidate does not match controlled source pin')
        binary=folder/'bin'/tool
        if digest(binary)!=provenance['executableSha256'] or digest(folder/'corresponding-source.tar.gz')!=provenance['correspondingSourceSha256']:raise ValueError('Candidate source or executable changed')
        observed=re.search(profile['pattern'],provenance['observedVersionOutput'])
        if not observed:raise ValueError('Unsupported readiness output for '+tool)
        contents={'bin/'+tool:binary.read_bytes(),'BUILD-PROVENANCE.json':json.dumps(provenance,indent=2).encode(),'THIRD-PARTY-NOTICES.txt':(folder/'THIRD-PARTY-NOTICES.txt').read_bytes()}
        for notice in source['licenseFiles']:
            path=folder/Path(notice['path']).name
            if digest(path)!=notice['sha256']:raise ValueError('License mismatch')
            contents[Path(notice['path']).name]=path.read_bytes()
        archive=targets/(tool+'-r1.tar.gz')
        with tarfile.open(archive,'w:gz') as output:
            for name,data in contents.items():
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o755 if name.startswith('bin/') else 0o644;member.mtime=0;output.addfile(member,io.BytesIO(data))
        row=descriptor(dict(schemaVersion=1,tool=tool,version=observed.group(1),revision=1,
            source=dict(url=source['fork'],commit=source['sourceCommit'],strategy='pinned_build',recipeSha256=provenance['recipeSha256'],license=source['licenseId'],notices=[name for name in contents if not name.startswith('bin/')]),
            platform=dict(os='Darwin',arch='arm64',minimumOS='14.0',testedOS=[platform.mac_ver()[0]]),target=archive.name,sha256=digest(archive),length=archive.stat().st_size,unpackedSize=sum(map(len,contents.values())),
            entrypoint='bin/'+tool,inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},adapter=profile['adapter'],appBuilds=[VERSION],readiness=tool+'-version-v1',distribution='local_preview',dependencies=[],state='approved',recovery=[]))
        rows.append(row)
    if rustscan_repository:
        from wixal.managed_tools import CatalogueClient
        source=Path(rustscan_repository).resolve()
        configuration=json.loads((source/'client.json').read_text())
        client=CatalogueClient(destination/'source-verification',configuration)
        updater,imported,errors=client.refresh()
        if errors:raise ValueError('Invalid imported RustScan catalogue')
        import shutil
        for row in imported:
            if row['tool']!='rustscan':continue
            info=updater.get_targetinfo(row['target'])
            if not info or info.hashes.get('sha256')!=row['sha256'] or info.length!=row['length']:raise ValueError('Imported target identity mismatch')
            updater.download_target(info,str(targets/row['target']));rows.append(row)
        shutil.rmtree(destination/'source-verification')
    if not rows:raise ValueError('No supported, completed source candidates')
    (targets/'catalogue.json').write_text(json.dumps(dict(schemaVersion=1,packages=rows),indent=2))
    target_data=Targets(expires=expiry(7))
    for file in targets.iterdir():target_data.targets[file.name]=TargetFile.from_file(file.name,str(file))
    publish('targets',target_data);publish('snapshot',Snapshot(expires=expiry(7),meta={'targets.json':MetaFile.from_data(1,(metadata/'targets.json').read_bytes(),['sha256'])}));publish('timestamp',Timestamp(expires=expiry(2),snapshot_meta=MetaFile.from_data(1,(metadata/'snapshot.json').read_bytes(),['sha256'])))
    from urllib.parse import urlsplit
    host=urlsplit(base_url).hostname
    if host!='127.0.0.1':raise ValueError('This acceptance repository requires loopback')
    configuration=dict(channel='preview',metadataURL=base_url.rstrip('/')+'/metadata/',targetsURL=base_url.rstrip('/')+'/targets/',trustedRoot=str(metadata/'root.json'),allowedHosts=[host],preview=True)
    (destination/'client.json').write_text(json.dumps(configuration,indent=2));print(json.dumps(dict(status='built',tools=[r['tool'] for r in rows],configuration=configuration),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidates',required=True);p.add_argument('--lock',required=True);p.add_argument('--output',required=True);p.add_argument('--keys',required=True);p.add_argument('--base-url',required=True);p.add_argument('--rustscan-repository');o=p.parse_args();build(o.candidates,o.lock,o.output,o.keys,o.base_url,o.rustscan_repository)
