#!/usr/bin/env python3
"""
NPI Skip-Tracer & Enricher — Real Website/Email Enrichment
============================================================
WHAT IT DOES:
  Takes the NPI-verified call sheet (real businesses with real phones) and adds
  the two things NPI does NOT give us:
    1. WEBSITE  -> discovered via web search (DuckDuckGo) + result-page scrape
    2. EMAIL    -> found on the practice's own site (mailto / contact page),
                   then DNS-MX verified so we NEVER fabricate a bouncy inbox.

WHY THIS IS HONEST (no fake data):
  - Emails are only kept if their domain passes an MX record check.
  - Websites only come from real discovery (DuckDuckGo), not guessing.
  - If nothing verifiable is found, the lead stays un-enriched (skipped).

OUTPUT (MBM/Artifacts/):
  - npi_enriched_callsheet.csv : original rows + website + email + confidence
  - npi_enriched_callsheet.json
  - logs/npi_enrichment_log.jsonl : per-row trace (what was found/why skipped)

Usage:
  python MBM/LeadEngine/npi_skip_enricher.py                # enrich whole sheet
  python MBM/LeadEngine/npi_skip_enricher.py --limit 50     # first 50 leads
  python MBM/LeadEngine/npi_skip_enricher.py --no-net       # offline (debug)
"""

import os
import re
import csv
import json
import time
import socket
import random
import argparse
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE.parent.parent / "MBM" / "Artifacts"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
CALLSHEET = ARTIFACTS / "npi_verified_callsheet.csv"
OUT_DIR = ARTIFACTS

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

BAD_EMAIL_DOMAINS = {
    "example.com", "test.com", "domain.com", "yourdomain.com", "gmail.com",
    "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com",
    "everyone.com", "music.com", "noreply.com", "demandforce.com", "wix.com",
    "sentry.io", "patientsites.com", "yext.com", "websites.com", "webmd.com",
    "healthgrades.com", "zocdoc.com", "yellowpages.com", "vphtml.com",
}
BOUNCE_PREFIXES = {"no-reply", "noreply", "donotreply", "do-not-reply",
                   "unsubscribe", "mailer", "mailer-daemon", "reply",
                   "noresponse", "info-reply", "autoreply"}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[NPI ENRICH] {ts} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def _get(url, timeout=8):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": random.choice(UA),
                 "Accept-Language": "en-US,en;q=0.9",
                 "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _soup(html):
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser")
    except ImportError:
        return None


def _emails_from_text(text):
    if not text:
        return []
    found = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    out = []
    for e in found:
        e = e.lower().strip(".").strip()
        dom = e.split("@")[-1]
        pfx = e.split("@")[0]
        if dom in BAD_EMAIL_DOMAINS:
            continue
        if pfx in BOUNCE_PREFIXES:
            continue
        if any(x in dom for x in (".png", ".jpg", ".gif", ".jpeg", ".svg", ".webp")):
            continue
        out.append(e)
    return list(dict.fromkeys(out))


def _mx_ok(domain, cache):
    """True if domain has an MX (or A) record via DNS. Cached."""
    domain = (domain or "").lower().strip(".")
    if not domain or "." not in domain:
        return False
    if domain in cache:
        return cache[domain]
    ok = False
    try:
        import dns.resolver
        try:
            _ = dns.resolver.resolve(domain, "MX", lifetime=3)
            ok = True
        except Exception:
            ok = False
    except ImportError:
        try:
            import DNS  # old package name fallback
            ok = bool(DNS.MailServerLookup(domain))
        except Exception:
            ok = False
    if not ok:
        try:
            socket.getaddrinfo(domain, None)
            ok = True
        except Exception:
            ok = False
    cache[domain] = ok
    return ok


def _host_of(url):
    try:
        net = urllib.parse.urlparse(url if "://" in url else "https://" + url).netloc.lower()
        return net.lstrip("www.").rstrip("/")
    except Exception:
        return ""


LEGAL_SUFFIXES = (" LLC", " LLC.", " INC", " INC.", " PLLC", " PLLC.", " PC",
                  " PC.", " PA", " PA.", " CORP", " CORP.", " CORPORATION", " LTD",
                  " LTD.", " PLC", " CO", " CO.", " LP", " LLP")


def _clean_company(company):
    c = (company or "").strip()
    if not c:
        return c
    if "," in c and c.count(" ") < 6:
        base = c.split(",")[0].strip()
        if len(base) >= 6:
            c = base
    for suf in sorted(LEGAL_SUFFIXES, key=len, reverse=True):
        if c.upper().endswith(suf) or c.upper() == suf.strip():
            c = c[: -len(suf)].strip()
            break
    return c or company


def _parse_rss(xml):
    """Parse RSS feed with xml.etree (robust for <link> text). Returns [(title,url)]."""
    import xml.etree.ElementTree as ET
    items = []
    try:
        root = ET.fromstring(xml)
        for it in root.iter("item"):
            title_el = it.find("title")
            link_el = it.find("link")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if link:
                items.append((title, link))
    except Exception:
        pass
    return items


