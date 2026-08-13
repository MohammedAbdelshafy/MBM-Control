# Chrome DevTools Rules

## Puppeteer Scripts
- Always close the browser instance in a `finally` block
- Use `page.waitForSelector()` before interacting with elements
- Set appropriate `timeout` values for all navigation and wait calls
- Use `page.setViewport()` for consistent responsive testing
- Handle dialog boxes with `page.on('dialog')` to prevent hangs

## Accessibility Testing
- Run axe-core audits on every page before manual testing
- Fix critical and serious violations before merging
- Test with screen readers (NVDA, VoiceOver) for key user flows
- Ensure all images have meaningful `alt` text
- Verify keyboard-only navigation works for all interactive elements

## Performance
- Use Lighthouse CI in CI/CD pipelines
- Set performance budgets: LCP < 2.5s, INP < 200ms, CLS < 0.1
- Monitor Total Blocking Time (TBT) as a proxy for INP
- Use Chrome DevTools Performance panel for deep profiling
- Avoid forced synchronous layouts in JavaScript

## Memory Management
- Take heap snapshots at key points to detect leaks
- Watch for detached DOM nodes in heap snapshots
- Use `performance.measureUserAgentSpecificMemory()` for overview
- Monitor event listener count growth over time
- Dispose of unused event listeners and observers

## Network
- Mock API responses for deterministic tests
- Use `page.setRequestInterception()` for request modification
- Monitor failed requests and console errors
- Test offline behavior with `page.setOfflineMode()`
