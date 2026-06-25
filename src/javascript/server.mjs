// src/javascript/server.mjs
import http from 'http';
import fs from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

// --- 1. Locate the WASM file ---
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Try to find the WASM file – check common locations
const possibleWasmPaths = [
    path.resolve(__dirname, '../../node_modules/fastgeotoolkit/wasm/fastgeotoolkit.wasm'),
    path.resolve(__dirname, '../../node_modules/fastgeotoolkit/dist/wasm/fastgeotoolkit.wasm'),
    path.resolve(__dirname, '../../node_modules/fastgeotoolkit/wasm/fastgeotoolkit_bg.wasm'),
];
let wasmPath = null;
for (const p of possibleWasmPaths) {
    if (fs.existsSync(p)) {
        wasmPath = p;
        break;
    }
}
if (!wasmPath) {
    console.error('❌ Could not find fastgeotoolkit.wasm. Searched in:');
    possibleWasmPaths.forEach(p => console.error(`  - ${p}`));
    process.exit(1);
}
console.log(`✅ Found WASM file: ${wasmPath}`);
const wasmBuffer = fs.readFileSync(wasmPath);

// --- 2. Override global.fetch to serve the WASM locally ---
const originalFetch = globalThis.fetch || global.fetch;

globalThis.fetch = async (url, ...args) => {
    const urlStr = String(url);
    console.log(`[fetch] URL: ${urlStr}`);  // <-- Log every fetch

    // If this is a request for the WASM file, return our local buffer
    if (urlStr.includes('fastgeotoolkit.wasm') || urlStr.includes('fastgeotoolkit_bg.wasm')) {
        console.log('✅ Intercepted WASM request, serving local file.');
        return new Response(wasmBuffer, {
            status: 200,
            headers: { 'Content-Type': 'application/wasm' }
        });
    }

    // Otherwise, fall back to original fetch
    if (originalFetch) {
        return originalFetch(url, ...args);
    }
    // If no original, use built-in fetch (Node 18+)
    return fetch(url, ...args);
};

// --- 3. Now import fastgeotoolkit ---
import { processGpxFiles } from 'fastgeotoolkit';

const PORT = 3000;

const server = http.createServer(async (req, res) => {
    if (req.method !== 'POST' || req.url !== '/process') {
        res.writeHead(404);
        res.end();
        return;
    }

    try {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const { files } = JSON.parse(body);
                if (!Array.isArray(files) || files.length === 0) {
                    throw new Error('Invalid input: "files" must be a non-empty array');
                }

                const fileBuffers = files.map(filePath => {
                    const buffer = fs.readFileSync(filePath);
                    return new Uint8Array(buffer);
                });

                const result = await processGpxFiles(fileBuffers);

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (error) {
                console.error('Processing error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: error.message, stack: error.stack }));
            }
        });
    } catch (error) {
        res.writeHead(500);
        res.end(JSON.stringify({ error: error.message }));
    }
});

server.listen(PORT, () => {
    console.log(`FastGeoToolkit server running on http://localhost:${PORT}`);
    console.log(`WASM file path: ${wasmPath}`);
});