// Music Video API v5 - Fixed URL extraction
import express from 'express';
import { Innertube } from 'youtubei.js';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;
app.use(cors());
app.use(express.json());

let yt = null;

async function getYT() {
  if (yt) return yt;
  yt = await Innertube.create({
    generate_session_locally: true,
    fetch: (input, init) => fetch(input, init),
  });
  console.log('[YT] Session ready');
  return yt;
}

getYT().catch(err => { console.error('[YT] Failed:', err.message); yt = null; });

// ── Audio URL extraction ──────────────────────────────────────────────────────
// Uses getBasicInfo -> streaming_data.adaptive_formats -> decipher
// Clients tried: ANDROID_MUSIC -> IOS -> WEB
async function getAudioUrl(instance, videoId) {
  const clients = ['ANDROID_MUSIC', 'IOS', 'WEB'];

  for (const client of clients) {
    try {
      const info = await instance.getBasicInfo(videoId, { client });
      const formats = info?.streaming_data?.adaptive_formats || [];

      const audioFmts = formats
        .filter(f => f.has_audio && !f.has_video)
        .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0));

      if (!audioFmts.length) continue;

      const fmt = audioFmts[0];

      if (!fmt.url && fmt.decipher) {
        try { fmt.url = await fmt.decipher(instance.session.player); } catch (_) {}
      }

      if (fmt.url) {
        console.log(`[AUDIO] OK ${videoId} via ${client}`);
        return fmt;
      }
    } catch (e) {
      console.log(`[AUDIO] ${client} failed ${videoId}: ${e.message}`);
    }
  }

  // Last resort: getStreamingData
  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'audio', quality: 'best', client: 'ANDROID' });
    if (fmt) {
      if (!fmt.url && fmt.decipher) {
        try { fmt.url = await fmt.decipher(instance.session.player); } catch (_) {}
      }
      if (fmt.url) { console.log(`[AUDIO] streamingData OK ${videoId}`); return fmt; }
    }
  } catch (e) {
    console.log(`[AUDIO] streamingData failed ${videoId}: ${e.message}`);
  }

  console.log(`[AUDIO] all failed ${videoId}`);
  return null;
}

// ── Video URL extraction ──────────────────────────────────────────────────────
async function getVideoUrl(instance, videoId) {
  const clients = ['ANDROID_MUSIC', 'IOS', 'WEB'];

  for (const client of clients) {
    try {
      const info = await instance.getBasicInfo(videoId, { client });
      const formats = info?.streaming_data?.adaptive_formats || [];

      const videoFmts = formats
        .filter(f => f.has_video && !f.has_audio)
        .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0));

      if (!videoFmts.length) continue;

      const fmt = videoFmts[0];

      if (!fmt.url && fmt.decipher) {
        try { fmt.url = await fmt.decipher(instance.session.player); } catch (_) {}
      }

      if (fmt.url) { console.log(`[VIDEO] OK ${videoId} via ${client}`); return fmt; }
    } catch (e) {
      console.log(`[VIDEO] ${client} failed ${videoId}: ${e.message}`);
    }
  }

  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'video', quality: 'best', client: 'ANDROID' });
    if (fmt) {
      if (!fmt.url && fmt.decipher) {
        try { fmt.url = await fmt.decipher(instance.session.player); } catch (_) {}
      }
      if (fmt.url) { console.log(`[VIDEO] streamingData OK ${videoId}`); return fmt; }
    }
  } catch (e) {
    console.log(`[VIDEO] streamingData failed ${videoId}: ${e.message}`);
  }

  console.log(`[VIDEO] all failed ${videoId}`);
  return null;
}

// ── Metadata ─────────────────────────────────────────────────────────────────
async function getMeta(instance, videoId) {
  try {
    const info = await instance.getBasicInfo(videoId, { client: 'WEB' });
    const bi = info?.basic_info || {};
    const thumbs = bi.thumbnail || [];
    return {
      title: bi.title || '',
      author: bi.author || '',
      duration: bi.duration || 0,
      duration_text: bi.duration_text || '',
      view_count: bi.view_count || 0,
      thumbnail: thumbs.find(t => t.width >= 480)?.url || thumbs[0]?.url ||
                 `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
    };
  } catch (e) {
    console.log(`[META] err ${videoId}: ${e.message}`);
    return { title: '', author: '', duration: 0, duration_text: '', view_count: 0,
             thumbnail: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` };
  }
}

