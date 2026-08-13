# Skill: Modern Web Guidance

## Overview
Expert-vetted, evergreen guidance for building accessible, performant, and secure modern web experiences.

## Capabilities
- **Accessibility (a11y)**: WCAG 2.1 compliance, semantic HTML, ARIA patterns, screen reader optimization
- **Performance**: Core Web Vitals (LCP, INP, CLS), lazy loading, code splitting, bundle optimization
- **Security**: CSP headers, XSS prevention, CSRF protection, secure auth patterns
- **Progressive Enhancement**: Service workers, offline-first, PWA best practices
- **CSS Modern**: Container queries, :has(), cascade layers, view transitions, color-mix()
- **JavaScript**: Import maps, Web Components, Islands architecture, Streaming SSR

## When to Use
- Building or reviewing React/Vue/Svelte/Angular components
- Auditing page performance or accessibility
- Setting up new frontend projects with best practices
- Reviewing PRs for web code quality

## Key Patterns

### Performance Budget
```
LCP < 2.5s  |  INP < 200ms  |  CLS < 0.1
```

### Accessibility Checklist
- Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`
- Focus management: visible focus rings, logical tab order
- Color contrast: 4.5:1 minimum for text
- Image alt text: descriptive, not redundant
- Form labels: explicit `<label>` associations

### Security Headers
```
Content-Security-Policy: default-src 'self'; script-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

## References
- https://web.dev/vitals
- https://developer.chrome.com/docs/lighthouse/overview
- https://www.w3.org/WAI/WCAG21/quickref/
