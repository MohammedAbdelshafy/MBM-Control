import assert from 'node:assert/strict';
import { getSmsConfig, normalizeE164Sms, smsSegmentCount, buildPhoundPrefillLink, sendPhoundSms } from './phoundSmsProvider.js';

assert.equal(normalizeE164Sms('+12125551234'), '+12125551234');
assert.equal(normalizeE164Sms('(212) 555-1234'), '+12125551234');
assert.throws(() => normalizeE164Sms('not-a-phone'), /Invalid phone number/);

assert.equal(smsSegmentCount('short'), 1);
assert.equal(smsSegmentCount('x'.repeat(161)), 2);

const disabled = getSmsConfig({ PHOUND_ENABLED: 'false' });
assert.equal(disabled.enabled, false);

const missing = getSmsConfig({ PHOUND_ENABLED: 'true' });
assert.equal(missing.enabled, false);
assert.equal(missing.configured, false);

const insecure = getSmsConfig({
  PHOUND_ENABLED: 'true',
  PHOUND_SMS_ENDPOINT: 'http://example.com/sms',
  PHOUND_API_TOKEN: 'test-token',
});
assert.equal(insecure.enabled, false);
assert.equal(insecure.configured, false);

const secure = getSmsConfig({
  PHOUND_ENABLED: 'true',
  PHOUND_SMS_ENDPOINT: 'https://example.com/sms',
  PHOUND_API_TOKEN: 'test-token',
});
assert.equal(secure.enabled, true);
assert.equal(secure.configured, true);

const prefill = buildPhoundPrefillLink('+12125551234', 'Hello there');
assert.ok(prefill.startsWith('https://web.phound.app/?phone='));
assert.ok(prefill.includes('Hello%20there'));

const native = await sendPhoundSms({ to: '+12125551234', message: 'Hi', campaign: 'test' }, { PHOUND_ENABLED: 'false' });
assert.equal(native.status, 'native_app');
assert.ok(native.prefill.startsWith('https://web.phound.app/'));

console.log('Phound SMS provider security checks passed.');
