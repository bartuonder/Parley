from typing import Any

import mcp_types as types
from mcp.server import Server, ServerRequestContext

from parley.tools.context import ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolRegistry


def build_server(registry: ToolRegistry, ctx: ToolContext) -> Server[None]:
    """An MCP server exposing the registry, with every call bound to one ticket's context."""

    async def list_tools(
        _: ServerRequestContext[None, Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        tools = [
            types.Tool(
                name=spec.name,
                description=spec.description,
                input_schema=spec.json_schema(),
                annotations=types.ToolAnnotations(
                    read_only_hint=spec.permission == Permission.READ
                ),
            )
            for spec in registry.specs
        ]
        return types.ListToolsResult(tools=tools)

    async def call_tool(
        _: ServerRequestContext[None, Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        result = registry.call(ctx, params.name, params.arguments or {})
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text", text=result.model_dump_json(exclude_none=ctx.compact_output)
                )
            ],
            structured_content=result.model_dump(mode="json"),
            is_error=not result.ok,
        )

    return Server("parley-tools", on_list_tools=list_tools, on_call_tool=call_tool)
