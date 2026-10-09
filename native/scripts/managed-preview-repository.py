#!/usr/bin/env python3
"""Build a LOCAL preview TUF repository from an explicitly supplied real binary.

No public upload. Single-operator keys stay in a separate private directory.
This is a local qualification recipe, not a reproducible source-build claim.
"""
import argparse
import io
import json
import os
import platform
import sys
import tarfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal import VERSION
from wixal.managed_tools import ADAPTER,digest,descriptor
from wixal.network_discovery import subprocess_version
from tuf.api.metadata import Metadata,Root,Targets,Snapshot,Timestamp,TargetFile,MetaFile
from securesystemslib.signer import CryptoSigner


def build(destination,binary,license_path,commit,key_directory,base_url,receipt=None):
    destination=Path(destination);keys=Path(key_directory)
    if keys.is_relative_to(destination) or destination.is_relative_to(keys):raise ValueError('Signing keys must be stored separately from the served repository')
    destination.mkdir(parents=True,exist_ok=False);keys.mkdir(mode=0o700,parents=True,exist_ok=False)
    metadata=destination/'metadata';targets=destination/'targets';metadata.mkdir();targets.mkdir()
    signers={role:CryptoSigner.generate_ed25519() for role in ('root','targets','snapshot','timestamp')}
    for role,signer in signers.items():
        path=keys/(role+'.pem');path.write_bytes(signer.private_bytes);path.chmod(0o600)
    now=datetime.now(timezone.utc);root=Root(expires=now+timedelta(days=365),consistent_snapshot=False)
    for role,signer in signers.items():root.add_key(signer.public_key,role)
    def publish(name,payload,role):
        signed=Metadata(payload);signed.sign(signers[role]);signed.to_file(str(metadata/name));return signed
    publish('root.json',root,'root')
    rows=[];version=subprocess_version(str(binary)).split()[-1]
    for revision in (1,2):
        contents={'bin/rustscan':Path(binary).read_bytes(),'LICENSE':Path(license_path).read_bytes(),'PREVIEW-NOTICE.json':json.dumps(dict(channel='local_preview',packageRevision=revision,sourceCommit=commit,sourceBinary=str(Path(binary).resolve()),sourceBinarySha256=digest(binary),recipe='Local repack of existing binary; source build/reproducibility not claimed',homebrewReceipt=json.loads(Path(receipt).read_text()) if receipt else None),indent=2).encode()}
        target=targets/('rustscan-r'+str(revision)+'.tar.gz')
        with tarfile.open(target,'w:gz') as archive:
            for name,data in contents.items():
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o755 if name.startswith('bin/') else 0o644;member.mtime=0
                archive.addfile(member,io.BytesIO(data))
        import hashlib
        row=dict(schemaVersion=1,tool='rustscan',version=version,revision=revision,source=dict(url='https://github.com/bee-san/RustScan',commit=commit,strategy='upstream_artifact',recipeSha256=digest(__file__),license='GPL-3.0',notices=['LICENSE','PREVIEW-NOTICE.json']),platform=dict(os='Darwin',arch='arm64',minimumOS='14.0',testedOS=[platform.mac_ver()[0]]),target=target.name,sha256=digest(target),length=target.stat().st_size,unpackedSize=sum(map(len,contents.values())),entrypoint='bin/rustscan',inventory={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},adapter=ADAPTER,appBuilds=[VERSION],readiness='rustscan-version-v1',distribution='local_preview',dependencies=[],state='approved',recovery=[rows[0]['sha256']] if rows else [])
        rows.append(descriptor(row))
    (targets/'catalogue.json').write_text(json.dumps(dict(schemaVersion=1,packages=rows),indent=2))
    target_data=Targets(expires=now+timedelta(days=7))
    for path in targets.iterdir():target_data.targets[path.name]=TargetFile.from_file(path.name,str(path))
    publish('targets.json',target_data,'targets')
    snapshot=Snapshot(expires=now+timedelta(days=7),meta={'targets.json':MetaFile.from_data(1,(metadata/'targets.json').read_bytes(),['sha256'])});publish('snapshot.json',snapshot,'snapshot')
    publish('timestamp.json',Timestamp(expires=now+timedelta(days=2),snapshot_meta=MetaFile.from_data(1,(metadata/'snapshot.json').read_bytes(),['sha256'])),'timestamp')
    configuration=dict(channel='preview',metadataURL=base_url.rstrip('/')+'/metadata/',targetsURL=base_url.rstrip('/')+'/targets/',trustedRoot=str(metadata/'root.json'),allowedHosts=['127.0.0.1'],preview=True)
    (destination/'client.json').write_text(json.dumps(configuration,indent=2))
    return configuration,rows

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--license',type=Path,required=True);parser.add_argument('--source-commit',required=True);parser.add_argument('--keys',type=Path,required=True);parser.add_argument('--base-url',required=True);parser.add_argument('--receipt',type=Path)
    options=parser.parse_args();configuration,rows=build(options.output,options.binary,options.license,options.source_commit,options.keys,options.base_url,options.receipt);print(json.dumps(dict(configuration=configuration,packages=[r['sha256'] for r in rows]),indent=2))
