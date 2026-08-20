import nodemailer from 'nodemailer';
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

/**
 * Modes:
 * DRY_RUN: Logs only. Never sends.
 * TEST: Sends only if email is on the allowlist.
 * LIVE: Sends normally.
 */
const EMAIL_MODE = process.env.EMAIL_MODE || 'DRY_RUN';
const TEST_ALLOWLIST = ['abdelshafyclapps@gmail.com', 'test@contecai.com'];

let _transporter = null;

function getTransporter() {
    if (_transporter) return _transporter;
    const email = process.env.SMTP_USER || 'abdelshafyclapps@gmail.com';
    const pass = (process.env.SMTP_PASS || '').replace(/\s+/g, '');
    const host = process.env.SMTP_HOST || 'smtp.gmail.com';
    const port = parseInt(process.env.SMTP_PORT || '587');

    _transporter = nodemailer.createTransport({
        host,
        port,
        secure: port === 465,
        auth: { user: email, pass }
    });
    return _transporter;
}

/**
 * Sends a follow-up email.
 * @param {Object} emailData 
 * @returns {Promise<{status: string, messageId?: string, error?: string}>}
 */
export async function sendFollowUpEmail(emailData) {
    const { to, subject, html, from, replyTo, tenantId, leadId, eventId, followupType } = emailData;
    
    if (EMAIL_MODE === 'DRY_RUN') {
        console.log(`[EmailProvider] DRY_RUN Mode. Would have sent: [${followupType}] to ${to}`);
        return { status: 'SKIPPED', messageId: `dry-run-${Date.now()}` };
    }

    if (EMAIL_MODE === 'TEST') {
        if (!TEST_ALLOWLIST.includes(to)) {
            console.log(`[EmailProvider] TEST Mode. Skipped sending to unapproved address: ${to}`);
            return { status: 'BLOCKED', error: 'Not in TEST_ALLOWLIST' };
        }
    }

    const transporter = getTransporter();
    try {
        const info = await transporter.sendMail({
            from: from || process.env.SMTP_FROM_NAME || '"MBM Dialer" <abdelshafyclapps@gmail.com>',
            to,
            replyTo,
            subject,
            html,
            headers: {
                'X-Tenant-ID': tenantId,
                'X-Lead-ID': leadId,
                'X-Event-ID': eventId
            }
        });

        console.log(`[EmailProvider] Email sent: ${info.messageId}`);
        return { status: 'SENT', messageId: info.messageId };
    } catch (error) {
        console.error(`[EmailProvider] Send failed for ${to}:`, error.message);
        return { status: 'FAILED', error: error.message };
    }
}
