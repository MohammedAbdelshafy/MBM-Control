# Antigravity SDK Rules

## Agent Design
- Give every agent a clear `name`, `description`, and `system_instruction`
- Use typed tools with proper docstrings (the SDK parses them for the LLM)
- Limit agent permissions to the minimum required (principle of least privilege)
- Use `safety` policies to block dangerous tool arguments

## Safety
- Always use `DenyRule` patterns for SQL injection, path traversal, and shell injection
- Set argument-level predicates for financial or destructive operations
- Log all tool invocations for audit trails
- Test safety policies with adversarial prompts before deployment

## Multi-Agent
- Use `Agent.handoff()` for delegation between agents
- Share context via structured `Context` objects, not raw strings
- Set clear termination conditions for agent loops
- Monitor token usage across agent chains

## Observability
- Track token usage per agent and per tool
- Set cost alerts for production workloads
- Use structured logging for all agent interactions
- Monitor latency percentiles (p50, p95, p99)

## MCP Servers
- Validate MCP server configs before connecting
- Use stdio transport for local servers, SSE for remote
- Handle MCP server crashes gracefully with retry logic
- Limit concurrent MCP connections to prevent resource exhaustion
