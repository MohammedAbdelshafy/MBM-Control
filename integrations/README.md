# Night-shift integrations — VibeFounder powers

One power per night, built from the backlog at `~/workspace/triage/VIBEFOUNDER_POWERS_2026-10-04.md`.
Branch: `night-shift/vibefounder-powers` (never merged to master without founder review).

| Power | Folder | Status 2026-10-04 |
|---|---|---|
| NVIDIA NIM free-tier routing (81 models, one key) | `integrations/nvidia-nim/` | Built + tested keyless; live chat needs `NVIDIA_API_KEY` from build.nvidia.com |
| Kapso CLI WhatsApp agent (AI Front Desk channel) | `integrations/kapso-whatsapp/` | CLI verified (v0.19.0), doctor green; number provisioning needs founder `kapso setup` |
| WhatsApp support agent on n8n stack (AI Front Desk ref impl) | `integrations/whatsapp-n8n-frontdesk/` | 28/28 harness tests pass (dry-run); go-live needs Meta app tokens |

Full build logs, skills and test evidence live under `~/workspace/night-shift/<power>/`.
