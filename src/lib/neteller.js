/**
 * neteller.js (frontend) — Canonical Neteller pay-link builder for the dashboard.
 *
 * Mirrors server/neteller.js + MBM/Scripts/neteller_config.py so every checkout
 * surface in the repo pays into the same wallet.
 */

export const NETELLER_EMAIL = 'abdelshafyclapps@gmail.com';
export const NETELLER_ACCOUNT_ID = '4599228811';
export const NETELLER_PAY_BASE = 'https://member.neteller.com/pay';

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

export function netellerWalletLabel() {
  return `${NETELLER_EMAIL} (Account: ${NETELLER_ACCOUNT_ID})`;
}