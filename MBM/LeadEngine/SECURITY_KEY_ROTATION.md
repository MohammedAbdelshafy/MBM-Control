# MBM LeadEngine — Security & Key Rotation Advisory

## Status: ACTION_REQUIRED (Production Key Rotation)

### 1. Key Inventory & Rotation Schedule

| Service | Environment Variable | Status | Recommendation |
| :--- | :--- | :--- | :--- |
| **Groq LPU** | `GROQ_API_KEY` | **REVOCATION / ROTATION SCHEDULED** | Rotate API token via console.groq.com and update secret manager / `.env`. |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | **SECURE (ENV-ONLY)** | Key loaded strictly via `os.getenv("NVIDIA_API_KEY")`. |
| **Google Gemini** | `GEMINI_API_KEY` | **SECURE (ENV-ONLY)** | Key loaded strictly via `os.getenv("GEMINI_API_KEY")`. |

### 2. Zero-Leak Policy Enforcement
- No source files or test scripts may hardcode API keys or credentials.
- All model dispatchers MUST load keys dynamically from environment variables.
- Telemetry loggers (`ai_routing_telemetry.jsonl`) MUST sanitize prompts and outputs to prevent PII or token leakage.
- Logs and database backups (`logs/db_backups/`, `logs/phound_wave/`) are strictly gitignored.
