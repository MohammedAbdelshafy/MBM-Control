# Skill: Chrome DevTools

## Overview
Agent skills for Chrome DevTools and Puppeteer: debugging accessibility issues, auditing Core Web Vitals, running visual automation tests, and diagnosing memory leaks.

## Capabilities
- **Accessibility Debugging**: Automated a11y audits, ARIA issue detection, contrast ratio checks
- **Performance Auditing**: LCP/INP/CLS measurement, Lighthouse reports, bundle analysis
- **Visual Automation**: Screenshot comparison, visual regression testing, responsive testing
- **Memory Leak Detection**: Heap snapshot analysis, detached DOM node tracking, event listener auditing
- **Network Analysis**: Request waterfall inspection, API performance monitoring, cache optimization
- **Puppeteer Scripts**: Browser automation, form filling, PDF generation, screenshot capture

## When to Use
- Debugging accessibility issues in web pages
- Auditing Core Web Vitals and performance
- Writing Puppeteer automation scripts
- Investigating memory leaks in long-running apps
- Visual regression testing

## Key Patterns

### Puppeteer Setup
```javascript
const puppeteer = require('puppeteer');

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 720 });
```

### Accessibility Audit
```javascript
const { AxePuppeteer } = require('@axe-core/puppeteer');
const results = await new AxePuppeteer(page).analyze();
console.log(results.violations);
```

### Performance Metrics via CDP
```javascript
const client = await page.target().createCDPSession();
await client.send('Performance.enable');
const metrics = await client.send('Performance.getMetrics');
```

### Memory Leak Detection
```javascript
// Take heap snapshots before and after
const snapshot1 = await page._client().send('HeapProfiler.takeHeapSnapshot');
// ... run operations ...
const snapshot2 = await page._client().send('HeapProfiler.takeHeapSnapshot');
// Compare with Chrome DevTools Memory tab
```

### Screenshot Comparison
```javascript
const screenshot1 = await page.screenshot({ path: 'baseline.png' });
// ... make changes ...
const screenshot2 = await page.screenshot({ path: 'current.png' });
// Use pixelmatch or similar for comparison
```

## MCP Server
The Chrome DevTools MCP server provides these tools via the Model Context Protocol:
```json
{
  "command": "npx",
  "args": ["-y", "@anthropic-ai/chrome-devtools-mcp"]
}
```

## References
- https://github.com/ChromeDevTools/chrome-devtools-mcp
- https://pptr.dev/
- https://web.dev/vitals/
- https://developer.chrome.com/docs/devtools/accessibility/
