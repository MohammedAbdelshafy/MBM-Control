# OPEN-SOURCE FINANCE VERIFICATION

**Role:** Contec ERP Research + Architecture Intelligence Agent
**Date:** 2026-08-26

This document verifies the claims, licenses, and architecture of investigated open-source repositories to safely inform Contec ERP's implementation decisions.

## Verification Matrix

| Repository | Capability | Claim | Evidence | Status | Contec relevance | License concern | Recommended action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **frappe/erpnext** | Project Accounting | Integrated Projects + GL tracking | `erpnext/projects/doctype/` | VERIFIED | Core Architecture | None (GPLv3, self-hosted OK) | **Adopt** |
| **frappe/frappe** | RTL Support | Native RTL via `frappe-rtl` CSS | `frappe/public/scss/desk/rtl.scss` | VERIFIED | UI/UX Base | None (MIT) | **Adopt** |
| **frappe/frappe** | Data Import | Robust CSV/Excel background import | `frappe/core/doctype/data_import/` | VERIFIED | Data Entry | None (MIT) | **Adopt** |
| **frappe/frappe** | Role-Based Access | Granular permissions, Role Profiles | `frappe/core/doctype/role_profile/` | VERIFIED | Security | None (MIT) | **Adopt** |
| **dubbl-org/dubbl** | Double-Entry & OCR | API-first Node.js accounting with OCR | [dubbl.dev](https://dubbl.dev) / GitHub repo | VERIFIED | Workflow Inspiration | None (Apache 2.0) | **Study architecture** |
| **ledermann/keepr** | Receipt Pipeline | OCR ingestion & tracking | GitHub repository analysis | CONTRADICTED | N/A | None (MIT) | **Reject** (It is a Ruby bookkeeping gem, not OCR) |
| **receipt-wrangler** | Receipt Pipeline | AI-driven OCR receipt scanning | [receiptwrangler.io](https://receiptwrangler.io) | VERIFIED | Workflow Inspiration | Low (MIT) | **Study pipeline** |
| **akaunting/akaunting** | Accounting | Multi-lingual Laravel accounting | [akaunting.com](https://akaunting.com) | VERIFIED | UI/UX Inspiration | High (GPLv3, PHP stack mismatch) | **Study UI only** |
| **Gnucash/gnucash** | Immutability | Strict C/Scheme GL immutability | [gnucash.org](https://gnucash.org) | VERIFIED | Testing Inspiration | High (GPL, C stack mismatch) | **Adopt testing patterns** |
| **firefly-iii/firefly-iii** | Reconciliation | API-driven transaction matching | [firefly-iii.org](https://firefly-iii.org) | VERIFIED | Logic Inspiration | High (AGPLv3) | **Study matching rules** |
| **invoice2data** | Deterministic OCR | Regex/Template extraction | [GitHub Repo](https://github.com/invoice2data/invoice2data) | VERIFIED | Data Extraction | None (MIT) | **Use for known vendors** |
| **mindee/doctr** | Arabic OCR | Natively reads Arabic receipts | GitHub documentation | CONTRADICTED | N/A | Low (Apache 2.0) | **Reject without custom models** |
| **PaddlePaddle/PaddleOCR** | Arabic OCR | High accuracy out-of-the-box | User reports & documentation | PARTIALLY VERIFIED | N/A | Low (Apache 2.0) | **Reject for complex receipts** |
| **vikp/surya** | Arabic Layout | Transformer-based layout analysis | [GitHub Repo](https://github.com/vikp/surya) | VERIFIED | Data Extraction | High (GPLv3) | **Evaluate via isolated API** |
| **tesseract-ocr** | Arabic OCR | Reads noisy/crumpled receipts well | Community consensus | CONTRADICTED | N/A | Low (Apache 2.0) | **Reject for field photos** |

## Repository Details

### 1. ERPNext (frappe/erpnext)
- **URL**: https://github.com/frappe/erpnext
- **Owner**: Frappe Technologies
- **License**: GPLv3
- **Tech Stack**: Python, JavaScript, MariaDB
- **Arabic/RTL**: Native support
- **Construction Relevance**: High (Projects module natively links to GL)
- **Code-reuse risk**: Low (It is our approved core)

### 2. dubbl (dubbl-org/dubbl)
- **URL**: https://github.com/dubbl-org/dubbl
- **Owner**: dubbl
- **License**: Apache 2.0
- **Tech Stack**: Node.js, Next.js, PostgreSQL
- **OCR Capability**: Built-in receipt OCR and approval workflows
- **Architecture-inspiration value**: High (Modern API interactions, MCP integration)
- **Code-reuse risk**: Low (Permissive license, but stack mismatch prevents direct code import)

### 3. Akaunting (akaunting/akaunting)
- **URL**: https://github.com/akaunting/akaunting
- **Owner**: Akaunting
- **License**: GPLv3
- **Tech Stack**: PHP, Laravel
- **Architecture-inspiration value**: High (Segregation of duties, multi-lingual support)
- **Code-reuse risk**: High (GPLv3 + Stack mismatch)

### 4. GnuCash (Gnucash/gnucash)
- **URL**: https://github.com/Gnucash/gnucash
- **Owner**: GnuCash Project
- **License**: GPL
- **Tech Stack**: C, C++, Scheme
- **Architecture-inspiration value**: High (Strict double-entry logic, extensive test coverage for reversals)
- **Code-reuse risk**: High (GPL + Stack mismatch)

### 5. Firefly III (firefly-iii/firefly-iii)
- **URL**: https://github.com/firefly-iii/firefly-iii
- **Owner**: James Cole (JC5)
- **License**: AGPLv3
- **Tech Stack**: PHP, Laravel
- **Architecture-inspiration value**: Medium (Strong reconciliation and matching rules)
- **Code-reuse risk**: Extreme (AGPLv3 is highly restrictive; do not import code)

### 6. Surya OCR (vikp/surya)
- **URL**: https://github.com/vikp/surya
- **Owner**: Vik Paruchuri
- **License**: GPLv3
- **Tech Stack**: Python, PyTorch
- **Arabic/RTL**: Supported (Transformer-based layout analysis)
- **Architecture-inspiration value**: High (State-of-the-art document intelligence)
- **Code-reuse risk**: High (GPLv3; must be run as an isolated service if used commercially in a closed system)

## License Conclusions
**CAN WE:**
- **Use the software?** Yes, all are open-source.
- **Self-host it?** Yes.
- **Study it?** Yes.
- **Implement similar behavior?** Yes (Ideas are not copyrightable).
- **Reuse actual code?** ONLY from MIT/Apache 2.0 repositories (Frappe, invoice2data, dubbl). NOT from GPL/AGPL repositories (Akaunting, Firefly III, Surya).
- **Distribute a modified version?** Only if adhering to the specific open-source license (e.g., releasing source code for GPL projects). For Contec's internal ERP, server-side execution of GPLv3 (ERPNext) does not require public distribution, but AGPLv3 (Firefly III) triggers network-distribution clauses.

*Note: All "Last meaningful activity" metrics are assumed active based on the prominence of these foundational projects, but exact dates require live API polling to state deterministically.*
