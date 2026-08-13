# Skill: Google Antigravity SDK (Python)

## Overview
Architecture references, getting-started examples, and configuration guides for the Antigravity Python SDK (`google-antigravity`).

## Capabilities
- **Build Agents**: Scaffold new Antigravity agents, configure models, register custom Python tools, connect MCP servers
- **Safety Policies**: Declarative safety policies with deny-by-default templates and argument-level predicates
- **Lifecycle Hooks**: Pre/post execution hooks, error handlers, cleanup routines
- **Multi-Agent**: Agent delegation, handoff protocols, shared context
- **Structured Output**: Typed responses, JSON schema validation, streaming output
- **Multimodal**: Image/audio/video input handling, multimodal prompts
- **Observability**: Token usage tracking, cost estimation, latency monitoring

## When to Use
- Building a new Antigravity Python agent
- Configuring model routing or fallback chains
- Adding safety guardrails to agent tools
- Implementing multi-agent orchestration
- Debugging token usage or cost issues

## Quick Start

### Install
```bash
pip install google-antigravity
```

### Basic Agent
```python
from antigravity import Agent, tool

@tool
def search_database(query: str) -> str:
    """Search the product database."""
    return db.search(query)

agent = Agent(
    name="search_assistant",
    model="gemini-2.5-flash",
    tools=[search_database],
    system_instruction="You help users find products.",
)

response = agent.run("Find wireless headphones under $50")
```

### Safety Policy
```python
from antigravity import SafetyPolicy, DenyRule

safety = SafetyPolicy(
    deny=[
        DenyRule(pattern=r"DELETE\s+FROM\s+\w+", reason="No destructive SQL"),
        DenyRule(predicate=lambda args: args.get("amount", 0) > 10000, reason="Amount too high"),
    ]
)

agent = Agent(name="safe_agent", safety=safety, tools=[...])
```

### MCP Server Connection
```python
agent = Agent(
    name="mcp_agent",
    mcp_servers=[
        {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
    ],
)
```

## References
- https://github.com/google-antigravity/antigravity-sdk-python
- https://antigravity.google/docs/sdk/overview
