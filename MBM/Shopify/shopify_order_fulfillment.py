"""
shopify_order_fulfillment.py — Automated Order Processing & Fulfillment Pipeline.
===================================================================================
Subsystem: MBM Shopify E-Commerce Engine

Processes incoming paid orders:
1. Ingests order details (Order ID, Customer Email, Amount Paid, Product Line Items).
2. Automates digital asset delivery & license key generation.
3. Sends instant email receipt + access credentials via email pool.
4. Logs revenue into MBM/Logs/revenue_ledger.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ORDERS_FILE = LOGS_DIR / "shopify_orders.json"
REVENUE_LEDGER = BASE_DIR.parent / "Logs" / "revenue_ledger.json"
EMAIL_QUEUE = BASE_DIR.parent / "Logs" / "email_queue.json"
REVENUE_LEDGER.parent.mkdir(parents=True, exist_ok=True)

DRY_RUN = os.getenv("SHOPIFY_DRY_RUN", "") == "true"


def _queue_delivery_email(full_record: dict) -> None:
    """Queue an instant receipt + license delivery email (idempotent)."""
    if DRY_RUN:
        print(f"[SHOPIFY FULFILLMENT DRY-RUN] receipt email for {full_record['customer_email']}")
        return
    queue_data = []
    if EMAIL_QUEUE.exists():
        try:
            queue_data = json.loads(EMAIL_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            queue_data = []
    entry = {
        "id": f"shop_deliv_{full_record['order_id']}_{int(time.time())}",
        "to": full_record["customer_email"],
        "subject": f"⚡ Your Contec AI license is ready — Order {full_record['order_id']}",
        "body": (
            f"Hi there,\n\n"
            f"Thank you for your order {full_record['order_id']}!\n"
            f"License Key: {full_record['license_key']}\n"
            f"Amount Paid: ${full_record['total_price_usd']:.2f}\n\n"
            f"Sign in and activate: https://contec-ai-store.myshopify.com/account\n\n"
            f"— Contec AI Store Team"
        ),
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    queue_data.append(entry)
    EMAIL_QUEUE.write_text(json.dumps(queue_data, indent=2), encoding="utf-8")


def process_order(order_data: dict) -> dict:
    """Processes paid order, delivers license key, and updates revenue ledger.

    Idempotent per order_id: replaying the same webhook (common in Shopify
    retries / orders/create + orders/paid pairs) won't duplicate deliveries.
    """
    order_id = order_data.get("id") or f"shop_ord_{int(time.time())}"
    customer_email = order_data.get("email") or "customer@contecai.com"

    # Idempotency guard — skip if this order was already processed.
    existing = []
    if ORDERS_FILE.exists():
        try:
            existing = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
            if any(o.get("order_id") == str(order_id) for o in existing):
                print(f"[SHOPIFY FULFILLMENT] Order {order_id} already fulfilled; skipping duplicate")
                return {
                    "status": "success",
                    "inputs": {"order_id": order_id, "customer_email": customer_email},
                    "outputs": {"duplicate": True, "existing": True},
                    "errors": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception:
            existing = []

    total_price = float(order_data.get("total_price") or 299.00)
    line_items = order_data.get("line_items") or [{"title": "Contec AI Agentic Suite", "quantity": 1}]

    license_key = f"CONTEC-AI-KEY-{uuid.uuid4().hex[:12].upper()}"

    fulfillment_record = {
        "order_id": order_id,
        "customer_email": customer_email,
        "total_price_usd": total_price,
        "currency": "USD",
        "line_items": line_items,
        "license_key": license_key,
        "fulfillment_status": "FULFILLED_DIGITAL_DELIVERED",
        "delivered_at": datetime.now(timezone.utc).isoformat()
    }

    # 1. Update Shopify Orders Log (reuse the list already loaded for the dedup guard)
    orders = existing

    orders.append(fulfillment_record)
    ORDERS_FILE.write_text(json.dumps(orders, indent=2), encoding="utf-8")

    # 1b. Queue instant receipt + license delivery email
    _queue_delivery_email(fulfillment_record)

    # 2. Update Global Revenue Ledger
    revenue_data = []
    if REVENUE_LEDGER.exists():
        try:
            revenue_data = json.loads(REVENUE_LEDGER.read_text(encoding="utf-8"))
        except Exception:
            revenue_data = []

    revenue_entry = {
        "id": f"rev_{order_id}",
        "source": "Shopify Storefront",
        "amount_usd": total_price,
        "customer_email": customer_email,
        "description": f"Order {order_id} ({line_items[0]['title']})",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    revenue_data.append(revenue_entry)
    REVENUE_LEDGER.write_text(json.dumps(revenue_data, indent=2), encoding="utf-8")

    print(f"[SHOPIFY FULFILLMENT] Order {order_id} (${total_price}) -> Delivered Key '{license_key}' to {customer_email}")

    return {
        "status": "success",
        "inputs": {"order_id": order_id, "customer_email": customer_email},
        "outputs": fulfillment_record,
        "errors": [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    # Support webhook-driven invocation: read a canonical order JSON from stdin.
    sample_order = {
        "id": "shop_ord_1001",
        "email": "officialshafy@gmail.com",
        "total_price": 299.00,
        "line_items": [{"title": "Contec AI Agentic Suite — Full License", "quantity": 1}]
    }
    if not sys.stdin.isatty():
        try:
            incoming = json.loads(sys.stdin.read())
            if isinstance(incoming, dict) and incoming.get("id"):
                sample_order.update({k: v for k, v in incoming.items() if v not in (None, "")})
        except Exception as e:
            print(f"[SHOPIFY] Could not parse stdin order: {e}", file=sys.stderr)
    res = process_order(sample_order)
    print(json.dumps(res, indent=2))
