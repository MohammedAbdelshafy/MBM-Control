import { executeOmniSkill } from './omniRouteClient.js';

const ALLOWED_STAGES = [
    "Prospecting", 
    "Diagnostic Booked", 
    "Audit SOW Sent", 
    "Closed Won", 
    "Closed Lost"
];

/**
 * Syncs the extracted CRM payload to Salesforce using the salesforce-crm-copilot skill.
 * 
 * @param {Object} syncData
 * @param {string} syncData.leadId
 * @param {string} syncData.eventId
 * @param {Object} syncData.extractedData - The structured JSON from Groq
 * @returns {Promise<Object>} The Salesforce Sync Result
 */
async function syncToSalesforce(syncData) {
    const { leadId, eventId, extractedData } = syncData;
    
    // Gating check
    if (!process.env.SALESFORCE_API_KEY && !process.env.SALESFORCE_ENABLED) {
        console.log(`[SalesforceSync] Skipping sync for ${leadId} (Event: ${eventId}) - SKIPPED_NO_CREDENTIALS`);
        return { status: 'SKIPPED_NO_CREDENTIALS' };
    }
    
    console.log(`[SalesforceSync] Syncing lead ${leadId} to Salesforce (Event: ${eventId})...`);
    
    let stage = extractedData.Recommended_Stage || "Prospecting";
    if (!ALLOWED_STAGES.includes(stage)) {
        console.warn(`[SalesforceSync] Invalid stage '${stage}' detected. Defaulting to 'needs_review'.`);
        stage = "needs_review";
    }
    
    // The salesforce-crm-copilot takes the extracted JSON deals and handles stage progression
    const sfPayload = {
        action: "upsert_opportunity",
        record: {
            External_ID__c: leadId,
            StageName: stage,
            NextStep: extractedData.Next_Steps || "",
            Description: `Pain Points: ${extractedData.Pain_Points || 'None identified'}\nBudget: ${extractedData.Budget || 'Unknown'}`
        }
    };
    
    try {
        const syncResult = await executeOmniSkill('salesforce-crm-copilot', sfPayload, { timeout: 30000 });
        
        if (syncResult && syncResult.id) {
            console.log(`[SalesforceSync] Successfully synced! Salesforce ID: ${syncResult.id}`);
            return {
                status: 'SYNCED',
                salesforceId: syncResult.id,
                stage: sfPayload.record.StageName,
                rawResult: syncResult
            };
        } else {
            console.warn(`[SalesforceSync] Warning: Salesforce sync did not return an ID (Event: ${eventId}).`, syncResult);
            return {
                status: 'NEEDS_REVIEW',
                salesforceId: null,
                stage: sfPayload.record.StageName,
                rawResult: syncResult
            };
        }
    } catch (err) {
        console.error(`[SalesforceSync] Error syncing lead ${leadId} to Salesforce (Event: ${eventId}):`, err.message);
        return { status: 'FAILED', error: err.message };
    }
}

export {
    syncToSalesforce
};
