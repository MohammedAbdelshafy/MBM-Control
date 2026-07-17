# API Rate Limiting

**Tags:** engineering, api, dallas

We encountered HTTP 429 errors when pulling leads from Dallas Open Data API. We implemented exponential backoff in the evidence collector.