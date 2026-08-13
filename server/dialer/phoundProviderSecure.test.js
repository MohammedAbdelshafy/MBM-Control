import assert from 'node:assert/strict';
import { getPhoundConfig, normalizeE164 } from './phoundProviderSecure.js';

assert.equal(normalizeE164('+12125551234'), '+12125551234');
assert.equal(normalizeE164('(212) 555-1234'), '+12125551234');
assert.throws(() => normalizeE164('not-a-phone'), /Invalid phone number/);

const disabled = getPhoundConfig({ PHOUND_ENABLED: 'false' });
assert.equal(disabled.enabled, false);

const missing = getPhoundConfig({ PHOUND_ENABLED: 'true' });
assert.equal(missing.enabled, false);
assert.equal(missing.configured, false);

const insecure = getPhoundConfig({
  PHOUND_ENABLED: 'true',
  PHOUND_CALL_ENDPOINT: 'http://example.com/call',
  PHOUND_API_TOKEN: 'test-token',
});
assert.equal(insecure.enabled, false);
assert.equal(insecure.configured, false);

const secure = getPhoundConfig({
  PHOUND_ENABLED: 'true',
  PHOUND_CALL_ENDPOINT: 'https://example.com/call',
  PHOUND_API_TOKEN: 'test-token',
});
assert.equal(secure.enabled, true);
assert.equal(secure.configured, true);

console.log('Phound provider security checks passed.');
