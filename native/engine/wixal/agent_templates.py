"""Executable starter workflows. They operate on the selected project, never demo data."""
from .memory import owner

PROFILES=[
 ('reviewer','Project reviewer','Inspect project evidence without changes.','Read only','Inspect actual project files, cite sources, distinguish findings from assumptions and return actionable results. Do not change files or run commands.'),
 ('coder','Code assistant','Inspect, change and verify code.','Review actions','Inspect the issue, reproduce it, make a focused correction and run relevant verification. Report actual tests and remaining failures.'),
 ('researcher','Researcher','Retrieve sources and produce a grounded brief.','Review actions','Choose tools to retrieve primary evidence. Cite actual sources, preserve exact identifiers and distinguish observation from inference.'),
 ('security','Security analyst','Investigate authorised scope with retained evidence.','Review actions','Confirm the authorised target and project. Choose appropriate security tools, retain evidence, verify findings and explain limitations. Never expand scope. Use disposable loopback fixtures for local simulations.')]
WORKFLOWS=[
 ('review-report','Project review and report', [('Inspect','reviewer','Inspect the selected project and identify concrete issues with file references.','Evidence and findings'),('Report','coder','Use the preceding evidence to save a project-review.md report. Read it back to verify the content.','Verified report artifact')]),
 ('fix-verify','Reproduce, fix and verify',[('Diagnose','reviewer','Inspect the project and identify the requested defect and relevant tests. Ask for missing task details.','Diagnosis with source references'),('Fix','coder','Use the diagnosis to reproduce the failure, make the focused correction and run relevant tests.','Changes and test evidence'),('Review','reviewer','Inspect the current files and preceding test evidence. Report remaining issues and limitations.','Final independent review')]),
 ('research-brief','Research and produce a brief',[('Research','researcher','Research the topic in the workflow goal using retrieved primary sources.','Source-grounded evidence'),('Produce brief','coder','Use the preceding evidence to save research-brief.md with citations. Read back the result.','Verified brief artifact')]),
 ('data-report','Analyse data and verify report',[('Inspect data','reviewer','Discover relevant data files and describe their fields, quality issues and required calculations.','Data inventory'),('Calculate and report','coder','Calculate the requested results from actual data, independently verify the calculations, save data-report.md and read it back.','Verified calculations and report')]),
 ('security-evidence','Authorised security evidence review',[('Inspect scope','reviewer','Inspect project scope notes and existing security evidence. Identify the authorised target. Do not infer authorisation.','Explicit scope and evidence'),('Assess','security','Within the preceding authorised scope and workflow goal, choose tools to assess the target and retain raw results. If no target is authorised, stop and ask.','Assessment evidence'),('Verify findings','reviewer','Inspect the saved evidence and distinguish confirmed observations, candidate findings and unverified attack claims.','Verified findings and limitations')]),
 ('local-security-lab','Disposable local security lab',[('Run lab','security','Run the built-in website_simulate tool on its disposable loopback fixtures. Save with a unique report prefix. Do not scan external targets.','Saved vulnerable and hardened control results'),('Review controls','reviewer','Inspect the saved lab report. Compare vulnerable and hardened controls, report expected versus unexpected results, and cite the report.','Control comparison')])]

def install(agents,model):
    existing={p['name']:p for p in agents.store.data['agentProfiles'] if p.get('owner','guest')==owner(agents.store)}
    mapped={}
    for key,name,purpose,policy,instructions in PROFILES:
        mapped[key]=existing.get(name) or agents.save_profile(dict(name=name,purpose=purpose,instructions=instructions,model=model,reviewPolicy=policy,memoryScope='Project only',skills=[]))
    created=[]
    for key,name,stages in WORKFLOWS:
        if any(w['name']==name and w.get('owner','guest')==owner(agents.store) for w in agents.store.data['agentWorkflows']):continue
        created.append(agents.save_workflow(dict(name=name,brief='Describe the specific task, target or topic before running this workflow.',stages=[dict(name=title,agentID=mapped[agent]['id'],goal=goal,output=output,requiresReview=index>0) for index,(title,agent,goal,output) in enumerate(stages)])))
    return dict(agents=len(mapped),workflows=len(created))
