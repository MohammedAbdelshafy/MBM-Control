#!/usr/bin/env python3
"""nvidia_chat.py — tiny CLI for one NVIDIA NIM chat completion.

Usage:
    python3 bin/nvidia_chat.py --model <model-id> "your prompt"
    python3 bin/nvidia_chat.py "your prompt"          # uses pick_model("chat")

Requires NVIDIA_API_KEY in the environment (free key from
https://build.nvidia.com). Without it, prints the exact export command and
exits 2.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nvidia_router import (
    API_KEY_ENV,
    BASE_URL,
    NvidiaAuthError,
    NvidiaRateLimitError,
    NvidiaRouterError,
    chat,
    pick_model,
)


def main(argv=None):
    ap = argparse.ArgumentParser(description="One-shot NVIDIA NIM chat completion")
    ap.add_argument("--model", default=None, help="exact model id (default: pick_model('chat'))")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("prompt", help="the user prompt to send")
    args = ap.parse_args(argv)

    if not os.environ.get(API_KEY_ENV):
        print(
            f"error: {API_KEY_ENV} is not set.\n\n"
            f"Get a FREE API key at https://build.nvidia.com (sign in, "
            f"generate key), then run:\n\n"
            f"    export {API_KEY_ENV}='nvapi-YOUR_KEY_HERE'\n\n"
            f"then re-run this command. No key is bundled with this tool and "
            f"none will be invented.",
            file=sys.stderr,
        )
        return 2

    model = args.model or pick_model("chat")
    try:
        resp = chat(
            model,
            [{"role": "user", "content": args.prompt}],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except (NvidiaAuthError, NvidiaRateLimitError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except NvidiaRouterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        print(resp["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        print(resp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
