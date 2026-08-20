import express from 'express';
import crypto from 'crypto';
import { processAfterCall } from './afterCallProcessor.js';
import { syncToSalesforce } from './salesforceSync.js';
import { triggerMultiChannelFollowUp } from './multiChannelFollowUp.js';
import { searchOmniMemory } from './omniRouteClient.js';

const router = express.Router();

// Basic middleware for tenant isolation (placeholder for existing dialer auth)
function authenticateDialer(req, res, next) {
    // In production, verify bearer token and extract tenant/user.
    // We expect the client to at least pass a tenantId in the body or header.
    const tenantId = req.headers['x-tenant-id'] || req.body.tenantId || 'DEFAULT_TENANT';
    req.tenantId = tenantId;
    next();
}

router.post('/aftercall', authenticateDialer, async (req, res) => {
    const eventId = req.body.eventId || crypto.randomUUID();
    const startTime = Date.now();
    
    try {
        const { leadId, phone, transcript, currentStage } = req.body;
        const tenantId = req.tenantId;
        
        if (!leadId || !transcript || transcript.trim() === '') {
            console.error(`[AfterCallRoute] Invalid payload (Event: ${eventId})`);
            return res.status(400).json({ error: 'leadId and transcript are required' });
        }

        console.log(JSON.stringify({
            event: 'after_call_started',
            eventId,
            leadId,
            tenantId,
            timestamp: new Date().toISOString()
        }));

        // 1. Process notes via Groq Fast Inference
        const extractedData = await processAfterCall({ leadId, transcript, currentStage, tenantId, eventId });

        // 2. Sync to Salesforce
        let sfResult = null;
        try {
            sfResult = await syncToSalesforce({ leadId, eventId, extractedData });
        } catch (sfError) {
            console.error(`[AfterCallRoute] Salesforce sync failed (Event: ${eventId}):`, sfError.message);
            sfResult = { status: 'FAILED', error: sfError.message };
        }

        // 3. Trigger Follow Ups
        let followUpResult = null;
        if (phone || req.body.email) {
            try {
                followUpResult = await triggerMultiChannelFollowUp({ 
                    leadId, 
                    eventId, 
                    phone, 
                    email: req.body.email,
                    firstName: req.body.firstName,
                    company: req.body.company,
                    tenantId,
                    disposition: req.body.disposition || currentStage,
                    extractedData 
                });
            } catch (fuError) {
                console.error(`[AfterCallRoute] FollowUp trigger failed (Event: ${eventId}):`, fuError.message);
                followUpResult = { status: 'FAILED', error: fuError.message };
            }
        }

        const processingTime = Date.now() - startTime;
        
        console.log(JSON.stringify({
            event: 'after_call_completed',
            eventId,
            leadId,
            tenantId,
            processing_time_ms: processingTime,
            groq_status: extractedData.is_fallback ? 'FALLBACK' : 'SUCCESS',
            salesforce_status: sfResult?.status || 'UNKNOWN',
            followup_status: followUpResult?.status || 'NO_ACTION'
        }));

        res.json({
            success: true,
            eventId,
            extractedData,
            salesforce: sfResult,
            followUp: followUpResult
        });
    } catch (err) {
        console.error(`[AfterCallRoute] Error (Event: ${eventId}):`, err.message);
        res.status(500).json({ error: err.message, eventId });
    }
});

router.get('/analytics', authenticateDialer, async (req, res) => {
    try {
        const tenantId = req.tenantId;
        
        // Securely fetch memory via CLI wrapper
        const stdout = await searchOmniMemory('disposition');
        
        // Try parsing JSON array from memory output
        let records = [];
        try {
            const jsonStart = stdout.indexOf('[');
            if (jsonStart !== -1) {
                records = JSON.parse(stdout.slice(jsonStart));
            } else {
                // Some memory dumps might not be arrays natively depending on omniroute version
                // We'll fall back to string matching if JSON parsing fails below
            }
        } catch (e) {
            // Fallback strategy done in metrics calculation
        }
        
        const rawString = stdout.toLowerCase();
        
        // Aggregate Tenant Metrics securely on server
        // In a real database, we would query WHERE tenantId = req.tenantId
        // Here we simulate it by parsing string matches since omniroute stores it verbatim
        const totalCalls = (stdout.match(new RegExp(tenantId, 'gi')) || []).length;
        const booked = (stdout.match(/Diagnostic Booked/gi) || []).length;
        
        const metrics = {
            totalLoggedCalls: totalCalls > 0 ? totalCalls : (stdout.match(/disposition/gi) || []).length,
            booked: booked,
            pipelineValue: booked * 1500,
            rawOutput: stdout // Still returning stdout temporarily for the UI, but structured metrics are available
        };
        
        res.json({ success: true, tenantId, metrics });
    } catch (err) {
        console.error('[AfterCallRoute] Analytics error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

export default router;
