import fs from 'fs';
import { processGpxFiles, calculateTrackStatistics } from 'fastgeotoolkit';

async function processTrails(gpxFilePaths) {
    try {
        const fileBuffers = gpxFilePaths.map(filePath => {
            const buffer = fs.readFileSync(filePath);
            return new Uint8Array(buffer);
        });

        const heatmap = await processGpxFiles(fileBuffers);

        const trackStats = [];
        for (const track of heatmap.tracks) {
            const stats = await calculateTrackStatistics(track.coordinates);
            trackStats.push({
                frequency: track.frequency,
                distance_km: stats.distance_km,
                point_count: stats.point_count,
                bounding_box: stats.bounding_box,
                coordinates: track.coordinates
            });
        }

        const result = {
            totalTracks: heatmap.tracks.length,
            maxFrequency: heatmap.max_frequency,
            tracks: trackStats
        };

        // Only JSON to stdout
        console.log(JSON.stringify(result));
        return result;
    } catch (error) {
        console.error('Error processing tracks:', error.message);
        process.exit(1);
    }
}

const args = process.argv.slice(2);
if (args.length === 0) {
    console.error('Usage: node process_tracks.mjs <gpx_file1> <gpx_file2> ...');
    process.exit(1);
}

await processTrails(args);