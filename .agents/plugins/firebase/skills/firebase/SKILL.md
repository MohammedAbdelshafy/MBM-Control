# Skill: Firebase

## Overview
Firebase agent skills for core services: Firestore, Authentication, App Hosting, Security Rules, Cloud Functions, and more.

## Capabilities
- **Firestore**: Schema design, queries, security rules, offline persistence, real-time listeners
- **Authentication**: Email/password, OAuth providers, custom claims, session management
- **Security Rules**: Write and test Firestore/Storage rules with rule language
- **App Hosting**: Deploy Next.js/Angular/SvelteKit apps with Firebase App Hosting
- **Cloud Functions**: Write, deploy, and test serverless functions (2nd gen)
- **Remote Config**: A/B testing, feature flags, parameter management
- **Analytics**: Event logging, custom dimensions, conversion tracking

## When to Use
- Setting up a new Firebase project
- Writing or reviewing Firestore security rules
- Deploying apps with Firebase App Hosting
- Configuring authentication flows
- Debugging Firebase Security Rules

## Key Patterns

### Firestore Data Model
```javascript
// Collections and documents
users/{userId}
  - name: string
  - email: string
  - role: "admin" | "user"
  - createdAt: timestamp

users/{userId}/posts/{postId}
  - title: string
  - content: string
  - published: boolean
```

### Security Rules Template
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if request.auth != null && request.auth.token.admin == true;
    }
  }
}
```

### Firebase Config
```javascript
const firebaseConfig = {
  apiKey: process.env.VITE_FIREBASE_API_KEY,
  authDomain: `${projectId}.firebaseapp.com`,
  projectId,
  storageBucket: `${projectId}.appspot.com`,
  messagingSenderId: "...",
  appId: "...",
};
```

## References
- https://firebase.google.com/docs/ai-assistance/agent-skills
- https://firebase.google.com/docs/firestore/security/rules
- https://firebase.google.com/docs/app-hosting
