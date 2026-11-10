"""Resolve tool schemas or execute one Prime tool call against its assigned MCP relay."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    command, *args = json.loads(os.environ["CARDWARS_MCP_COMMAND"])
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        await session.initialize()
        if len(sys.argv) == 1:
            tools = await session.list_tools()
            result = [tool.model_dump(mode="json") for tool in tools.tools]
        else:
            result = await session.call_tool(sys.argv[1], json.loads(sys.argv[2]))
            if result.isError:
                raise RuntimeError(result.content[0].text)
            result = [block.model_dump(mode="json") for block in result.content]
        print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
