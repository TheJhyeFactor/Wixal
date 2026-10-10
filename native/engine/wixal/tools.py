"""Python port of project, command, network, memory and MCP tool enforcement."""
import asyncio
import codecs
import html
import ipaddress
import json
import os
import re
import shutil
import signal
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from .storage import identity, now

DEFINITIONS = json.loads((Path(__file__).parent / "resources/tools.json").read_text())
from .addons import definitions as addon_definitions
DEFINITIONS += addon_definitions()

SKIP = {".git", "node_modules", ".venv", "venv", "release", ".next", "dist", ".build", ".wixal-tmp"}


def sensitive(relative):
    return any(re.match(r"^\.env(?:\.|$)", p) or p in {".ssh", ".aws", ".gnupg", ".npmrc", ".netrc", "credentials.enc", "wixal-connection.json", "workspace.sqlite3"}
               or re.search(r"\.(pem|key|p12|pfx)$", p, re.I) for p in Path(relative).parts)


def safe_path(root, relative, writing=False):
    if not root:
        raise ValueError("Open a project directory")
    if not isinstance(relative, str) or Path(relative).is_absolute() or sensitive(relative):
        raise ValueError("Use a project-relative path without credentials")
    base = Path(root).resolve(strict=True)
    target = base / relative
    actual = target.resolve(strict=not writing)
    if not actual.is_relative_to(base) or sensitive(actual.relative_to(base)):
        raise ValueError("Path escapes the project or reaches protected credentials")
    if writing and not actual.parent.is_dir():
        raise ValueError("Parent directory must exist")
    return actual


def validate(args, schema):
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object")
    properties = schema.get("properties", {})
    if any(k not in args for k in schema.get("required", [])):
        raise ValueError("Missing required tool argument; required fields: "+", ".join(schema.get("required",[])))
    if schema.get("additionalProperties") is False and set(args) - set(properties):
        raise ValueError("Unknown tool argument; allowed fields: "+", ".join(properties))
    for key, value in args.items():
        rule = properties.get(key, {})
        types = {"string": str, "integer": int, "number": (int, float), "array": list, "object": dict, "boolean": bool}
        expected = types.get(rule.get("type"))
        if expected and (not isinstance(value, expected) or rule.get("type") in ("integer", "number") and isinstance(value, bool)):
            raise ValueError(f"Invalid type for {key}")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"Invalid value for {key}; choose one of {rule["enum"]}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < rule.get("minimum", value) or value > rule.get("maximum", value):
                raise ValueError(f"{key} is outside its bounds")
        if isinstance(value, str) and len(value) > rule.get("maxLength", 100000):
            raise ValueError(f"{key} is too long")
        if isinstance(value, list):
            if len(value) > rule.get("maxItems", 100):
                raise ValueError("Too many items")
            for item in value:
                validate({"item": item}, {"properties": {"item": rule.get("items", {})}})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_request(args):
    url = urllib.parse.urlsplit(args["url"])
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("Use an HTTP(S) URL without credentials")
    method = args.get("method", "GET").upper()
    if method not in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"):
        raise ValueError("Unsupported HTTP method")
    body = args.get("body")
    if body is not None:
        if method in ("GET", "HEAD") or len(body) > 16000:
            raise ValueError("Invalid HTTP body")
        json.loads(body)
    if method not in ("GET", "HEAD") and args.get("offset", 0):
        raise ValueError("Write pagination could repeat a mutation")
    request = urllib.request.Request(args["url"], data=body.encode() if body else None, method=method,
        headers={"User-Agent": "Wixal-Native/1", **({"Content-Type": "application/json"} if body else {})})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(1024*1024+1)
        text = raw[:1024*1024].decode("utf-8", errors="replace")
        if "text/html" in response.headers.get("Content-Type", ""):
            text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.S | re.I)
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
            text = re.sub(r"[ \t]+", " ", text)
        offset, limit = args.get("offset", 0), args.get("max_chars", 12000)
        if not 0 <= offset <= len(text):
            raise ValueError("Invalid response offset")
        return dict(url=args["url"], status=response.code, headers=dict(response.headers), content=text[offset:offset+limit],
            next_offset=min(len(text), offset+limit), more=offset+limit < len(text), truncated=len(raw)>1024*1024,
            redirect=response.headers.get("Location"))