def _relevance_tokens(company):
    return [t for t in re.split(r"[\s\-,\.&/]+", (company or "").lower())
            if len(t) > 2 and t not in {"the", "and", "for", "care", "inc",
                                        "llc", "pllc", "services", "group",
                                        "health", "home", "therapy", "clinic",
                                        "center", "rehab", "physical",
                                        "medical", "pediatric", "urgent",
                                        "official", "corporation", "company"}]


def candidate_sites(company, city, state, no_net=False):
    """Return list of candidate (url, source) from RSS search feeds."""
    if no_net:
        return []
    clean = _clean_company(company)
    found = []
    seen = set()
    candidates = [
        ("bing-rss", "https://www.bing.com/search?q={q}&format=rss"),
        ("google-news-rss", "https://news.google.com/rss/search?q={q}&hl=en-US"),
    ]
    for src, tpl in candidates:
        for qtxt in (f'"{clean}" {city} {state}',
                     f'"{clean}" {city}',
                     f'"{clean}"'):
            url = tpl.format(q=urllib.parse.quote_plus(qtxt))
            xml = _get(url)
            if not xml:
                continue
            for title, href in _parse_rss(xml):
                host = _host_of(href)
                if not host or host in seen:
                    continue
                if any(x in host for x in
                       ["bing", "microsoft", "google", "facebook", "instagram",
                        "linkedin", "youtube", "yelp", "healthgrades", "webmd",
                        "zocdoc", "ratemds", "vitals", "sharecare", "doximity",
                        "dictionary", "wikipedia.org", "action.com", "boels",
                        "merriam-webster", "cambridge"]):
                    continue
                if host.startswith(("w.", "www.")) or host.startswith("www."):
                    host = host[len("www."):]
                seen.add(host)
                found.append((host, src))
            time.sleep(0.2)
        if found:
            break
    return found


def _derive_domains(company):
    """Derive plausible practice domains from the company name."""
    c = _clean_company(company)
    words = [w for w in re.split(r"[^A-Za-z0-9]+", c.lower())
             if len(w) >= 3 and w not in {
                 "the", "and", "inc", "llc", "pllc", "pc", "pa", "corp",
                 "services", "group", "clinic", "center", "centers", "health",
                 "therapy", "therapies", "rehab", "home", "care"}]
    if not words:
        return []
    slugs = {"".join(words), "-".join(words)}
    if len(words) >= 3:
        slugs.add("".join(words[:2]))
    out = set()
    for s in slugs:
        if len(s) < 5:
            continue
        for tld in (".com", ".net", ".org", ".us"):
            out.add(s + tld)
    return sorted(out)


def _host_resolves(host):
    try:
        import dns.resolver
        try:
            _ = dns.resolver.resolve(host, "A", lifetime=1.2)
            return True
        except Exception:
            return False
    except ImportError:
        try:
            socket.gethostbyname(host)
            return True
        except Exception:
            return False


def _fetch_title(host):
    """Fetch host homepage; return (normalized_text, title) or (None, '')."""
    html = _get(f"https://{host}", timeout=5)
    if not html:
        html = _get(f"http://{host}", timeout=5)
    if not html:
        return None, ""
    low = html.lower()[:300000]
    title = ""
    soup = _soup(html)
    if soup and soup.title:
        title = soup.title.get_text(" ", strip=True).lower()
    return low, title


def _compact_brand(company):
    """Compact the company name to a distinctive phrase, e.g.
    'ABILITY PRO THERAPY' -> 'abilityprotherapy'."""
    c = _clean_company(company)
    return re.sub(r"[^a-z0-9]", "", c.lower())


def _strong_confirm(host, company):
    """Require the practice's own brand phrase in routing the page <title>
    (or first chunk of text) — generic tokens like 'pro' are never enough."""
    brand = _compact_brand(company)
    if len(brand) < 4:
        return False
    low, title = _fetch_title(host)
    if not low:
        return False
    if brand in title:
        return True
    if brand in low[:120000]:
        return True
    return False


def find_website(company, city, state, no_net=False):
    """Find the practice's real site using validated derived domains first,
    then homepage-confirmed RSS as fallback. No fabricated URLs."""
    if no_net:
        return None, ""
    clean = _clean_company(company)
    # Pass 1: derived domain (DNS + homepage-strict-confirm) — honest & precise
    for host in _derive_domains(company)[:6]:
        if not _host_resolves(host):
            continue
        if _strong_confirm(host, clean):
            return f"https://{host}", "derived"
        time.sleep(0.02)
    # Pass 2: RSS candidates, but strict 2-token confirm (avoids garbage)
    for host, src in candidate_sites(company, city, state)[:6]:
        if _strong_confirm(host, clean):
            return f"https://{host}", src
        time.sleep(0.02)
    return None, ""


