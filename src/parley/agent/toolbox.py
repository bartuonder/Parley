import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import mcp_types as types
from mcp import Client

from parley.agent.result import ToolInvocation
from parley.tools.context import ToolContext
from parley.tools.registry import ToolRegistry
from parley.tools.server import build_server


def openai_tool(tool: types.Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


class Toolbox:
    """The agent's view of the tools: they are listed and called through an MCP client."""

    def __init__(self, client: Client, schemas: list[dict[str, Any]]) -> None:
        self._client = client
        self.schemas = schemas

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[ToolInvocation, str]:
        """Run a tool; returns the trace entry and the text to hand back to the model."""
        result = await self._client.call_tool(name, arguments)
        content = result.content[0]
        text = content.text if isinstance(content, types.TextContent) else "{}"
        payload = json.loads(text)
        ok = bool(payload.get("ok"))
        output = (
            payload.get("data") or {}
            if ok
            else {"error_code": payload.get("error_code"), "message": payload.get("message")}
        )
        return ToolInvocation(name=name, arguments=arguments, ok=ok, output=output), text


@asynccontextmanager
async def open_toolbox(registry: ToolRegistry, ctx: ToolContext) -> AsyncIterator[Toolbox]:
    async with Client(build_server(registry, ctx)) as client:
        listing = await client.list_tools()
        yield Toolbox(client, [openai_tool(t) for t in listing.tools])
