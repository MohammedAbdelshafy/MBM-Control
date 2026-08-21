/**
 * Deterministically maps a disposition and recommended stage to a follow-up email type.
 * 
 * Rules:
 * - DNC / UNSUBSCRIBED -> BLOCK
 * - NOT_INTERESTED -> BLOCK
 * - DIAGNOSTIC_BOOKED -> DIAGNOSTIC_BOOKED_CONFIRMATION
 * - FOLLOW_UP_REQUIRED -> FOLLOW_UP_AFTER_CALL
 * - NEEDS_MORE_INFO -> NEEDS_MORE_INFO
 * - PROPOSAL_SENT -> PROPOSAL_FOLLOW_UP
 * - QUALIFIED -> QUALIFICATION_FOLLOW_UP
 * - NOT_NOW -> REACTIVATION
 * 
 * @param {string} disposition - The raw call disposition.
 * @param {string} recommendedStage - The AI enriched recommended stage.
 * @returns {string|null} - The followupType or null if blocked/unsupported.
 */
export function determineEmailFollowUp(disposition, recommendedStage) {
    if (!disposition) return null;

    const lowerDisp = disposition.toLowerCase();
    
    // Hard blocks
    if (lowerDisp.includes('dnc') || lowerDisp.includes('unsubscribe') || lowerDisp.includes('do not call')) {
        return null; // BLOCKED
    }
    if (lowerDisp.includes('not interested') || lowerDisp.includes('wrong number') || lowerDisp.includes('bad number')) {
        return null;
    }

    const stage = (recommendedStage || '').toUpperCase().replace(/ /g, '_');

    if (lowerDisp.includes('diagnostic') || stage === 'DIAGNOSTIC_BOOKED') {
        return 'DIAGNOSTIC_BOOKED_CONFIRMATION';
    }
    if (stage === 'PROPOSAL_SENT') {
        return 'PROPOSAL_FOLLOW_UP';
    }
    if (stage === 'QUALIFIED' || lowerDisp.includes('qualified')) {
        return 'QUALIFICATION_FOLLOW_UP';
    }
    if (stage === 'NEEDS_MORE_INFO' || lowerDisp.includes('more info') || lowerDisp.includes('send info')) {
        return 'NEEDS_MORE_INFO';
    }
    if (stage === 'FOLLOW_UP_REQUIRED' || lowerDisp.includes('follow up') || lowerDisp.includes('call back')) {
        return 'FOLLOW_UP_AFTER_CALL';
    }
    if (stage === 'NOT_NOW' || lowerDisp.includes('not now') || lowerDisp.includes('timing')) {
        return 'REACTIVATION';
    }
    if (lowerDisp.includes('success') || lowerDisp.includes('positive')) {
        return 'THANK_YOU';
    }

    return null;
}
