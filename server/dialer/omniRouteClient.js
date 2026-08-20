import { exec } from 'child_process';
import util from 'util';
import fs from 'fs';
import os from 'os';
import path from 'path';
import crypto from 'crypto';

const execPromise = util.promisify(exec);

/**
 * Executes an OmniRoute skill securely via the CLI using temporary files to avoid shell injection.
 * @param {string} skillId - The ID of the skill to execute (e.g., 'groq-fast-inference')
 * @param {Object} input - JSON payload to pass to the skill
 * @param {Object} options - Execution options like timeout
 * @returns {Promise<Object>} - The JSON result from the skill execution
 */
async function executeOmniSkill(skillId, input, options = { timeout: 30000 }) {
    const tmpFile = path.join(os.tmpdir(), `omni_in_${crypto.randomUUID()}.json`);
    try {
        fs.writeFileSync(tmpFile, JSON.stringify(input), 'utf8');
        
        console.log(`[OmniRoute] Executing skill ${skillId}...`);
        
        const cmd = `npx --yes omniroute skills execute ${skillId} --input-file "${tmpFile}"`;
        
        const { stdout, stderr } = await execPromise(cmd, { timeout: options.timeout });
        
        if (stderr && !stderr.includes('Loaded env')) {
            console.warn(`[OmniRoute] Warning from ${skillId}:`, stderr);
        }
        
        try {
            const jsonStart = stdout.indexOf('{');
            if (jsonStart !== -1) {
                const jsonStr = stdout.slice(jsonStart);
                return JSON.parse(jsonStr);
            }
            return { rawOutput: stdout.trim() };
        } catch (parseError) {
            console.error(`[OmniRoute] Failed to parse JSON from ${skillId} output:`, stdout);
            return { rawOutput: stdout.trim() };
        }
    } catch (error) {
        console.error(`[OmniRoute] Error executing skill ${skillId}:`, error.message);
        throw error;
    } finally {
        if (fs.existsSync(tmpFile)) {
            fs.unlinkSync(tmpFile);
        }
    }
}

/**
 * Adds data to OmniRoute's persistent memory securely via file.
 * @param {string} type - The type of memory (e.g., 'disposition', 'transcript')
 * @param {Object} content - The structured content or text to store
 * @param {Object} metadata - Optional metadata (e.g., leadId, timestamp, tenantId, eventId)
 * @returns {Promise<boolean>}
 */
async function addOmniMemory(type, content, metadata = {}) {
    const tmpFile = path.join(os.tmpdir(), `omni_mem_${crypto.randomUUID()}.txt`);
    try {
        const contentStr = typeof content === 'string' ? content : JSON.stringify(content);
        fs.writeFileSync(tmpFile, contentStr, 'utf8');
        
        // Metadata only contains safe UUIDs/IDs, so it's safe to inline. 
        // We replace double quotes with \" for shell parsing on Windows.
        const metadataStr = JSON.stringify(metadata).replace(/"/g, '\\"');
        
        console.log(`[OmniRoute] Adding memory of type ${type}...`);
        
        const cmd = `npx --yes omniroute memory add --type "${type}" --file "${tmpFile}" --metadata "${metadataStr}"`;
        
        const { stdout } = await execPromise(cmd, { timeout: 15000 });
        
        return stdout.toLowerCase().includes('success') || stdout.toLowerCase().includes('added');
    } catch (error) {
        console.error(`[OmniRoute] Error adding memory:`, error.message);
        return false;
    } finally {
        if (fs.existsSync(tmpFile)) {
            fs.unlinkSync(tmpFile);
        }
    }
}

/**
 * Search data from OmniRoute's persistent memory securely.
 * @param {string} type - The type of memory
 * @returns {Promise<string>} raw output from omniroute
 */
async function searchOmniMemory(type) {
    try {
        console.log(`[OmniRoute] Searching memory of type ${type}...`);
        
        const cmd = `npx --yes omniroute memory search --type "${type}"`;
        const { stdout } = await execPromise(cmd, { timeout: 30000 });
        
        return stdout;
    } catch (error) {
        console.error(`[OmniRoute] Error searching memory:`, error.message);
        throw error;
    }
}

export {
    executeOmniSkill,
    addOmniMemory,
    searchOmniMemory
};
