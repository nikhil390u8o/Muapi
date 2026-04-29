import express from 'express';
import cors from 'cors';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);
const app = express();
const PORT = process.env.PORT || 3000;
const baseArgs = [
  '--no-warnings',
  '--cookies', '/etc/secrets/.cookies.txt',          // ← ye add karo
  '--extractor-args', 'youtube:player_client=web,default',
];

app.use(cors());
app.use(express.json());

// ── yt-dlp helper ─────────────────────────────────────────────────────────────
async function ytdlp(...args) {
  const { stdout } = await execFileAsync('yt-dlp', args, { maxBuffer: 10 * 1024 * 1024 });
  return stdout.trim();
}

// Search YouTube → returns array of {id, title, duration, thumbnail, author}
async function ytSearch(query, limit = 5) {
  const raw = await ytdlp(
    `ytsearch${limit}:${query}`,
    '--dump-json',
    '--flat-playlist',
    '--no-warnings',
    '--skip-download'
  );
  return raw.split('\n').filter(Boolean).map(line => {
    const v = JSON.parse(line);
    const dur = v.duration || 0;
    const mins = Math.floor(dur / 60);
    const secs = String(dur % 60).padStart(2, '0');
    return {
      id: v.id,
      title: v.title || '',
      author: v.uploader || v.channel || '',
      duration: dur,
      duration_text: dur ? `${mins}:${secs}` : '',
      thumbnail: v.thumbnail || `https://i.ytimg.com/vi/${v.id}/hq720.jpg`,
    };
  });
}

// Get audio + video URLs for a videoId
async function getUrls(videoId) {
  const raw = await ytdlp(
    `https://www.youtube.com/watch?v=${videoId}`,
    '--dump-json',
    '--no-warnings',
    '--skip-download',
    '-f', 'bestaudio,bestvideo'
  );

  // yt-dlp may return 1 or 2 JSON lines (one per format requested)
  const lines = raw.split('\n').filter(Boolean);
  const info = JSON.parse(lines[0]); // full info is always in first line

  // Pick best audio-only format
  const formats = info.formats || [];
  const audioFmts = formats
    .filter(f => f.acodec !== 'none' && f.vcodec === 'none' && f.url)
    .sort((a, b) => (b.abr || b.tbr || 0) - (a.abr || a.tbr || 0));

  const videoFmts = formats
    .filter(f => f.vcodec !== 'none' && f.acodec === 'none' && f.url)
    .sort((a, b) => (b.height || 0) - (a.height || 0));

  const af = audioFmts[0] || null;
  const vf = videoFmts[0] || null;

  const dur = info.duration || 0;
  const mins = Math.floor(dur / 60);
  const secs = String(dur % 60).padStart(2, '0');

  return {
    id: videoId,
    title: info.title || '',
    author: info.uploader || info.channel || '',
    duration: dur,
    duration_text: dur ? `${mins}:${secs}` : '',
    thumbnail: info.thumbnail || `https://i.ytimg.com/vi/${videoId}/hq720.jpg`,
    audio_url: af?.url || null,
    video_url: vf?.url || null,
    audio_mime: af ? `audio/${af.ext}` : null,
    video_mime: vf ? `video/${vf.ext}` : null,
    audio_bitrate: af?.abr || af?.tbr || null,
    video_resolution: vf ? `${vf.width}x${vf.height}` : null,
  };
}

// ── ROOT ──────────────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({
    name: 'MuAPI', version: '6.0',
    endpoints: {
      search:  '/search?q=song+name&limit=5',
      stream:  '/stream/:videoId',
      details: '/details/:videoId',
    }
  });
});

// ── SEARCH ────────────────────────────────────────────────────────────────────
// ?urls=true  → also fetch audio/video URLs (slower)
// ?urls=false → only metadata, use /stream/:id separately (faster) [DEFAULT]
app.get('/search', async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: 'q required' });

    const limit = Math.min(parseInt(req.query.limit) || 5, 10);
    const fetchUrls = req.query.urls === 'true';

    const results = await ytSearch(q, limit);

    if (fetchUrls) {
      const withUrls = await Promise.all(results.map(r => getUrls(r.id)));
      return res.json({ query: q, count: withUrls.length, results: withUrls });
    }

    res.json({ query: q, count: results.length, results });

  } catch (err) {
    console.error('[SEARCH]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── STREAM (audio URL only) ───────────────────────────────────────────────────
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const data = await getUrls(videoId);
    if (!data.audio_url) return res.status(404).json({ error: 'Audio URL not found' });
    res.json(data);
  } catch (err) {
    console.error('[STREAM]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── DETAILS (audio + video URLs) ──────────────────────────────────────────────
app.get('/details/:videoId', async (req, res) => {
  try {
    const data = await getUrls(req.params.videoId);
    res.json(data);
  } catch (err) {
    console.error('[DETAILS]', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`MuAPI running on port ${PORT}`));
