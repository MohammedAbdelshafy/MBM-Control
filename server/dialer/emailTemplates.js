// Local HTML escape utility to avoid adding external dependencies
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

const TEMPLATES = {
    'DIAGNOSTIC_BOOKED_CONFIRMATION': {
        subject: 'Confirmed: Our upcoming diagnostic call',
        body: `
            <p>Hi {{first_name}},</p>
            <p>I'm confirming our upcoming diagnostic call to discuss {{company}}.</p>
            {{pain_points_section}}
            <p>Looking forward to speaking with you.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'FOLLOW_UP_AFTER_CALL': {
        subject: 'Following up on our conversation',
        body: `
            <p>Hi {{first_name}},</p>
            <p>It was great speaking with you about {{company}}.</p>
            {{next_steps_section}}
            <p>Let me know if you have any further questions.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'PROPOSAL_FOLLOW_UP': {
        subject: 'Checking in on the proposal for {{company}}',
        body: `
            <p>Hi {{first_name}},</p>
            <p>I wanted to follow up on the proposal we sent over. Do you have any questions or require adjustments?</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'NEEDS_MORE_INFO': {
        subject: 'Information requested - {{company}}',
        body: `
            <p>Hi {{first_name}},</p>
            <p>Thanks for taking the time to speak with me. As requested, I wanted to pass along some additional information.</p>
            {{next_steps_section}}
            <p>Let me know when you'd like to reconnect.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'QUALIFICATION_FOLLOW_UP': {
        subject: 'Next steps for {{company}}',
        body: `
            <p>Hi {{first_name}},</p>
            <p>It was great learning more about your goals for {{company}}.</p>
            {{next_steps_section}}
            <p>Looking forward to moving this forward.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'REACTIVATION': {
        subject: 'Checking back in - {{company}}',
        body: `
            <p>Hi {{first_name}},</p>
            <p>I know the timing wasn't right when we last spoke, but I wanted to check back in to see if anything has changed regarding your priorities.</p>
            <p>Let me know if you'd be open to a quick catch-up.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    },
    'THANK_YOU': {
        subject: 'Thank you for your time',
        body: `
            <p>Hi {{first_name}},</p>
            <p>Thank you for taking the time to speak with me today.</p>
            <p>Best regards,<br>{{sender_name}}</p>
        `
    }
};

/**
 * Builds the HTML email content safely.
 * @param {string} templateId 
 * @param {Object} data 
 * @param {Object} aiEnrichment 
 * @returns {{subject: string, html: string}}
 */
export function buildEmailTemplate(templateId, data, aiEnrichment = {}) {
    const template = TEMPLATES[templateId];
    if (!template) {
        throw new Error(`Unknown template ID: ${templateId}`);
    }

    const safeFirstName = escapeHtml(data.first_name || 'there');
    const safeCompany = escapeHtml(data.company || 'your business');
    const safeSenderName = escapeHtml(data.sender_name || 'Our Team');

    let subject = template.subject.replace('{{company}}', safeCompany);

    let html = template.body
        .replace(/{{first_name}}/g, safeFirstName)
        .replace(/{{company}}/g, safeCompany)
        .replace(/{{sender_name}}/g, safeSenderName);

    // AI Enrichment sections (Only added if present, otherwise safely removed)
    if (aiEnrichment.Pain_Points && aiEnrichment.Pain_Points.toLowerCase() !== 'unknown') {
        const safePain = escapeHtml(aiEnrichment.Pain_Points);
        html = html.replace('{{pain_points_section}}', `<p>I've noted that a primary focus is: <i>${safePain}</i>.</p>`);
    } else {
        html = html.replace('{{pain_points_section}}', '');
    }

    if (aiEnrichment.Next_Steps && aiEnrichment.Next_Steps.toLowerCase() !== 'needs_review' && aiEnrichment.Next_Steps.toLowerCase() !== 'unknown') {
        const safeSteps = escapeHtml(aiEnrichment.Next_Steps);
        html = html.replace('{{next_steps_section}}', `<p>Our agreed next step is: <b>${safeSteps}</b>.</p>`);
    } else {
        html = html.replace('{{next_steps_section}}', '');
    }

    // Append unsubscribe footer
    const unsubscribeLink = `https://app.contecai.com/unsubscribe?lead=${encodeURIComponent(data.leadId)}&tenant=${encodeURIComponent(data.tenantId)}`;
    html += `
        <br><br>
        <hr style="border: none; border-top: 1px solid #eee;">
        <p style="font-size: 11px; color: #888;">
            If you no longer wish to receive these emails, you can 
            <a href="${unsubscribeLink}">unsubscribe here</a>.
        </p>
    `;

    return { subject, html };
}
