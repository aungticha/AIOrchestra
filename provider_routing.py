"""Route new jobs using the same verified quota connections as the dashboard."""
import quota


def connections(workspace):
    statuses={'Codex':quota.cached_codex(),'Claude':quota.claude_status(workspace)}
    return {engine:value.get('status') in ('ok','api_mode') for engine,value in statuses.items()}


def resolve(engine, model, connected):
    available=[name for name,ready in connected.items() if ready]
    if len(available)==1 and engine!=available[0]:
        return available[0],''
    return engine,model
