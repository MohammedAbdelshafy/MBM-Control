import fs from 'fs';
import path from 'path';

// Load sequences
const sequencesPath = path.join(process.cwd(), 'server', 'dialer', 'followup_sequences.json');
let sequences = {};
try {
    if (fs.existsSync(sequencesPath)) {
        sequences = JSON.parse(fs.readFileSync(sequencesPath, 'utf8'));
    }
} catch (err) {
    console.error('[EmailSequencer] Error loading sequences:', err);
}

/**
 * Calculates the next send window for an email based on tenant business hours.
 * For MVP, we simply add the delay minutes. If the delay is 0, it sends immediately.
 * In a full production setup, this would check the tenant's timezone and ensure 
 * the calculated time falls within 9 AM - 5 PM, pushing to the next day if needed.
 * 
 * @param {number} delayMinutes 
 * @param {string} tenantTimezone 
 * @returns {Date} 
 */
function calculateSendAfter(delayMinutes, tenantTimezone = 'UTC') {
    const now = new Date();
    if (delayMinutes === 0) return now;

    // Add minutes
    const sendAfter = new Date(now.getTime() + delayMinutes * 60000);
    return sendAfter;
}

/**
 * Gets the sequence steps for a given stage.
 * @param {string} stage 
 * @returns {Array} 
 */
export function getSequenceForStage(stage) {
    const upperStage = (stage || '').toUpperCase().replace(/ /g, '_');
    return sequences[upperStage] || [];
}

/**
 * Determines if a follow-up is an immediate trigger or requires scheduling.
 * @param {string} followupType 
 * @param {string} stage 
 * @returns {{isImmediate: boolean, sendAfter: Date}}
 */
export function determineTiming(followupType, stage) {
    const sequence = getSequenceForStage(stage);
    
    // Find if the followupType is in a sequence
    const step = sequence.find(s => s.type === followupType);
    
    if (step && step.delay_minutes > 0) {
        return { isImmediate: false, sendAfter: calculateSendAfter(step.delay_minutes) };
    }

    // Default immediate
    return { isImmediate: true, sendAfter: new Date() };
}