PROFILES = {
    "discovery": ["-sn", "-PS22,80,443"], "ports": ["-sT", "-Pn"],
    "services": ["-sT", "-Pn", "-sV", "--version-light"],
    "web": ["-sT", "-Pn", "-sV", "--script", "http-title,http-headers,http-security-headers"],
    "tls": ["-sT", "-Pn", "-sV", "--script", "ssl-cert,ssl-enum-ciphers"],
    "ssh": ["-sT", "-Pn", "-sV", "--script", "ssh-hostkey,ssh2-enum-algos"],
    "enumeration": ["-sT", "-Pn", "-sV", "--script", "http-enum"],
    "checks": ["-sT", "-Pn", "-sV", "--script", "ssl-poodle,http-cookie-flags,http-security-headers"]}


def scan_plan(args):
    target = args["target"].strip()
    if "://" in target:
        url = urllib.parse.urlsplit(target)
        if url.scheme not in ("http", "https") or url.username or url.password:
            raise ValueError("Invalid scan URL")
        target = url.hostname or ""
    if "/" in target:
        net = ipaddress.ip_network(target, strict=False)
        if net.version != 4 or net.prefixlen < 24 or not any(net.subnet_of(ipaddress.ip_network(cidr)) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")):
            raise ValueError("Subnet scans require a private IPv4 /24–/32")
    else:
        try:
            ipaddress.ip_address(target)
        except ValueError:
            if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?", target) or any(not p or len(p)>63 for p in target.split(".")):
                raise ValueError("Invalid scan target")
    profile = args.get("profile", "services")
    if profile not in PROFILES:
        raise ValueError("Unknown scan profile")
    ports = args.get("ports", "22,53,80,443,445,3389,8080,8443")
    if not re.fullmatch(r"\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*", ports):
        raise ValueError("Invalid TCP ports")
    for part in ports.split(","):
        values = list(map(int, part.split("-")))
        if not 1 <= values[0] <= values[-1] <= 65535:
            raise ValueError("Ports must be 1–65535")
    seconds = args.get("timeout_seconds", 180)
    return [*(["-6"] if ":" in target else []), *PROFILES[profile], "-n", "--reason", "-T3", "--max-retries", "1",
            "--host-timeout", f"{seconds}s", "--script-timeout", "30s", *([] if profile=="discovery" else ["-p", ports]), "-oX", "-", target]


def web_search(args):
    """Return actual provider links, with bounded fallback on provider failure."""
    failures = []
    for provider, base in (("DuckDuckGo", "https://lite.duckduckgo.com/lite/"),
                           ("Bing", "https://www.bing.com/search")):
        params = {"q": args["query"]}
        if provider == "Bing":
            params["format"] = "rss"
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Wixal-Native/1)"}), timeout=20) as response:
                raw = response.read(1024 * 1024).decode("utf-8")
            results = []
            if provider == "Bing":
                root = ET.fromstring(raw)
                if root.tag != "rss":
                    raise ValueError("Provider returned an unexpected response")
                for item in root.findall("./channel/item"):
                    results.append(dict(title=item.findtext("title", ""), url=item.findtext("link", "")))
            else:
                if "anomaly.js" in raw or "bots use DuckDuckGo" in raw:
                    raise ValueError("Provider returned a bot challenge")
                for attributes, title in re.findall(r"<a\b([^>]*)>(.*?)</a>", raw, re.S):
                    if "result-link" not in attributes and "result__a" not in attributes:
                        continue
                    match = re.search(r'href=[\"\']([^\"\']+)', attributes)
                    if not match:
                        continue
                    href = match.group(1)
                    href = html.unescape(href)
                    href = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("uddg", [href])[0]
                    results.append(dict(title=html.unescape(re.sub("<[^>]+>", "", title)), url=href))
                if not results and "No results" not in raw:
                    raise ValueError("Provider response did not contain recognised search results")
            results = [item for item in results if item["url"].startswith(("http://", "https://"))]
            return dict(results=results[:max(1, min(20, int(args.get("limit", 8))))],
                        state="results" if results else "no_results", provider=provider, providerFailures=failures)
        except (OSError, ValueError, ET.ParseError) as error:
            failures.append(dict(provider=provider, error=str(error)))
    raise ValueError("Search providers unavailable: " + "; ".join(f'{row["provider"]}: {row["error"]}' for row in failures))


