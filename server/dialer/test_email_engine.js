import { determineEmailFollowUp } from './emailRuleEngine.js';
import { determineTiming } from './emailSequencer.js';
import { buildEmailTemplate } from './emailTemplates.js';
import { isEmailSuppressed, suppressEmail } from './emailSuppression.js';
import fs from 'fs';
import path from 'path';

async function runTests() {
    console.log('--- STARTING EMAIL ENGINE VERIFICATION ---');

    let passed = 0;
    let failed = 0;

    function assert(condition, message) {
        if (condition) {
            console.log(`✅ PASS: ${message}`);
            passed++;
        } else {
            console.error(`❌ FAIL: ${message}`);
            failed++;
        }
    }

    // 1. Rule Engine Tests
    console.log('\n[Rule Engine]');
    assert(determineEmailFollowUp('Connected', 'Diagnostic Booked') === 'DIAGNOSTIC_BOOKED_CONFIRMATION', 'Mapped Connected/Diagnostic Booked correctly');
    assert(determineEmailFollowUp('DNC', 'Diagnostic Booked') === null, 'DNC disposition is blocked');
    assert(determineEmailFollowUp('Not Interested', 'Closed Lost') === null, 'Not Interested is blocked');

    // 2. Templates Tests
    console.log('\n[Templates]');
    const tpl = buildEmailTemplate('DIAGNOSTIC_BOOKED_CONFIRMATION', { first_name: 'Test', company: '<script>alert(1)</script>' }, { Pain_Points: 'High cost & low quality' });
    assert(tpl.html.includes('Test'), 'Template injected first_name');
    assert(!tpl.html.includes('<script>'), 'Template escaped HTML (XSS prevention)');
    assert(tpl.html.includes('&lt;script&gt;'), 'Template safely rendered HTML entity');
    assert(tpl.html.includes('High cost &amp; low quality'), 'Pain points injected and escaped');

    // 3. Suppression Tests
    console.log('\n[Suppression]');
    const testEmail = `test_${Date.now()}@example.com`;
    assert(!isEmailSuppressed(testEmail, 'tenant1'), 'New email is not suppressed');
    suppressEmail(testEmail, 'tenant1');
    assert(isEmailSuppressed(testEmail, 'tenant1'), 'Suppressed email is correctly blocked');

    // Cleanup suppression file test entries if needed
    const suppPath = path.join(process.cwd(), 'suppression_list.json');
    if (fs.existsSync(suppPath)) {
        let supps = JSON.parse(fs.readFileSync(suppPath, 'utf8'));
        supps = supps.filter(e => !e.startsWith('test_'));
        fs.writeFileSync(suppPath, JSON.stringify(supps));
    }

    // 4. Sequencer Tests
    console.log('\n[Sequencer]');
    const timing1 = determineTiming('DIAGNOSTIC_BOOKED_CONFIRMATION', 'Diagnostic Booked');
    assert(timing1.isImmediate === true, 'Diagnostic booked confirmation is immediate');
    
    const timing2 = determineTiming('MEETING_REMINDER', 'Diagnostic Booked');
    assert(timing2.isImmediate === false, 'Meeting reminder is scheduled');
    assert(timing2.sendAfter > new Date(), 'Send after is in the future');

    console.log(`\n--- TEST SUMMARY ---`);
    console.log(`Tests Run: ${passed + failed}`);
    console.log(`Passed: ${passed}`);
    console.log(`Failed: ${failed}`);

    if (failed > 0) {
        process.exit(1);
    }
}

runTests().catch(err => {
    console.error('Unhandled test failure:', err);
    process.exit(1);
});
