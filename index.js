import express from 'express';
import cors from 'cors';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);
const app = express();
const PORT = process.env.PORT || 3000;

const baseArgs = [
  '--no-warnings',
  '--cookies', '/etc/secrets/.cookies.txt',
  '--extractor-args', 'youtube:player_client=web,default',
];

app.use(cors());
app.use(express.json());

// ── yt-dlp helper ─────────────────────────────────────────────────────────────
async function ytdlp(...args) {
  // baseArgs PEHLE, phir custom args
  const { stdout } = await execFileAsync('yt-dlp', [...baseArgs, ...args], {
    maxBuffer: 10 * 1024 * 1024
  });
  return stdout.trim();
}

// Search YouTube
async function ytSearch(query, limit = 5) {
  const raw = await ytdlp(
    `ytsearch${limit}:${query}`,
    '--dump-json',
    '--flat-playlist',
    '--skip-download'
  );
  return raw.split('\n').filter(Boolean).map(line => {
    const v = JSON.parse(line);
    const dur = v.duration || 0;
    const mins = Math.floor(dur / 60);
    const secs = String(Math.floor(dur % 60)).padStart(2, '0');
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

// Get audio + video URLs
async function getUrls(videoId) {
  const raw = await ytdlp(
    `https://www.youtube.com/watch?v=${videoId}`,
    '--dump-json',
    '--skip-download',
    '-f', 'bestaudio,bestvideo'
  );

  const lines = raw.split('\n').filter(Boolean);
  const info = JSON.parse(lines[0]);
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
  const secs = String(Math.floor(dur % 60)).padStart(2, '0');

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

// ROOT
app.get('/', (req, res) => {
  res.json({ name: 'MuAPI', version: '6.2', status: 'ok' });
});

// SEARCH
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

// STREAM
app.get('/stream/:videoId', async (req, res) => {
  try {
    const data = await getUrls(req.params.videoId);
    if (!data.audio_url) return res.status(404).json({ error: 'Audio URL not found' });
    res.json(data);
  } catch (err) {
    console.error('[STREAM]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// DETAILS
app.get('/details/:videoId', async (req, res) => {
  try {
    const data = await getUrls(req.params.videoId);
    res.json(data);
  } catch (err) {
    console.error('[DETAILS]', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`MuAPI v6.2 running on port ${PORT}`));