// ── ROOT ──────────────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({
    name: 'Music Video API', version: '5.0',
    endpoints: {
      search: '/search?q=query&limit=5&urls=true',
      stream: '/stream/:videoId?type=audio|video',
      details: '/details/:videoId',
      info: '/info/:videoId'
    }
  });
});

// ── SEARCH ────────────────────────────────────────────────────────────────────
// ?urls=false  -> skip audio/video URL fetch (fast, use /stream/:id separately)
// ?urls=true   -> fetch URLs eagerly (default, slower ~2-3s per result)
app.get('/search', async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: 'q required' });

    const limit = Math.min(parseInt(req.query.limit) || 5, 10);
    const fetchUrls = req.query.urls !== 'false';

    const instance = await getYT();
    const search = await instance.search(q);
    const videos = (search.results || []).filter(i => i.type === 'Video').slice(0, limit);

    const results = [];
    for (const v of videos) {
      const videoId = v.id;
      const thumb =
        v.thumbnail?.contents?.[0] ||
        v.best_thumbnail ||
        { url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` };

      let af = null, vf = null;
      if (fetchUrls) {
        [af, vf] = await Promise.all([
          getAudioUrl(instance, videoId),
          getVideoUrl(instance, videoId)
        ]);
      }

      results.push({
        id: videoId,
        title: v.title?.text || v.title || '',
        duration: v.duration?.seconds || v.duration || 0,
        duration_text: v.duration?.text || '',
        views: v.view_count?.text || v.views || '',
        author: v.author?.name || v.author || '',
        thumbnail: thumb.url,
        audio_url: af?.url || null,
        video_url: vf?.url || null,
        audio_mime: af?.mime_type || null,
        video_mime: vf?.mime_type || null,
        audio_bitrate: af?.bitrate || null,
        video_resolution: (vf?.width && vf?.height) ? `${vf.width}x${vf.height}` : null,
      });
    }

    res.json({ query: q, count: results.length, results });

  } catch (err) {
    console.error('[SEARCH ERROR]', err.message);
    yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ── STREAM ────────────────────────────────────────────────────────────────────
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audio';

    const instance = await getYT();
    const fmt = type === 'video'
      ? await getVideoUrl(instance, videoId)
      : await getAudioUrl(instance, videoId);

    if (!fmt || !fmt.url) {
      return res.status(404).json({ error: 'Could not extract URL for this video' });
    }

    res.json({
      id: videoId, type,
      url: fmt.url,
      mime_type: fmt.mime_type,
      has_audio: fmt.has_audio,
      has_video: fmt.has_video,
      content_length: fmt.content_length,
      bitrate: fmt.bitrate,
      audio_sample_rate: fmt.audio_sample_rate,
      width: fmt.width,
      height: fmt.height,
      fps: fmt.fps
    });

  } catch (err) {
    console.error('[STREAM ERROR]', err.message);
    if (err.message?.includes('404')) yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ── DETAILS ───────────────────────────────────────────────────────────────────
app.get('/details/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const instance = await getYT();

    const [meta, af, vf] = await Promise.all([
      getMeta(instance, videoId),
      getAudioUrl(instance, videoId),
      getVideoUrl(instance, videoId)
    ]);

    res.json({
      id: videoId, ...meta,
      audio: af ? {
        url: af.url, mime_type: af.mime_type, bitrate: af.bitrate,
        content_length: af.content_length, audio_sample_rate: af.audio_sample_rate
      } : null,
      video: vf ? {
        url: vf.url, mime_type: vf.mime_type, bitrate: vf.bitrate,
        content_length: vf.content_length, width: vf.width, height: vf.height, fps: vf.fps
      } : null
    });

  } catch (err) {
    console.error('[DETAILS ERROR]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── INFO ──────────────────────────────────────────────────────────────────────
app.get('/info/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const instance = await getYT();
    const meta = await getMeta(instance, videoId);
    res.json({ id: videoId, ...meta });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
