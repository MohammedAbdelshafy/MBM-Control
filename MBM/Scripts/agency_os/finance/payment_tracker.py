import time
import sys
import os

# Add MBM/Scripts to path so we can import telegram_notify
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import telegram_notify

def check_for_payments():
    """
    Checks real Stripe API for released payments if STRIPE_API_KEY is connected.
    Returns empty list if Stripe is not connected. ZERO mock data.
    """
    stripe_key = os.getenv("STRIPE_API_KEY")
    if not stripe_key:
        print("[Payment Tracker] Stripe API key not connected yet. Skipping payment check (Real Data Only mode).")
        return []

    try:
        import stripe
        stripe.api_key = stripe_key
        charges = stripe.Charge.list(limit=5)
        real_payments = []
        for c in charges.data:
            if c.paid:
                real_payments.append({
                    "client_name": c.billing_details.name or c.customer or "Verified Customer",
                    "amount": c.amount / 100.0,
                    "currency": c.currency.upper(),
                    "source": "Stripe (Verified)"
                })
        return real_payments
    except Exception as e:
        print(f"[Payment Tracker] Error querying Stripe API: {e}")
        return []

def track():
    payments = check_for_payments()
    for payment in payments:
        client = payment['client_name']
        amount = payment['amount']
        source = payment['source']
        
        msg = f"🚨 *GOD MODE: PAYMENT RECEIVED!* 🚨\n\n💰 Amount: ${amount:.2f}\n👤 Client: {client}\n🏦 Source: {source}\n\n_The AI Agency strikes again._"
        
        print(f"[Payment Tracker] Simulated Payment Received. (Telegram disabled for fake data)")
        # telegram_notify.send_message(msg)

if __name__ == "__main__":
    track()
