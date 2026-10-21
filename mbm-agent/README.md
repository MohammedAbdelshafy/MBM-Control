# MBM Agent Package — Lead Cleaner (v1)

One capability, many distributions. This is the first commercial package in the MBM agent distribution strategy.

## What's built

```
/mbm-agent/
  /mcp/                 ✅ BUILT & TESTED
    server.py           — 4 tools: clean_leads, score_lead, verify_email, generate_outreach
    requirements.txt
    README.md           — registry-ready docs
  /chatgpt-app/         🔲 next
  /n8n/                 🔲 next
  /huggingface/         🔲 next
  /landing/             🔲 next
```

## Distribution checklist

| Channel | Action | Status |
|---------|--------|--------|
| MCP Registry | Publish server.py + README | Ready to submit |
| Smithery | Deploy MCP server | Ready |
| Glama | List with health checks | Ready |
| LobeHub | Submit as skill | Ready |
| Hugging Face | Wrap as Space demo | TODO |
| n8n | "AI Lead Cleaner" workflow template | TODO |
| ChatGPT Apps SDK | Submit app | TODO |
| GitHub commit | Push to MBM-Control | TODO |

## Commercial ladder

```
FREE (MCP, 500 leads/mo)
  → Hosted API ($49/mo)
  → Pro ($199/mo, 10K leads)
  → White-label for agencies ($999/mo)
  → Enterprise (custom)
```

## Next: push to GitHub

Commit this package to MBM-Control under `/mbm-agent/` so it's versioned alongside the core engine.
