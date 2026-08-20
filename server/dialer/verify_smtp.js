import nodemailer from 'nodemailer';
import dotenv from 'dotenv';

// Load environment variables from .env.local if present
dotenv.config({ path: '.env.local' });

async function verifySmtp() {
    const user = process.env.SMTP_USER;
    const pass = process.env.SMTP_PASS;
    const host = process.env.SMTP_HOST || 'smtp.gmail.com';
    const port = parseInt(process.env.SMTP_PORT || '587');

    if (!user || !pass || pass === 'REPLACE_WITH_NEW_APP_PASSWORD') {
        console.error('❌ Missing or default SMTP credentials.');
        console.error('Please configure SMTP_USER and SMTP_PASS in .env.local');
        console.error('For Gmail, SMTP_PASS must be a 16-character App Password (not your main password).');
        process.exit(1);
    }

    console.log(`Connecting to ${host}:${port} as ${user}...`);

    const transporter = nodemailer.createTransport({
        host,
        port,
        secure: port === 465,
        auth: { user, pass }
    });

    try {
        await transporter.verify();
        console.log('✅ SMTP Connection Successful! Credentials are valid.');
    } catch (error) {
        console.error('❌ SMTP Connection Failed!');
        console.error(error.message);
        if (error.responseCode === 535) {
            console.error('\nNOTE: A 535 5.7.8 error means authentication failed.');
            console.error('If you are using Gmail, you MUST use an App Password.');
            console.error('1. Go to Google Account -> Security -> 2-Step Verification -> App passwords');
            console.error('2. Generate a new password and put it in .env.local as SMTP_PASS.');
        }
        process.exit(1);
    }
}

verifySmtp();
