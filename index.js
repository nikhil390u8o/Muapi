// Music Video API v4 - Fixed
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
  yt = await Innertube.create({});
  console.log('[YT] Session ready');
  return yt;
}

getYT().catch(err => { console.error('[YT] Failed:', err.message); yt = null; });

// Get audio URL using getStreamingData (proven working in /stream endpoint)
async function getAudioUrl(instance, videoId) {
  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'audio', quality: 'best', client: 'ANDROID' });
    console.log(`[AUDIO] ANDROID ok ${videoId} url=${!!fmt?.url}`);
    if (fmt?.url) return fmt;
    // url might need decipher
    if (fmt) {
      try { fmt.url = await fmt.decipher(instance.session.player); } catch(_) {}
      if (fmt.url) return fmt;
    }
  } catch (e) { console.log(`[AUDIO] ANDROID err ${videoId}: ${e.message}`); }

  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'audio', quality: 'best', client: 'WEB' });
    console.log(`[AUDIO] WEB ok ${videoId} url=${!!fmt?.url}`);
    if (fmt?.url) return fmt;
    if (fmt) {
      try { fmt.url = await fmt.decipher(instance.session.player); } catch(_) {}
      if (fmt.url) return fmt;
    }
  } catch (e) { console.log(`[AUDIO] WEB err ${videoId}: ${e.message}`); }

  // Last resort: getBasicInfo + chooseFormat
  try {
    const info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
    const fmt = info?.chooseFormat?.({ type: 'audio', quality: 'best' });
    if (fmt) {
      fmt.url = await fmt.decipher(instance.session.player);
      if (fmt.url) { console.log(`[AUDIO] basicInfo ok ${videoId}`); return fmt; }
    }
  } catch (e) { console.log(`[AUDIO] basicInfo err ${videoId}: ${e.message}`); }

  console.log(`[AUDIO] all failed ${videoId}`);
  return null;
}

// Get video URL
async function getVideoUrl(instance, videoId) {
  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'video', quality: 'best', client: 'ANDROID' });
    console.log(`[VIDEO] ANDROID ok ${videoId} url=${!!fmt?.url}`);
    if (fmt?.url) return fmt;
    if (fmt) {
      try { fmt.url = await fmt.decipher(instance.session.player); } catch(_) {}
      if (fmt.url) return fmt;
    }
  } catch (e) { console.log(`[VIDEO] ANDROID err ${videoId}: ${e.message}`); }

  try {
    const fmt = await instance.getStreamingData(videoId, { type: 'video', quality: 'best', client: 'WEB' });
    console.log(`[VIDEO] WEB ok ${videoId} url=${!!fmt?.url}`);
    if (fmt?.url) return fmt;
    if (fmt) {
      try { fmt.url = await fmt.decipher(instance.session.player); } catch(_) {}
      if (fmt.url) return fmt;
    }
  } catch (e) { console.log(`[VIDEO] WEB err ${videoId}: ${e.message}`); }

  try {
    const info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
    const fmt = info?.chooseFormat?.({ type: 'video', quality: 'best' });
    if (fmt) {
      fmt.url = await fmt.decipher(instance.session.player);
      if (fmt.url) { console.log(`[VIDEO] basicInfo ok ${videoId}`); return fmt; }
    }
  } catch (e) { console.log(`[VIDEO] basicInfo err ${videoId}: ${e.message}`); }

  console.log(`[VIDEO] all failed ${videoId}`);
  return null;
}

// Get metadata using WEB client (ANDROID returns empty basic_info)
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

// ============ ROOT ============
app.get('/', (req, res) => {
  res.json({ name: 'Music Video API', version: '4.0',
    endpoints: { search: '/search?q=query&limit=5', stream: '/stream/:videoId?type=audio|video', details: '/details/:videoId', info: '/info/:videoId' }
  });
});

// ============ SEARCH — everything in one call ============
app.get('/search', async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: 'q required' });
    const limit = Math.min(parseInt(req.query.limit) || 5, 10);

    const instance = await getYT();
    const search = await instance.search(q);
    const videos = (search.results || []).filter(i => i.type === 'Video').slice(0, limit);

    const results = [];
    for (const v of videos) {
      const videoId = v.id;
      const thumb = v.thumbnail?.contents?.[0] || v.best_thumbnail ||
                    { url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` };

      // Fetch audio, video, meta in parallel
      const [af, vf] = await Promise.all([
        getAudioUrl(instance, videoId),
        getVideoUrl(instance, videoId)
      ]);

      results.push({
        id: videoId,
        title: v.title?.text || v.title || '',
        duration: v.duration?.seconds || v.duration || 0,
        duration_text: v.duration?.text || '',
        views: v.views || '',
        author: v.author?.name || v.author || '',
        thumbnail: thumb.url,
        audio_url: af?.url || null,
        video_url: vf?.url || null,
        audio_mime: af?.mime_type || null,
        video_mime: vf?.mime_type || null,
        audio_bitrate: af?.bitrate || null,
        video_resolution: (vf?.width && vf?.height) ? `${vf.width}x${vf.height}` : null
      });
    }

    res.json({ query: q, count: results.length, results });

  } catch (err) {
    console.error('[SEARCH ERROR]', err.message);
    yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ============ STREAM ============
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audio';
    const quality = req.query.quality || 'best';

    const instance = await getYT();
    let format;

    try {
      format = await instance.getStreamingData(videoId, {
        type: type === 'videoandaudio' ? 'video+audio' : type, quality, client: 'ANDROID'
      });
    } catch (e1) {
      try {
        format = await instance.getStreamingData(videoId, {
          type: type === 'videoandaudio' ? 'video+audio' : type, quality, client: 'WEB'
        });
      } catch (e2) {
        const info = await instance.getBasicInfo(videoId, { client: 'ANDROID' })
          .catch(() => instance.getBasicInfo(videoId, { client: 'WEB' }));
        format = info.chooseFormat({ type: type === 'videoandaudio' ? 'video+audio' : type, quality });
        if (!format) throw new Error(`No format for type=${type}`);
        format.url = await format.decipher(instance.session.player);
      }
    }

    res.json({
      id: videoId, type, url: format.url, mime_type: format.mime_type,
      has_audio: format.has_audio, has_video: format.has_video,
      content_length: format.content_length, bitrate: format.bitrate,
      audio_sample_rate: format.audio_sample_rate, width: format.width,
      height: format.height, fps: format.fps
    });

  } catch (err) {
    console.error('[STREAM ERROR]', err.message);
    if (err.message?.includes('404')) yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ============ DETAILS ============
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
      id: videoId,
      ...meta,
      audio: af ? { url: af.url, mime_type: af.mime_type, bitrate: af.bitrate, content_length: af.content_length, audio_sample_rate: af.audio_sample_rate } : null,
      video: vf ? { url: vf.url, mime_type: vf.mime_type, bitrate: vf.bitrate, content_length: vf.content_length, width: vf.width, height: vf.height, fps: vf.fps } : null
    });

  } catch (err) {
    console.error('[DETAILS ERROR]', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ============ INFO ============
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
