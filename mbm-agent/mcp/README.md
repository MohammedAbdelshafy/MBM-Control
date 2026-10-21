# MBM Lead Cleaner — MCP Server

Turn any agent into a lead-verification machine. Clean, score, and dedupe lead lists; verify emails; generate personalized outreach.

## Tools

| Tool | What it does |
|------|--------------|
| `clean_leads` | Clean, verify, dedupe, and score a CSV lead list (0-100 per lead) |
| `score_lead` | Score a single lead with signal breakdown |
| `verify_email` | Deep-check an email (syntax, disposable, role-based, free vs work) |
| `generate_outreach` | Generate a personalized cold email for a lead |

## Quick start

```bash
pip install -r requirements.txt
python server.py
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "mbm-lead-cleaner": {
      "command": "python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Example

```
User: Clean this list: name,email,phone,company / John Smith,john@acme.com,555-123-4567,Acme Corp
Agent: [calls clean_leads] → 1 VERIFIED (score 100), ready to dial.
```

## Commercial

Free for up to 500 leads/month. Hosted API + white-label at [MBM](https://github.com/MohammedAbdelshafy/MBM-Control).
Built by MBM — the revenue intelligence layer for AI agents.
