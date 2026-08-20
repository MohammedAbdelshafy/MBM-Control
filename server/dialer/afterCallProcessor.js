import { executeOmniSkill, addOmniMemory } from './omniRouteClient.js';

/**
 * Processes a post-call transcript or notes using Groq Fast Inference to extract structured CRM fields.
 * 
 * @param {Object} callData
 * @param {string} callData.leadId
 * @param {string} callData.transcript - The raw transcript or notes dictated by the agent
 * @param {string} callData.currentStage - The current stage of the deal
 * @param {string} callData.tenantId - The tenant ID
 * @param {string} callData.eventId - The unique after-call event ID
 * @returns {Promise<Object>} The structured CRM payload
 */
async function processAfterCall(callData) {
    const { leadId, transcript, currentStage, tenantId, eventId } = callData;
    
    // Fallback object to ensure downstream processes do not crash
    const fallbackData = {
        Pain_Points: "unknown",
        Budget: "unknown",
        Next_Steps: "needs_review",
        Recommended_Stage: currentStage || "needs_review",
        is_fallback: true
    };
    
    if (!transcript || transcript.trim() === '') {
        console.warn(`[AfterCallProcessor] Empty transcript for lead ${leadId}. Returning fallback.`);
        return fallbackData;
    }

    const extractionPrompt = `
You are an expert Sales CRM AI. Analyze the following post-call transcript/notes and extract structured CRM fields.
Transcript:
"""
${transcript}
"""

Current Stage: ${currentStage}

Respond ONLY with a JSON object matching this schema:
{
    "Pain_Points": "String summarizing the core problem the lead faces, or 'unknown'",
    "Budget": "String summarizing any mention of price or budget, or 'unknown'",
    "Next_Steps": "Actionable next steps, or 'needs_review'",
    "Recommended_Stage": "One of: Prospecting, Diagnostic Booked, Audit SOW Sent, Closed Won, Closed Lost"
}
`;

    console.log(`[AfterCallProcessor] Running Groq Fast Inference for Lead: ${leadId}, Event: ${eventId}`);
    
    const groqInput = {
        messages: [
            { role: "system", content: "You are an expert CRM data extractor." },
            { role: "user", content: extractionPrompt }
        ],
        model: "llama-3.3-70b-versatile"
    };
    
    let extractedData = {};
    
    try {
        const extractionResult = await executeOmniSkill('groq-fast-inference', groqInput, { timeout: 30000 });
        
        if (extractionResult && extractionResult.choices && extractionResult.choices[0] && extractionResult.choices[0].message) {
            try {
                const content = extractionResult.choices[0].message.content;
                const jsonStr = content.replace(/```json/g, '').replace(/```/g, '').trim();
                extractedData = JSON.parse(jsonStr);
                
                // Ensure required fields exist, even if AI hallucinated schema
                extractedData.Pain_Points = extractedData.Pain_Points || "unknown";
                extractedData.Budget = extractedData.Budget || "unknown";
                extractedData.Next_Steps = extractedData.Next_Steps || "needs_review";
                extractedData.Recommended_Stage = extractedData.Recommended_Stage || currentStage || "needs_review";
                
            } catch (err) {
                console.error(`[AfterCallProcessor] Failed to parse JSON from Groq output (Event: ${eventId}):`, err);
                extractedData = { ...fallbackData };
            }
        } else {
            console.warn(`[AfterCallProcessor] Unexpected result format from Groq (Event: ${eventId})`);
            extractedData = { ...fallbackData }; 
        }
    } catch (err) {
        console.error(`[AfterCallProcessor] Process failed for lead ${leadId} (Event: ${eventId}):`, err.message);
        extractedData = { ...fallbackData, error: err.message };
    }
    
    // Save to OmniRoute persistent memory safely
    try {
        await addOmniMemory('disposition', extractedData, { 
            leadId, 
            tenantId, 
            eventId, 
            timestamp: new Date().toISOString() 
        });
    } catch (memErr) {
        console.error(`[AfterCallProcessor] Failed to save memory for event ${eventId}:`, memErr.message);
    }
    
    return extractedData;
}

export {
    processAfterCall
};
