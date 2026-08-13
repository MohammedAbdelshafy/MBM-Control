# Modern Web Rules

## Performance
- Always measure Core Web Vitals before declaring "done"
- Use `loading="lazy"` for below-the-fold images
- Prefer `font-display: swap` for web fonts
- Avoid layout shifts from dynamically injected content
- Use `content-visibility: auto` for large off-screen sections

## Accessibility
- Every interactive element must have an accessible name
- Use semantic HTML over generic `<div>` elements
- Test with keyboard navigation (Tab, Enter, Escape, Arrow keys)
- Ensure color contrast meets WCAG AA (4.5:1 for text)
- Add `aria-live` regions for dynamic content updates

## Security
- Never use `innerHTML` with user input
- Set `Content-Security-Policy` headers on all responses
- Use `HttpOnly` and `Secure` flags on session cookies
- Validate and sanitize all API inputs server-side
- Avoid `eval()`, `Function()`, and `setTimeout(string)`

## CSS
- Use CSS custom properties for theming
- Prefer `clamp()` for responsive typography
- Use `:has()` for parent selectors instead of JS workarounds
- Avoid `!important` except in utility classes
