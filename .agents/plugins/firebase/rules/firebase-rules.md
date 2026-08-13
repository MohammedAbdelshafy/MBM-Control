# Firebase Rules

## Security Rules
- Always write deny-by-default rules; explicitly allow only required operations
- Use `request.auth` to verify authentication before any write
- Validate data types and ranges in rules (not just the client)
- Use `get()` and `exists()` for cross-document authorization checks
- Test rules with the Firebase Emulator before deploying

## Firestore
- Design flat data models; avoid deep nesting (max 10 levels)
- Use batched writes for multi-document transactions
- Create composite indexes for complex queries
- Use `limit()` to prevent unbounded reads
- Cache reads client-side with `enablePersistence()`

## Authentication
- Never store passwords in Firestore
- Use Firebase Auth ID tokens (not custom tokens) for client auth
- Implement token refresh handling on the client
- Use custom claims for role-based access control
- Rate-limit auth endpoints

## Cloud Functions
- Use 2nd gen Cloud Functions (Cloud Run-based)
- Handle idempotency for retry-safe operations
- Set appropriate timeouts (up to 60min for 2nd gen)
- Use `onCall` for client-invoked functions (type-safe)
- Use `onDocumentWritten` for Firestore triggers

## Deployment
- Use `firebase deploy` for production; `firebase emulators:start` for dev
- Pin Firebase CLI version in `package.json`
- Use separate Firebase projects for dev/staging/prod
