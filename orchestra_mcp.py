"""AIOrchestra MCP stdio adapter; the dashboard server owns all jobs and state."""
import argparse
import os
from pathlib import Path
import workflow_bridge


def create_server(workspace,server=None):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    mcp=FastMCP('AIOrchestra',instructions='Use list_agents to select a team/profile. Use start_agent only for an explicitly requested single-agent task; use start_workflow for coordinated team work. Reuse request_id after uncertain responses. Show real evidence and obtain explicit user approval for each workflow gate. Never infer approval or mark unfinished tasks done. Keep secrets out of reports.')
    def bridge():return workflow_bridge.Bridge(workspace,server)
    def request(path,payload=None):
        client=bridge();client.health();return client.request(path,payload)
    def guard():
        if os.environ.get('AIORCHESTRA_WORKFLOW_WORKER')=='1' or os.environ.get('AIORCHESTRA_DIRECT_AGENT')=='1':raise ValueError('Worker cannot delegate recursively')
    read=ToolAnnotations(readOnlyHint=True,openWorldHint=False)
    write=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)

    @mcp.tool(annotations=read)
    def health() -> dict:
        """Check the actual server/workspace. Does not start a job."""
        return bridge().run({'action':'health'})

    @mcp.tool(annotations=read)
    def list_agents() -> dict:
        """List team IDs, agent roles, assigned skills and CLI connection options."""
        return request('/api/agents/catalog')

    @mcp.tool(annotations=read)
    def get_agent_context(team:str,agent:str) -> dict:
        """Read a profile, team rules, assigned skills and relevant feedback without launching a process. Follow higher-priority user/project instructions."""
        from urllib.parse import urlencode
        return request('/api/agents/context?'+urlencode(dict(team=team,agent=agent)))

    @mcp.tool(annotations=write)
    def start_agent(team:str,agent:str,project:str,task:str,request_id:str,engine:str='Codex',model:str='',access:str='read-only') -> dict:
        """Run one agent without workflow gates. project is an absolute local folder. Default read-only; workspace-write requires an authorized editing task. Reuse request_id for transport retries. No automatic commit/push/publication."""
        guard();return request('/api/agents/start',dict(team=team,agent=agent,project=project,task=task,request_id=request_id,engine=engine,model=model,access=access))

    @mcp.tool(annotations=read)
    def get_agent_job(id:str) -> dict:
        """Read a single-agent job's real status, bounded log, result and errors."""
        from urllib.parse import quote
        return request('/api/agents/job?id='+quote(id,safe=''))

    @mcp.tool(annotations=read)
    def list_agent_jobs() -> dict:
        """List recent single-agent jobs. Does not launch agents."""
        return request('/api/agents/jobs')

    @mcp.tool(annotations=write)
    def cancel_agent_job(id:str) -> dict:
        """Cancel/dismiss the specified job when requested by the user."""
        guard();return request('/api/agents/cancel',{'id':id})

    @mcp.tool(annotations=write)
    def start_workflow(team:str,project:str,task:str,request_id:str,engine:str='',ui:str='auto',push:bool=False,remote:str='origin',scope:str='full',reference_mode:str='original') -> dict:
        """Start a team workflow. scope=planning-only (Editorial) stops after explicit Accept 1; no media production/export. reference_mode=original needs no style-reference clip; reference-based requires actual inspection. Full scope keeps both explicit approval gates. A start request never approves a gate. push only when explicitly requested."""
        guard();payload=dict(action='start',team=team,project=project,task=task,request_id=request_id,ui=ui,push=push,remote=remote,scope=scope,reference_mode=reference_mode)
        if engine:payload['engine']=engine
        client=bridge();client.health()
        from urllib.parse import quote
        graph=client.request('/api/workflows/template?team='+quote(team,safe=''))['graph']
        payload.pop('action');payload['graph']=graph
        return client.view(client.request('/api/workflows/create',payload))

    @mcp.tool(annotations=read)
    def get_workflow(id:str,wait_seconds:int=0) -> dict:
        """Get actual workflow state and approval evidence; bounded wait 0–30 seconds."""
        return bridge().run(dict(action='wait',id=id,wait_seconds=wait_seconds))

    @mcp.tool(annotations=read)
    def list_workflows() -> dict:
        """List recent workflows without starting work."""
        return bridge().run({'action':'list'})

    @mcp.tool(annotations=write)
    def set_workflow_scope(id:str,revision:int,scope:str='planning-only',reference_mode:str='original') -> dict:
        """At the user's request reduce an unapproved Editorial task to planning-only. Only failed/interrupted/awaiting-plan jobs with no production or active worker are eligible. Does not retry, execute, or approve anything."""
        guard();client=bridge();client.health()
        return client.view(client.request('/api/workflows/action',dict(id=id,revision=revision,action='set_scope',scope=scope,reference_mode=reference_mode)))

    @mcp.tool(annotations=write)
    def approve_workflow(id:str,revision:int,gate:int,user_confirmed:bool=False,selected_reference:str='') -> dict:
        """Approve only the displayed gate/revision after explicit user acceptance of its evidence. Silence, tests passing, or a start request are not approval."""
        guard();return bridge().run(dict(action='approve',id=id,revision=revision,gate=gate,user_confirmed=user_confirmed,selected_reference=selected_reference))

    @mcp.tool(annotations=write)
    def revise_workflow(id:str,revision:int,feedback:str) -> dict:
        """Relay the user's requested changes to a workflow, preserving approval gates."""
        guard();return bridge().run(dict(action='revise',id=id,revision=revision,feedback=feedback))

    @mcp.tool(annotations=write)
    def cancel_workflow(id:str,revision:int) -> dict:
        """Cancel a workflow at the user's request, using its latest revision."""
        guard();return bridge().run(dict(action='cancel',id=id,revision=revision))

    @mcp.tool(annotations=write)
    def report_agent(engine:str,team:str,agent:str,project:str,event:str,session:str='',skill:str='',summary:str='',result:str='') -> dict:
        """Report actual profile use in this chat through the central server. selected returns a session; reuse it. Server-owned jobs report themselves: do not duplicate their lifecycle. done only after successful delivery; never include secrets."""
        guard();return request('/api/agents/report',dict(engine=engine,team=team,agent=agent,project=project,event=event,session=session,skill=skill,summary=summary,result=result))
    return mcp


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',default=str(Path(__file__).resolve().parent/'workspace'));parser.add_argument('--server');args=parser.parse_args()
    create_server(args.workspace,args.server).run(transport='stdio')


if __name__=='__main__':main()