class Tools:
    def __init__(self, store, approve, emit, mcp, host=None):
        self.store, self.approve, self.emit, self.mcp, self.host = store, approve, emit, mcp, host
        self.jobs = {}
        self.delegate = None

    def environment(self):
        return dict(shell='/bin/zsh -l',executables={name:path for name in ('python','python3','node','npm','git','rg','nmap') if (path:=shutil.which(name))})

    def catalog(self):
        return DEFINITIONS + self.mcp.definitions() + (self.management.definitions() if getattr(self,"management",None) else [])

    def files(self, directory="."):
        root = self.store.project()["root"]
        start = safe_path(root, directory)
        result = []
        for folder, dirs, files in os.walk(start, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not sensitive(d) and not (Path(folder)/d).is_symlink()
                             and len(Path(folder).relative_to(start).parts)<6)
            for file in sorted(files):
                p = Path(folder) / file
                if not p.is_symlink() and not sensitive(p.relative_to(root)):
                    result.append(str(p.relative_to(root)))
                if len(result) >= 1200:
                    return result
        return result

    async def start_command(self, command, seconds, session_id, argv=None, assessment=None, environment=None, on_finished=None, retain_evidence=False):
        if sum(j["state"]=="running" for j in self.jobs.values()) >= 8:
            raise ValueError("Eight commands are already running")
        project = dict(self.store.project() or {})
        if not project or not command.strip() or len(command)>8000:
            raise ValueError("A project and valid command are required")
        if not await self.approve(dict(name="command_start", command=command, root=project["root"], timeout_seconds=seconds,**({"assessment":assessment} if assessment else {}))):
            return "User declined this command."
        if self.store.project()!=project or sum(j["state"]=="running" for j in self.jobs.values())>=8:
            raise ValueError("Project or command capacity changed during review; review the action again")
        from .agent_context import profile
        branch=(profile.get() or {}).get("_branchRoot")
        invocation=argv or ["/bin/zsh", "-l", "-c", command]
        if branch:
            if not Path("/usr/bin/sandbox-exec").is_file():raise ValueError("Isolated commands require the macOS sandbox backend")
            policy="(version 1) (allow default) (deny file-write*) (deny network*) (allow file-write* (subpath "+json.dumps(str(Path(branch).resolve()))+")) (allow file-write* (literal \"/dev/null\"))"
            invocation=["/usr/bin/sandbox-exec","-p",policy,*invocation]
            temporary=Path(branch)/".wixal-tmp";temporary.mkdir(exist_ok=True)
            environment={**os.environ,"TMPDIR":str(temporary),"PYTHONDONTWRITEBYTECODE":"1"}
        child = await asyncio.create_subprocess_exec(*invocation, cwd=project["root"],env=environment,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE if retain_evidence else asyncio.subprocess.STDOUT, start_new_session=True)
        job_id = identity()
        job = dict(id=job_id, owner=session_id, projectId=project["id"], command=command, started=now(), state="running",
                   output="", base=0, exitCode=None, child=child, reason=None)
        self.jobs[job_id] = job
        if assessment: job['assessment']=assessment
        if retain_evidence:
            directory=self.store.directory/'tool-evidence'/project['id']/job_id
            directory.mkdir(parents=True,mode=0o700)
            job['evidence']=dict(stdoutPath=str(directory/'stdout'),stderrPath=str(directory/'stderr'),incomplete=False,limitBytes=16*1024*1024)
        async def collect():
            async def drain(stream,label):
                decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
                captured=0
                output=Path(job['evidence'][label+'Path']).open('wb') if retain_evidence else None
                try:
                    while chunk:=await stream.read(8192):
                        if output:
                            captured+=len(chunk)
                            if captured>job['evidence']['limitBytes']:
                                job['evidence']['incomplete']=True;self.stop_job(job,'evidence_limit');break
                            output.write(chunk)
                        text=decoder.decode(chunk)
                        job['output']+=text
                        extra=max(0,len(job['output'])-1024*1024)
                        job['base']+=len(job['output'][:extra].encode('utf-16-le'))//2
                        job['output']=job['output'][extra:]
                        self.emit('command-output',dict(text=text,session_id=job_id))
                    tail=decoder.decode(b'',final=True)
                    if tail:job['output']+=tail
                finally:
                    if output:
                        output.flush();os.fsync(output.fileno());output.close()
                        from .managed_tools import digest
                        job['evidence'][label+'Sha256']=digest(job['evidence'][label+'Path'])
            try:
                async with asyncio.timeout(seconds):
                    await asyncio.gather(drain(child.stdout,'stdout'),*([drain(child.stderr,'stderr')] if retain_evidence else []))
                    job['exitCode']=await child.wait()
                    job['state']='stopped' if job['reason'] else 'completed'
            except TimeoutError:
                if retain_evidence:job['evidence']['incomplete']=True
                self.stop_job(job,'timeout');await child.wait();job['exitCode']=child.returncode;job['state']='stopped'
            except BaseException:
                self.stop_job(job,'collector_error');await child.wait();job['exitCode']=child.returncode;job['state']='stopped'
                raise
            finally:
                # The session leader may have exited while a descendant still
                # owns a pipe or keeps running after redirecting its output.
                self.terminate_group(job)
                job['finished']=now()
                try:
                    if on_finished:await on_finished(job)
                except Exception as error:
                    job.update(state='failed',error='Command evidence finalization failed: '+str(error))
                finally:job['settled']=True
        job["collector"] = asyncio.create_task(collect())
        return dict(session_id=job_id, state="running")

    def terminate_group(self,job):
        if job.get('groupTerminated'):return
        try:os.killpg(job['child'].pid,signal.SIGKILL)
        except ProcessLookupError:pass
        job['groupTerminated']=True

    def stop_job(self, job, reason="user_stop"):
        if job['state']=='running' or job["child"].returncode is None:
            job["reason"] = reason
            self.terminate_group(job)

    async def read_job(self, args, session_id):
        job = self.jobs.get(args["session_id"])
        if not job or job["owner"] != session_id or job["projectId"] != (self.store.project() or {}).get("id"):
            raise ValueError("Command belongs to another conversation or project")
        if job["state"] == "running" or not job.get('settled',False):
            await asyncio.sleep(args.get("wait_ms", 1000)/1000)
        offset = args.get("offset", job["base"])
        encoded=job['output'].encode('utf-16-le');units=len(encoded)//2
        if offset<0 or offset>job["base"]+units:
            raise ValueError("Invalid output offset")
        start = max(offset, job["base"])
        maximum=args.get('max_chars',24000)
        if not isinstance(maximum,int) or not 1<=maximum<=100000:raise ValueError('Choose 1–100,000 output characters')
        data=encoded[(start-job['base'])*2:(start-job['base']+maximum)*2]
        if data and 0xDC00<=int.from_bytes(data[:2],'little')<=0xDFFF:
            raise ValueError('Output offset must align to a character boundary')
        try:output=data.decode('utf-16-le')
        except UnicodeDecodeError:
            # A one-unit page must still advance over a complete emoji. Never
            # return an empty page at the same offset forever.
            if len(data)==2 and 0xD800<=int.from_bytes(data,'little')<=0xDBFF:
                data=encoded[(start-job['base'])*2:(start-job['base']+2)*2]
            else:data=data[:-2]
            try:output=data.decode('utf-16-le')
            except UnicodeDecodeError as error:raise ValueError('Output offset must align to a character boundary') from error
        structured=job.get('structuredResult',{})
        return dict(**({"structuredResult":structured} if structured else {}), **({"services":structured['services'],"summary":structured['summary']} if structured.get('kind')=='nmap' else {}), **({"error":job.get('error') or structured['error']} if job.get('error') or structured.get('error') else {}), **({"evidence":job["evidence"]} if job.get("evidence") else {}), session_id=job["id"], command=job["command"], state=job["state"] if job.get('settled',False) else 'running', exitCode=job["exitCode"],
                    reason=job["reason"], output=output, offset=start, next_offset=start+len(output.encode('utf-16-le'))//2,
                    more=start+len(output.encode('utf-16-le'))//2<job["base"]+units, earliest_offset=job["base"], started=job["started"], finished=job.get("finished"))

    async def execute(self, name, args, session_id):
        from .agent_context import available_names
        definition = next((t for t in self.catalog() if t["function"]["name"]==name), None)
        if not definition:raise ValueError("Unknown tool name. Inspect workspace_info for the exact available tool names.")
        if name not in available_names(self,self.store):
            raise ValueError(f"{name} is switched off or outside this agent task boundary")
        if name in ("network_scan","network_discover") and name not in self.store.data.get("enabledTools",[]):raise ValueError(name+" is switched off")
        validate(args, definition["function"]["parameters"])
        from .agent_context import profile
        from .agent_authority import enforce_target
        enforce_target(profile.get(),name,args)
        if (profile.get() or {}).get("_branchRoot") and (name.startswith("mcp_") or name.startswith("browser_") or name in ("terminal_exec","delegate_task","http_request","web_search","website_assess","network_scan","network_discover")):
            raise ValueError("External actions are unavailable in an isolated change branch")
        root = (self.store.project() or {}).get("root")
        from .context_policy import requires_project
        if requires_project(name) and (self.store.project() or {}).get('syncRootRequired'):raise ValueError('Locate this synced project folder in Settings before using project tools')
        if getattr(self,"management",None) and name in self.management.names:
            return await self.management.tool(name,args)
        if name.startswith("addon_"):
            manager=getattr(self.store,"addons",None)
            if not manager:raise ValueError("Capability library is unavailable in this workspace")
            if name=="addon_discover":return await manager.discover(args["query"])
            if name=="addon_catalog":return manager.snapshot(args.get("query",""))
            if name=="addon_install":return await manager.install(args,self,session_id)
            if name=="addon_job":return await manager.job(args,session_id)
            if name=="addon_workflow":
                if (profile.get() or {}).get("_branchRoot"):raise ValueError("Workflow installation is unavailable in an isolated change branch")
                if not await self.approve(dict(name="addon_workflow",id=args["id"])):return "User declined this workflow installation."
                return manager.workflow(args["id"])
            if name=="addon_run":
                from .addon_execution import run
                return await run(manager,self,args,session_id)
        if name == "load_skill":
            skill = next((s for s in self.store.data["skills"] if s["name"]==args["name"]),None)
            if not skill: raise ValueError("Unknown skill")
            return dict(name=skill["name"],instructions=skill["content"])
        if name == "delegate_task":
            if not self.delegate: raise ValueError("Delegation is unavailable in a child agent")
            return await self.delegate(args["prompt"])
        if name == "workspace_info":
            from .context_policy import eligible,category
            available=eligible(self.catalog(),available_names(self,self.store),self.store.project())
            return dict(app="Wixal Native",environment=self.environment(), project=self.store.project(), model=self.store.data["model"], approvalMode=self.store.approval_mode(), tools=[dict(name=t['function']['name'],category=category(t['function']['name']),description=t['function']['description']) for t in available],memory=self.store.memory.snapshot()['policy'])
        if name == "verify_json":
            from .outcomes import criteria,verify
            check=criteria([dict(kind='json_matches_source',**args)])[0]
            task=next((t for t in reversed(self.store.data['tasks']) if t.get('sessionId')==session_id and t.get('status')=='running'),None)
            if task is not None:
                checks=task.setdefault('successCriteria',[])
                if check not in checks:task['successCriteria']=criteria([*checks,check])
                self.store.save()
            probe=dict(sessionId=session_id,checkpoints=[],successCriteria=[check])
            return await verify(self.store,self,probe)
        if name == "list_files":
            return self.files(args.get("directory", "."))[args.get("offset", 0):]
        if name in ("read_file", "search_files"):
            files = [args["path"]] if name == "read_file" else self.files()
            results = []
            for relative in files:
                file = safe_path(root, relative)
                if not file.is_file() or file.stat().st_size>1024*1024:
                    if name=='read_file':raise ValueError('Choose a readable text file below 1 MB, not a directory')
                    continue
                try:
                    text = file.read_text()
                except UnicodeError:
                    if name=='read_file':raise ValueError('This file is not UTF-8 text')
                    continue
                if "\0" in text:
                    if name=='read_file':raise ValueError('This file contains binary data')
                    continue
                if name == "read_file":
                    offset = args.get("offset", 0)
                    return dict(content=text[offset:offset+24000], next_offset=min(len(text), offset+24000), more=offset+24000<len(text))
                results.extend(dict(path=relative, line=i+1, text=line[:400]) for i,line in enumerate(text.splitlines()) if args["query"].lower() in line.lower())
            return results[args.get("offset", 0):][:100]
        if name in ("write_file", "edit_file", "make_directory"):
            file = safe_path(root, args["path"], True)
            before = file.read_bytes() if file.is_file() else None
            if name == "edit_file":
                text = (before or b"").decode()
                if not args["old_text"] or text.count(args["old_text"])!=1:
                    raise ValueError("Edit requires one exact unique match")
                content = text.replace(args["old_text"], args["new_text"])
            else:
                content = args.get("content", "")
            if len(content)>100000:
                raise ValueError("File write exceeds 100,000 characters")
            if not await self.approve(dict(name=name, path=str(file), content=content, before=(before or b"").decode(errors="replace"))):
                return "User declined this file operation."
            if safe_path(root, args["path"], True)!=file or (file.read_bytes() if file.is_file() else None)!=before:
                raise ValueError("File changed during review")
            if name == "make_directory":
                file.mkdir()
            else:
                file.write_text(content)
            return f"Saved {args['path']}"
        if name == "save_memory":
            session=next((s for s in self.store.data['sessions'] if s['id']==session_id),{})
            source=next((m for m in reversed(session.get('messages',[])) if m['role']=='user'),{})
            scope=args.get('scope','project')
            if not await self.approve(dict(name=name, content=args["content"],scope=scope,replace_id=args.get('replace_id'))):
                return "User declined this memory."
            note=self.store.memory.save(args['content'],scope,session_id,source.get('id'),args.get('replace_id'))
            return dict(saved=True,id=note['id'],scope=scope,content=note['content'])
        if name=='recall_memory':
            if hasattr(self,'runtime'):await self.store.memory.prepare(args['query'],self.runtime,args.get('scope'),session_id)
            return dict(results=self.store.memory.recall(args['query'],args.get('scope'),exclude_session=session_id),note='Saved facts and allowed history only. Earlier assistant text is evidence, not verified fact.')
        if name=='forget_memory':
            if not await self.approve(dict(name=name,id=args['id'],action='Forget this saved memory and exclude its source from recall')):return 'User declined forgetting memory.'
            return dict(forgotten=self.store.memory.forget(args['id']))
        if name == "search_history":
            if (self.store.project() or {}).get("memoryMode") in ("off", "global"):
                raise ValueError("Project recall is disabled")
            return self.store.memory.recall(args['query'],scope='project',limit=8,exclude_session=session_id)
        if name in ("command_start", "run_command"):
            result = await self.start_command(args["command"], args.get("timeout_seconds", 60 if name=="run_command" else 600), session_id)
            if name=="run_command" and isinstance(result, dict):
                await self.jobs[result["session_id"]]["collector"]
                return await self.read_job(dict(session_id=result["session_id"], wait_ms=0), session_id)
            return result
        if name in ("command_read", "network_read"):
            return await self.read_job(args, session_id)
        if name in ("command_stop", "network_stop", "command_write", "command_save_output"):
            result = await self.read_job(dict(session_id=args["session_id"], wait_ms=0), session_id)
            job = self.jobs[args["session_id"]]
            if name.endswith("stop"):
                self.stop_job(job)
                return dict(session_id=job["id"], cancellationRequested=True)
            if name=="command_save_output":
                result["output"] = job["output"]
                return await self.execute("write_file", dict(path=args["path"], content=json.dumps(result, indent=2)), session_id)
            if not await self.approve(dict(name=name, command=args["input"])):
                return "User declined command input."
            job["child"].stdin.write(args["input"].encode())
            await job["child"].stdin.drain()
            if args.get("close_stdin"):
                job["child"].stdin.close()
            return dict(inputSent=True)
        if name == 'security_tools':
            manager=getattr(self.store,'addons',None)
            rustscan=manager.snapshot('rustscan')['packages'] if manager else []
            return dict(installed=bool(shutil.which('nmap') or Path('/opt/homebrew/bin/nmap').is_file()),profiles=list(PROFILES),rustscan=rustscan,interpretation='Installation, capability readiness and model evaluation are separate states')
        if name == 'network_discover':
            from .network_discovery import start
            return await start(self,args,session_id)
        if name == 'network_scan':
            if args.get('source_run_id') or args.get('source_session_id'):
                from .network_discovery import inspect
                return await inspect(self,args,session_id)
            executable=shutil.which('nmap') or ('/opt/homebrew/bin/nmap' if Path('/opt/homebrew/bin/nmap').exists() else None)
            if not executable:raise ValueError('Install Nmap to use network assessment')
            from .agent_context import profile
            active=profile.get() or {}
            if active.get('restrictTargets'):
                from .network_discovery import plan
                await plan(dict(target=args['target'],ports=args.get('ports','22,53,80,443,445,3389,8080,8443')),active)
            argv=[executable,*scan_plan(args)]
            from .network_discovery import ports
            from .managed_tools import controlled_environment,digest
            assessment=dict(capability='network_scan',profile=args.get('profile','services'),target=args['target'],ports=ports(args.get('ports','22,53,80,443,445,3389,8080,8443')),executableSha256=await asyncio.to_thread(digest,executable))
            from .nmap_results import finish
            return await self.start_command(' '.join(argv),args.get('timeout_seconds',180),session_id,argv,assessment=assessment,retain_evidence=True,environment=controlled_environment(Path(executable).parent),on_finished=finish)
        if name in ("http_request", "web_search"):
            if not await self.approve(dict(name=name, **args, **({"providers": ["lite.duckduckgo.com", "www.bing.com"]} if name == "web_search" else {}))):
                return "User declined this network request."
            if name=="http_request":
                return await asyncio.to_thread(http_request, args)
            return await asyncio.to_thread(web_search, args)
        if name.startswith("browser_"):
            if not self.host:
                raise ValueError("Rendered browser tools require the native desktop")
            if name in ("browser_open", "browser_action", "browser_inspect") and not await self.approve(dict(name=name, **args)):
                return "User declined this browser action."
            return await self.host("browser", dict(name=name, args=args, owner=session_id))
        if name.startswith("mcp_"):
            if not await self.approve(dict(name=name, arguments=args)):
                return "User declined this MCP action."
            return await self.mcp.execute(name, args)
        if name in ("website_assess", "website_simulate"):
            from .website import execute_website
            return await execute_website(self, name, args, session_id)
        raise ValueError("Unknown tool")

    async def close(self, owner=None):
        jobs = [j for j in self.jobs.values() if owner is None or j["owner"]==owner]
        for job in jobs:
            self.stop_job(job)
        await asyncio.gather(*(j["collector"] for j in jobs), return_exceptions=True)
