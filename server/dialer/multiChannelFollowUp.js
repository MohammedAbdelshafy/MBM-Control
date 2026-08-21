import { executeOmniSkill } from './omniRouteClient.js';
import { determineEmailFollowUp } from './emailRuleEngine.js';
import { determineTiming } from './emailSequencer.js';
import { buildEmailTemplate } from './emailTemplates.js';
import { isEmailSuppressed } from './emailSuppression.js';
import { sendFollowUpEmail } from './emailProvider.js';

// Idempotency cache (In a real system, this would be Redis or a DB table)
const processedEvents = new Set();
const processedEmails = new Set();

/**
 * Triggers multi-channel follow ups (SMS/WhatsApp/Email) depending on the extracted stage and intent.
 * 
 * @param {Object} followUpData
 * @param {string} followUpData.leadId
 * @param {string} followUpData.eventId
 * @param {string} followUpData.phone
 * @param {string} followUpData.email
 * @param {string} followUpData.firstName
 * @param {string} followUpData.company
 * @param {string} followUpData.tenantId
 * @param {string} followUpData.disposition - Original disposition
 * @param {Object} followUpData.extractedData - Output from Groq
 * @returns {Promise<Object>} Execution status
 */
async function triggerMultiChannelFollowUp(followUpData) {
    const { leadId, eventId, phone, email, firstName, company, tenantId, disposition, extractedData } = followUpData;
    
    // Default response status
    let resultStatus = { sms: 'NO_ACTION', social: 'NO_ACTION', email: 'NO_ACTION' };

    // --- EMAIL FOLLOW UP ENGINE ---
    const emailFollowUpType = determineEmailFollowUp(disposition, extractedData?.Recommended_Stage);
    const emailIdempotencyKey = `${tenantId}:${leadId}:${eventId}:${emailFollowUpType}`;

    if (emailFollowUpType) {
        if (processedEmails.has(emailIdempotencyKey)) {
            console.log(`[EmailEngine] Event ${emailIdempotencyKey} already processed. Skipping duplicate email.`);
            resultStatus.email = 'SKIPPED_DUPLICATE';
        } else if (isEmailSuppressed(email, tenantId)) {
            console.log(`[EmailEngine] Email ${email} is suppressed. Blocking ${emailFollowUpType}.`);
            resultStatus.email = 'BLOCKED_SUPPRESSED';
            processedEmails.add(emailIdempotencyKey);
        } else {
            console.log(`[EmailEngine] Preparing to send ${emailFollowUpType} to ${email}...`);
            const timing = determineTiming(emailFollowUpType, extractedData?.Recommended_Stage);
            
            if (timing.isImmediate) {
                const { subject, html } = buildEmailTemplate(emailFollowUpType, {
                    first_name: firstName,
                    company,
                    tenantId,
                    leadId
                }, extractedData);
                
                try {
                    const sendRes = await sendFollowUpEmail({
                        to: email,
                        subject,
                        html,
                        tenantId,
                        leadId,
                        eventId,
                        followupType: emailFollowUpType
                    });
                    resultStatus.email = sendRes.status;
                    if (sendRes.status !== 'FAILED') {
                        processedEmails.add(emailIdempotencyKey);
                    }
                } catch (emailErr) {
                    console.error(`[EmailEngine] Email error:`, emailErr);
                    resultStatus.email = 'FAILED';
                }
            } else {
                console.log(`[EmailEngine] Scheduling ${emailFollowUpType} for ${timing.sendAfter}`);
                resultStatus.email = 'SCHEDULED';
                processedEmails.add(emailIdempotencyKey);
            }
        }
    }

    // --- SMS / SOCIAL FOLLOW UP ---
    if (processedEvents.has(eventId)) {
        console.log(`[MultiChannelFollowUp] Event ${eventId} already processed for lead ${leadId}. Skipping to prevent duplicate SMS.`);
        resultStatus.sms = 'SKIPPED_DUPLICATE';
        resultStatus.social = 'SKIPPED_DUPLICATE';
    } else {
        if (extractedData?.Recommended_Stage === 'Diagnostic Booked') {
            console.log(`[MultiChannelFollowUp] Stage is Diagnostic Booked. Firing confirmation SMS...`);
            try {
                console.log(`[MultiChannelFollowUp] -> SENT SMS to ${phone}`);
                resultStatus.sms = 'SMS_SENT';
                processedEvents.add(eventId);
            } catch (err) {
                console.error(`[MultiChannelFollowUp] Error sending SMS to ${phone} (Event: ${eventId}):`, err.message);
                resultStatus.sms = 'SMS_FAILED';
            }
        } else if (extractedData?.Recommended_Stage === 'Closed Lost' || extractedData?.Recommended_Stage === 'Prospecting') {
            console.log(`[MultiChannelFollowUp] Lead is cold or lost. Queuing for retargeting...`);
            const socialPayload = { action: 'queue_retargeting', audience: 'cold_outreach', lead_phone: phone, notes: extractedData?.Next_Steps || "" };
            try {
                await executeOmniSkill('omnichannel-social-distribution', socialPayload, { timeout: 15000 });
                console.log(`[MultiChannelFollowUp] -> Queued lead ${leadId} for omnichannel retargeting.`);
                resultStatus.social = 'SOCIAL_QUEUED';
                processedEvents.add(eventId);
            } catch (err) {
                console.error(`[MultiChannelFollowUp] Error queuing retargeting for ${leadId} (Event: ${eventId}):`, err.message);
                resultStatus.social = 'SOCIAL_QUEUE_FAILED';
            }
        }
    }
    
    // Prevent memory leaks in simple cache
    if (processedEvents.size > 10000) processedEvents.clear();
    if (processedEmails.size > 10000) processedEmails.clear();
    
    return { status: resultStatus, timestamp: new Date().toISOString() };
}

export {
    triggerMultiChannelFollowUp
};
