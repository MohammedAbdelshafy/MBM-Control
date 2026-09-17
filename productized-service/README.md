# MBM Digital Product Factory

The productized-service tree is the canonical source for reusable offers and customer-delivery artifacts.

## Factory boundary

The factory is deterministic and side-effect free:

`OFFER ASSETS → VALIDATE → BUILD CUSTOMER PACK → HUMAN DELIVERY`

Payment manifests may contain private account metadata. They are not customer-pack inputs. External outreach, calls, publishing, payments, and deployments remain outside this factory and require their own authorization gates.

## Current canonical offer

`ai-consultancy-sprint`

The Audit offer has a delivery kit containing:

- evidence-first AI Growth Audit
- five sales-script templates
- lead-map template
- 72-hour implementation plan

The customer pack builder lives in `productized_service.factory`.

Example:

```bash
python -m productized_service.factory productized-service/ai-consultancy-sprint ./dist/ai-sprint-audit
```

Commercial validation is never inferred from the presence of payment links or checkout manifests.
