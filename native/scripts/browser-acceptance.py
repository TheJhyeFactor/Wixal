"""Exercise the desktop's real WebKit page through its engine socket."""
import asyncio
import json
from pathlib import Path


async def main():
    root=Path(__file__).resolve().parents[2]
    reader,writer=await asyncio.open_unix_connection(Path.home()/"Library/Application Support/Wixal Native/engine.sock",limit=16*1024*1024)
    counter=0
    async def tool(name,arguments):
        nonlocal counter
        counter+=1;identifier=f"browser-acceptance-{counter}"
        writer.write((json.dumps(dict(id=identifier,method="tool",params=dict(name=name,arguments=arguments)))+"\n").encode());await writer.drain()
        while line:=await asyncio.wait_for(reader.readline(),90):
            row=json.loads(line)
            if row["event"]=="response" and row["data"]["id"]==identifier:
                data=row["data"]
                if data.get("error"):raise RuntimeError(data["error"])
                return data["result"]
        raise RuntimeError("Disconnected")
    report=dict(status="running",url="https://en.wikipedia.org/wiki/Special:Search",implementation="real desktop WebKit")
    artifact=root/"artifacts/native/browser-acceptance.json"
    page=None
    try:
        page=await tool("browser_open",dict(url=report["url"],wait_for="Search",wait_ms=10000))
        report["snapshot"]=page
        assert "Search" in page.get("text",""),page
        searched=await tool("browser_read",dict(session_id=page["session_id"],filter="Search",wait_ms=1000))
        controls=searched.get("controls",[])
        inputs=[control for control in controls if control.get("kind")=="input" and control.get("type") in ("text","search")]
        report["inputCandidates"]=inputs
        if inputs:
            candidate=next((control for control in inputs if "search" in json.dumps(control).lower()),inputs[0])
            changed=await tool("browser_action",dict(session_id=page["session_id"],action="fill",ref=candidate["ref"],value="Swift programming language",wait_ms=1000))
            report["fill"]=changed
            assert any(c.get("value")=="Swift programming language" for c in changed.get("controls",[])),"Filled value absent from fresh snapshot"
            submit=next(c for c in changed["controls"] if c.get("kind")=="button" and c.get("type")=="submit")
            try:await tool("browser_action",dict(session_id=page["session_id"],action="click",ref=submit["ref"]))
            except RuntimeError as error:
                assert "Form submission is unsupported" in str(error),error
                report["submissionBlocked"]=True
            else:raise AssertionError("Submission was allowed")
            menu=await tool("browser_read",dict(session_id=page["session_id"],filter="Main menu",wait_ms=0))
            toggle=next(c for c in menu["controls"] if c.get("type")=="checkbox")
            checked=await tool("browser_action",dict(session_id=page["session_id"],action="click",ref=toggle["ref"],wait_ms=0))
            assert any(c.get("label")=="Main menu" and c.get("checked")!=toggle["checked"] for c in checked["controls"])
            report["buttonInteraction"]=True
        await tool("browser_close",dict(session_id=page["session_id"]));page=None
        page=await tool("browser_open",dict(url="https://docs.python.org/3/",wait_for="Python",wait_ms=10000))
        theme=await tool("browser_read",dict(session_id=page["session_id"],filter="theme",wait_ms=0))
        select=next(c for c in theme["controls"] if c["kind"]=="select")
        option=next(o for o in select["options"] if not o.get("disabled") and o["value"]!=select["value"])
        selected=await tool("browser_action",dict(session_id=page["session_id"],action="select",ref=select["ref"],value=option["value"],wait_ms=0))
        assert any(c.get("kind")=="select" and c.get("value")==option["value"] for c in selected["controls"])
        report["optionSelection"]=dict(url="https://docs.python.org/3/",value=option["value"])
        report["status"]="passed" if inputs else "partial"
    except BaseException as error:
        report["status"]="failed";report["error"]=str(error);raise
    finally:
        if page and page.get("session_id"):
            report["close"]=await tool("browser_close",dict(session_id=page["session_id"]))
        artifact.write_text(json.dumps(report,indent=2));writer.close();await writer.wait_closed()
    print(json.dumps(dict(status=report["status"],controls=len(report["snapshot"].get("controls",[])),inputCandidates=len(report.get("inputCandidates",[])),filled="fill" in report)))


if __name__=="__main__":asyncio.run(main())
