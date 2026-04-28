import express from 'express';
import cors from 'cors';
import { Innertube } from 'youtubei.js';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Global Innertube instance (lazy init)
let youtube = null;

async function getYoutube() {
  if (!youtube) {
    youtube = await Innertube.create({
      lang: 'en',
      location: 'US',
      retrieve_player: true,   // needed for deciphering stream URLs
    });
  }
  return youtube;
}

/**
 * GET /search?q=artist+song+name
 * Returns: { results: [{ id, title, duration, author, thumbnails, videoUrl, audioUrl, thumbnail }] }
 */
app.get('/search', async (req, res) => {
  try {
    const query = req.query.q;
    if (!query) {
      return res.status(400).json({ error: 'Query parameter "q" is required' });
    }

    const yt = await getYoutube();

    // Search for videos (type: video only)
    const search = await yt.search(query, { type: 'video' });

    // Get first 10 video results
    const videos = search.videos.slice(0, 10);

    if (videos.length === 0) {
      return res.json({ results: [] });
    }

    // Fetch detailed info (including streaming data) for each video
    const results = await Promise.all(
      videos.map(async (video) => {
        try {
          const info = await yt.getInfo(video.video_id);

          // --- Get best thumbnail ---
          const thumbnail =
            video.thumbnails?.[0]?.url ||
            `https://img.youtube.com/vi/${video.video_id}/hqdefault.jpg`;

          // --- Audio stream (best audio-only format) ---
          const audioFormat = info.chooseFormat({
            type: 'audio',
            quality: 'best',
          });
          const audioUrl = audioFormat?.url || null;

          // --- Video stream (best video+audio combined, medium quality) ---
          const videoFormat = info.chooseFormat({
            type: 'videoandaudio',
            quality: '360p',  // or '720p', '480p', etc.
          });
          const videoUrl = videoFormat?.url || null;

          return {
            id: video.video_id,
            title: video.title?.toString() || 'Untitled',
            duration: video.duration?.text || '0:00',
            author: {
              name: video.author?.name || 'Unknown',
              channel_url: video.author?.channel_url || null,
            },
            thumbnails: video.thumbnails.map((t) => ({
              url: t.url,
              width: t.width,
              height: t.height,
            })),
            thumbnail,         // best single thumbnail URL
            videoUrl,           // streaming URL (video+audio)
            audioUrl,           // streaming URL (audio only)
          };
        } catch (err) {
          // Skip individual video errors
          return null;
        }
      })
    );

    // Filter out failed results
    const filtered = results.filter((r) => r !== null);

    res.json({
      query,
      count: filtered.length,
      results: filtered,
    });
  } catch (err) {
    console.error('Search error:', err);
    res.status(500).json({ error: err.message || 'Internal server error' });
  }
});

/**
 * GET /stream/:videoId
 * Optional: ?type=audio|video|videoandaudio
 * Returns streaming URL directly for a known video ID
 */
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'videoandaudio';
    const quality = req.query.quality || (type === 'audio' ? 'best' : '360p');

    const yt = await getYoutube();
    const info = await yt.getInfo(videoId);

    const format = info.chooseFormat({ type, quality });

    if (!format || !format.url) {
      return res.status(404).json({ error: 'No suitable stream found' });
    }

    res.json({
      id: videoId,
      title: info.basic_info.title,
      url: format.url,
      mime_type: format.mime_type,
      quality: format.quality_label || format.quality,
      content_length: format.content_length,
      thumbnail: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
    });
  } catch (err) {
    console.error('Stream error:', err);
    res.status(500).json({ error: err.message || 'Internal server error' });
  }
});

/**
 * GET /thumbnail/:videoId
 * Redirects to the video's maxres thumbnail
 */
app.get('/thumbnail/:videoId', (req, res) => {
  const { videoId } = req.params;
  // YouTube thumbnail URL formats (from best to fallback)
  const url = `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
  res.redirect(url);
});

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'Music Video API is running' });
});

app.listen(PORT, () => {
  console.log(`🎵 Music Video API running on port ${PORT}`);
});
