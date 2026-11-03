"""Exercise the real SDK client/server stdio handshake without launching models."""
import argparse
import asyncio
import json
from pathlib import Path
import sys


async def probe(workspace):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    parameters=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).resolve().parent/'orchestra_mcp.py'),'--workspace',workspace])
    async with stdio_client(parameters) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize();tools=await session.list_tools();health=await session.call_tool('health',{})
            if health.isError:raise RuntimeError(str(health.content))
            catalog=await session.call_tool('list_agents',{})
            if catalog.isError:raise RuntimeError(str(catalog.content))
            return dict(ok=True,transport='stdio',tools=[t.name for t in tools.tools],health=[c.text for c in health.content if hasattr(c,'text')])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True);args=parser.parse_args()
    print(json.dumps(asyncio.run(probe(args.workspace)),ensure_ascii=False))
