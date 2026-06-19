// src/javascript/server.mjs
import http from 'http';
import fs from 'fs';
import { processGpxFiles } from 'fastgeotoolkit';

const PORT = 3000;

const server = http.createServer(async (req, res) => {
    // Only accept POST requests to the /process endpoint
    if (req.method !== 'POST' || req.url !== '/process') {
        res.writeHead(404);
        res.end();
        return;
    }

    try {
        // Read the request body which contains a JSON array of file paths
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const { files } = JSON.parse(body);
                if (!Array.isArray(files) || files.length === 0) {
                    throw new Error('Invalid input: "files" must be a non-empty array');
                }

                // Read each file into a Uint8Array (required by fastgeotoolkit)
                const fileBuffers = files.map(filePath => {
                    const buffer = fs.readFileSync(filePath);
                    return new Uint8Array(buffer);
                });

                // Process the files using fastgeotoolkit
                const result = await processGpxFiles(fileBuffers);

                // Send the result as JSON
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (error) {
                // Send error details back to the client
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: error.message }));
            }
        });
    } catch (error) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: error.message }));
    }
});

server.listen(PORT, () => {
    console.log(`FastGeoToolkit server running on http://localhost:${PORT}`);
});