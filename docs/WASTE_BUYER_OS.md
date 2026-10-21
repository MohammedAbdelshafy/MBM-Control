# Waste Buyer OS

## Purpose

Waste Buyer OS converts a factory's actual monthly waste quotas into evidence-first buyer research specs.

Pipeline:

Factory quota -> material normalization -> buyer-category targeting -> Dawar marketplace/network -> external evidence -> buyer qualification -> meeting/offtake pipeline

It does not scrape or invent buyer demand. Public evidence must be attached before a buyer is treated as verified.

## Factory intake

Capture one record per waste stream:

| Field | Example |
|---|---|
| Material | EVA foam |
| kg/month | 12,000 |
| Form | Offcuts |
| Grade/spec | Virgin/recycled mix, if known |
| Contamination | Clean / mixed / adhesive / textile |
| Current disposition | Current buyer / disposal |
| Asking price | EGP/kg, if known |
| Pickup location | Factory location |
| Available from | Date |
| Evidence | Weighbridge, inventory, photos, invoices |

Prioritize EVA, rubber, PVC/PU, textile/mesh, soles/uppers, cardboard, and plastic film.

## Buyer qualification gate

A buyer becomes qualified only when:

1. The company is identifiable.
2. A public source proves it processes or purchases the relevant material.
3. The exact material/form is confirmed.
4. Logistics or collection coverage is confirmed.
5. Purchase capacity or MOQ is confirmed when available.
6. A commercial decision-maker is mapped.

A directory listing without material evidence is a prospect, not a qualified buyer.

## Integrations

### Dawar

Use Dawar as the marketplace/network rail. Its public marketplace is the transaction-discovery surface.

Marketplace: https://dawarapp.com/marketplace/

The code stores the public URL and role without assuming an undocumented API.

### Clay / prospecting

Search for businesses first, then map commercial roles such as owner, procurement, plant manager, recycling sales, or business development.

### Firecrawl / web research

Use the buyer's own website or reputable public sources to capture evidence for accepted materials, processing capabilities, facility location, industries served, collection radius, and public contact channels.

### LinkedIn

Use only after the company is identified, to map the relevant decision-maker role.

## Output contract

A research run should produce:

- quota
- material_canonical
- buyer_categories
- company_name
- website
- accepted_materials
- accepted_forms
- evidence_urls
- decision_maker_role
- score
- reasons
- missing_checks
- next_action

## Compliance boundary

Do not use this workflow to sell counterfeit branded footwear. Finished branded/counterfeit goods require lawful disposition. The initial revenue target is ordinary factory scrap and recyclable materials.
