from parley.tools.policy import POLICY_TOOLS
from parley.tools.read import READ_TOOLS
from parley.tools.registry import ToolRegistry
from parley.tools.write import WRITE_TOOLS


def default_registry() -> ToolRegistry:
    return ToolRegistry([*READ_TOOLS, *POLICY_TOOLS, *WRITE_TOOLS])
