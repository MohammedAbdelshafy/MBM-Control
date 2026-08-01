"""
Generate Contracts for Top 50 Scored Leads
==========================================
Reads texas_300_leads.csv, takes top 50 by score, generates AS-IS cash assignment contracts.
"""

import os
import csv
from datetime import datetime, timedelta

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")
CONTRACTS_DIR = os.path.join(MBM_ROOT, "LeadEngine", "contracts")

BUYER_NAME = "Contech AI Real Estate Acquisitions LLC"
BUYER_REP = "Omar"
BUYER_TITLE = "Authorized Representative"

# Assignment fee range
ASSIGNMENT_FEE_MIN = 5000
ASSIGNMENT_FEE_MAX = 25000


def calculate_offer(asking_price, equity):
    """Calculate offer price (70% of estimated value or asking - assignment fee)."""
    asking_price = int(float(asking_price)) if asking_price else 0
    equity = int(float(equity)) if equity else 0
    if asking_price > 0:
        # 70% of asking price
        offer = int(asking_price * 0.70)
    elif equity > 0:
        # Equity minus assignment fee
        offer = equity - 10000
    else:
        # Default range
        offer = 180000
    return max(offer, 75000)  # Minimum $75K


def generate_contract(lead, closing_date, contract_number):
    """Generate a contract markdown file."""
    offer_price = calculate_offer(lead["asking_price"], lead["est_equity"])
    emd = 10000
    balance = offer_price - emd

    # Format currency
    def fmt(n):
        return f"${n:,.2f}"

    def fmt_words(n):
        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        if n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + ("-" + ones[n % 10] if n % 10 else "")
        elif n < 1000:
            return ones[n // 100] + " Hundred" + (" and " + fmt_words(n % 100) if n % 100 else "")
        elif n < 1000000:
            return fmt_words(n // 1000) + " Thousand" + (" " + fmt_words(n % 1000) if n % 1000 else "")
        else:
            return fmt_words(n // 1000000) + " Million" + (" " + fmt_words(n % 1000000) if n % 1000000 else "")

    today = datetime.now().strftime("%B %d, %Y")
    closing = closing_date.strftime("%B %d, %Y")
    full_name = f"{lead['first_name']} {lead['last_name']}"
    address = lead.get("address", "TBD")
    city = lead.get("city", "TX")
    state = lead.get("state", "TX")

    contract = f"""# REAL ESTATE PURCHASE AND SALE AGREEMENT (AS-IS CASH ASSIGNMENT)

**DATE**: {today}
**CONTRACT #**: {contract_number}
**SELLER**: {full_name}
**BUYER / ASSIGNOR**: {BUYER_NAME} (and/or Assigns)
**PROPERTY ADDRESS**: {address}, {city}, {state}
**LEGAL DESCRIPTION**: TBD - To be determined at title company

---

### 1. AGREEMENT TO PURCHASE
Seller agrees to sell, and Buyer agrees to purchase the real property described above, together with all improvements, fixtures, and appurtenances attached thereto, in its current **AS-IS, WHERE-IS** condition with no warranties expressed or implied.

### 2. PURCHASE PRICE AND TERMS
- **Total Purchase Price**: **{fmt(offer_price)} USD** ({fmt_words(int(offer_price))} Dollars & 00/100)
- **Earnest Money Deposit (EMD)**: **{fmt(emd)} USD** to be deposited into Escrow/Title Company within 24 hours of agreement execution.
- **Balance at Closing**: **{fmt(balance)} USD** via certified wire transfer at settlement.

### 3. PROPERTY CONDITION
Buyer acknowledges that the property is being purchased in its current **AS-IS** condition. Buyer waives all inspection contingencies and agrees to accept the property in whatever condition it currently exists.

### 4. CLOSING COSTS AND DATES
- **Closing Date**: On or before **{closing}** (or sooner upon title clearance).
- **Closing Costs**: **Buyer agrees to pay 100% of traditional closing costs**, title policy insurance, and settlement fees. Seller pays ZERO agent commissions or closing fees.

### 5. ASSIGNMENT OF CONTRACT
Buyer retains full right to assign this Purchase & Sale Agreement to a qualified cash investor, private equity fund, or end buyer prior to settlement.

### 6. TITLE AND ENCUMBRANCES
Seller shall deliver clear and marketable title, free and clear of all liens, encumbrances, and defects, unless otherwise agreed in writing.

### 7. DEFAULT
In the event of default by either party, the non-defaulting party shall be entitled to all remedies available at law or in equity, including specific performance.

---

### SIGNATURE SECTION

**SELLER**:
____________________________________
**{full_name}**
Date: _______________

**BUYER / ASSIGNOR**:
____________________________________
**{BUYER_NAME}**
By: {BUYER_REP} ({BUYER_TITLE})
Date: {today}
"""
    return contract, offer_price, emd


def main():
    print("=" * 60)
    print("TOP 50 CONTRACT GENERATOR")
    print("=" * 60)

    # Read leads CSV
    csv_path = os.path.join(ARTIFACTS, "texas_300_leads.csv")
    leads = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    print(f"\nLoaded {len(leads)} leads")

    # Sort by score (highest first) and take top 50
    leads.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
    top50 = leads[:50]

    print(f"Top 50 leads selected (scores {top50[0]['score']} to {top50[-1]['score']})")

    # Generate contracts
    os.makedirs(CONTRACTS_DIR, exist_ok=True)
    generated = []
    total_emd = 0
    total_assignment = 0

    today = datetime.now()

    for i, lead in enumerate(top50):
        # Stagger closing dates (2-3 weeks out)
        closing_date = today + timedelta(days=14 + (i % 7))
        contract_num = f"CNT-{today.strftime('%Y%m%d')}-{i+1:03d}"

        contract_md, offer_price, emd = generate_contract(lead, closing_date, contract_num)

        # Write contract file
        full_name = f"{lead['first_name']}_{lead['last_name']}"
        filename = f"contract_{full_name}_{contract_num}.md"
        filepath = os.path.join(CONTRACTS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contract_md)

        generated.append({
            "contract_num": contract_num,
            "seller": f"{lead['first_name']} {lead['last_name']}",
            "city": lead["city"],
            "score": lead["score"],
            "grade": lead["grade"],
            "offer_price": offer_price,
            "emd": emd,
            "closing_date": closing_date.strftime("%Y-%m-%d"),
            "file": filename,
        })

        total_emd += emd
        total_assignment += offer_price

        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1}/50 contracts...")

    # Export contract summary
    summary_path = os.path.join(ARTIFACTS, "top50_contracts_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "contract_num", "seller", "city", "score", "grade",
            "offer_price", "emd", "closing_date", "file"
        ])
        writer.writeheader()
        writer.writerows(generated)

    print(f"\n{'=' * 60}")
    print("CONTRACT GENERATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Contracts generated: {len(generated)}")
    print(f"  Directory: {CONTRACTS_DIR}")
    print(f"  Summary: {summary_path}")
    print(f"\n  Total Offer Value: ${total_assignment:,.2f}")
    print(f"  Total EMD: ${total_emd:,.2f}")
    print(f"  Avg Offer: ${total_assignment/len(generated):,.2f}")
    print(f"\n  Top 5 contracts:")
    for c in generated[:5]:
        print(f"    {c['contract_num']} | {c['seller']:20s} | {c['city']:15s} | Score: {c['score']} | ${c['offer_price']:>10,.2f}")


if __name__ == "__main__":
    main()
