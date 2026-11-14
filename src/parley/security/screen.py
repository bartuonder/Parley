from parley.security.scan import ScanResult, scan_text
from parley.tools.context import ToolContext


def screen_ticket(ctx: ToolContext, subject: str, body: str) -> ScanResult:
    """Scan the ticket text; a hit locks refunds and cancellations for this ticket."""
    if not ctx.guards.scan:
        return ScanResult(False)
    result = scan_text(f"{subject}\n{body}")
    if result.flagged:
        ctx.write_locked = True
        ctx.guard_events.append("injection:" + ",".join(result.reasons))
    return result


def screen_tool_output(ctx: ToolContext, tool: str, text: str) -> ScanResult:
    """Scan what a tool returned; hostile text in a record or a passage locks the ticket too."""
    if not ctx.guards.scan:
        return ScanResult(False)
    result = scan_text(text)
    if result.flagged:
        ctx.write_locked = True
        ctx.guard_events.append(f"injection:{tool}:" + ",".join(result.reasons))
    return result
