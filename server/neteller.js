/**
 * neteller.js — Canonical Neteller payout config & pay-link builder (Node/ESM).
 *
 * Single source of truth for every Neteller monetization surface in the repo
 * (server checkout/payout endpoints + frontend storefronts). Mirrors
 * MBM/Scripts/neteller_config.py so wallet details live in exactly one place
 * per runtime.
 *
 * Defaults (owned account):
 *   email      = abdelshafyclapps@gmail.com
 *   account_id = 4599228811
 *
 * Overridable via env:
 *   NETELLER_EMAIL
 *   NETELLER_ACCOUNT_ID
 *   NETELLER_PAY_BASE
 */

const NETELLER_EMAIL = process.env.NETELLER_EMAIL || 'abdelshafyclapps@gmail.com';
const NETELLER_ACCOUNT_ID = process.env.NETELLER_ACCOUNT_ID || '4599228811';
const NETELLER_PAY_BASE = process.env.NETELLER_PAY_BASE || 'https://member.neteller.com/pay';

/**
 * Build a 1-click Neteller member-pay URL.
 * @param {number} amount  Decimal amount to charge (e.g. 997.00).
 * @param {string} item    URL-safe item/sku label shown to the buyer.
 * @param {Object} [opts]  Optional overrides { currency, email, account, base }.
 * @returns {string} Fully-formed Neteller checkout URL.
 */
export function netellerLink(amount, item, opts = {}) {
  const email = opts.email || NETELLER_EMAIL;
  const account = opts.account || NETELLER_ACCOUNT_ID;
  const currency = opts.currency || 'USD';
  const base = opts.base || NETELLER_PAY_BASE;
  const params = new URLSearchParams({
    email,
    account,
    amount: Number(amount).toFixed(2),
    currency,
    item,
  });
  return `${base}?${params.toString()}`;
}

/** Human-readable wallet label, e.g. 'abdelshafyclapps@gmail.com (Account: 4599228811)'. */
export function netellerWalletLabel() {
  return `${NETELLER_EMAIL} (Account: ${NETELLER_ACCOUNT_ID})`;
}

export { NETELLER_EMAIL, NETELLER_ACCOUNT_ID, NETELLER_PAY_BASE };