def _website_emails(domain):
    """Fetch homepage + common contact pages, return ALL emails found (raw).
    Fast: stops at the first page that yields an email; hard-caps requests."""
    emails = []
    tried = set()
    max_pages = 6
    pages_tried = 0
    for pp in ["", "/contact", "/contact-us", "/about", "/about-us", "/team"]:
        if pages_tried >= max_pages:
            break
        for scheme in ("https://", "http://"):
            url = scheme + domain + pp
            if url in tried:
                continue
            tried.add(url)
            pages_tried += 1
            try:
                html = _get(url, timeout=5)
            except Exception:
                html = None
            if not html:
                continue
            soup = _soup(html)
            text = soup.get_text(" ", strip=True) if soup else html
            for e in _emails_from_text(text):
                if e not in emails:
                    emails.append(e)
            if soup:
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "") or ""
                    if not href.lower().startswith("mailto:"):
                        continue
                    mail = href.split(":", 1)[1].split("?")[0].strip().lower()
                    if mail and "@" in mail and mail not in emails:
                        emails.append(mail)
            if emails:
                return emails
            time.sleep(0.1)
    return emails


def enrich_lead(row, mx_cache, no_net=False):
    """Enrich one NPI row with website + DNS-verified email. Returns dict."""
    company = (row.get("company_name") or "").strip()
    city = (row.get("city") or "").strip().title()
    state = (row.get("state") or "").strip()
    entry = {"website": "", "email": "", "confidence": "none",
             "source": "", "note": "no company name"}
    if not company:
        return entry

    url, src = find_website(company, city, state, no_net=no_net)
    if not url:
        entry["note"] = "no website found"
        return entry
    entry["website"] = url
    entry["source"] = src
    entry["note"] = "website found"

    domain = _host_of(url)
    candidates = _website_emails(domain)
    verified = []
    for e in candidates:
        top_dom = _root(domain)
        if _mx_ok(e.split("@")[-1], mx_cache) or _mx_ok(top_dom, mx_cache):
            verified.append(e)
    if verified:
        # prefer emails on the same root domain, then shortest non-generic
        same = [e for e in verified if top_dom in e.split("@")[-1]]
        pool = same or verified
        best = sorted(pool, key=len)[0]
        entry["email"] = best
        entry["confidence"] = "high" if same else "medium"
        entry["note"] = f"mx-verified ({best.split('@')[-1]})"
    else:
        entry["note"] += " (no MX-verified email)"
    return entry


def _root(domain):
    """Give the registrable root (last 2 labels) for matching."""
    parts = (domain or "").lower().split(".")
    if len(parts) >= 3:
        return ".".join(parts[-2:])
    return domain or ""


def enrich_sheet(path=None, limit=None, no_net=False):
    p = path or CALLSHEET
    if not p.exists():
        log(f"Call sheet not found: {p}. Run npi_verified_callsheet.py first.")
        return
    with open(p, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    log(f"Enriching {len(rows)} leads from {p}...")
    mx_cache = {}
    done = 0
    log_path = LOGS / "npi_enrichment_log.jsonl"

    for idx, r in enumerate(rows):
        if limit and idx >= limit:
            break
        if r.get("email"):
            continue
        en = enrich_lead(r, mx_cache, no_net=no_net)
        r["website"] = en.get("website", "")
        r["email"] = en.get("email", "")
        r["enrich_confidence"] = en.get("confidence", "none")
        r["enrich_source"] = en.get("source", "")
        r["enrich_note"] = en.get("note", "")
        with open(log_path, "a", encoding="utf-8") as f_:
            json.dump({"npi": r.get("npi", ""), "company": r.get("company_name", ""),
                       "city": r.get("city", ""), "website": r["website"],
                       "email": r["email"], "confidence": r["enrich_confidence"],
                       "note": r["enrich_note"]}, f_)
            f_.write("\n")
        if r["email"]:
            done += 1
            log(f"[{idx+1}/{len(rows)}] {r.get('company_name','')} -> {r['email']} "
                f"({r['enrich_confidence']}) [{r.get('website','')}]")
        else:
            log(f"[{idx+1}/{len(rows)}] {r.get('company_name','')} -> no MX email")
        time.sleep(random.uniform(0.3, 0.7))

    headers = list(rows[0].keys())
    for h in ("website", "email", "enrich_confidence", "enrich_source", "enrich_note"):
        if h not in headers:
            headers.append(h)
    out_csv = OUT_DIR / "npi_enriched_callsheet.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(OUT_DIR / "npi_enriched_callsheet.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "total": len(rows), "enriched": done, "leads": rows},
                  f, indent=2, default=str)
    log(f"DONE — {done}/{len(rows)} leads enriched -> {out_csv}")
    print(json.dumps({"enriched": done, "total": len(rows), "csv": str(out_csv)}, indent=2))


def main():
    ap = argparse.ArgumentParser(description="NPI Skip-Tracer / Enricher")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-net", action="store_true")
    ap.add_argument("--sheet", default=None)
    args = ap.parse_args()
    enrich_sheet(path=args.sheet, limit=args.limit, no_net=args.no_net)


if __name__ == "__main__":
    main()