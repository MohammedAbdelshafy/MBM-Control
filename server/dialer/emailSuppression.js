import fs from 'fs';
import path from 'path';

// In MVP, we mock the database suppression list using a local JSON file 
// or simple in-memory set if the file isn't present.
const SUPPRESSION_FILE = path.join(process.cwd(), 'suppression_list.json');

function loadSuppressionList() {
    try {
        if (fs.existsSync(SUPPRESSION_FILE)) {
            const data = fs.readFileSync(SUPPRESSION_FILE, 'utf8');
            return new Set(JSON.parse(data));
        }
    } catch (err) {
        console.error('[EmailSuppression] Error loading suppression list:', err);
    }
    return new Set();
}

function saveSuppressionList(suppressedSet) {
    try {
        fs.writeFileSync(SUPPRESSION_FILE, JSON.stringify(Array.from(suppressedSet)), 'utf8');
    } catch (err) {
        console.error('[EmailSuppression] Error saving suppression list:', err);
    }
}

let _suppressedEmails = loadSuppressionList();

/**
 * Checks if an email is suppressed (DNC, unsubscribed, invalid).
 * @param {string} email 
 * @param {string} tenantId 
 * @returns {boolean} true if suppressed and should be BLOCKED
 */
export function isEmailSuppressed(email, tenantId) {
    if (!email || !email.includes('@')) return true; // Invalid is suppressed
    const normalized = email.toLowerCase().trim();
    // In a multi-tenant DB, you'd check tenant-specific suppressions. 
    // Here we use a global blocklist for safety.
    return _suppressedEmails.has(normalized);
}

/**
 * Adds an email to the suppression list.
 * @param {string} email 
 * @param {string} tenantId 
 */
export function suppressEmail(email, tenantId) {
    if (!email) return;
    const normalized = email.toLowerCase().trim();
    _suppressedEmails.add(normalized);
    saveSuppressionList(_suppressedEmails);
    console.log(`[EmailSuppression] Suppressed email: ${normalized} for tenant: ${tenantId}`);
}
