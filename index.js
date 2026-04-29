// Music Video API - Clean Rewrite v3
import express from 'express';
import { Innertube } from 'youtubei.js';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;
app.use(cors());
app.use(express.json());

// ============ YT SESSION ============
let yt = null;

async function getYT() {
  if (yt) return yt;
  console.log('[YT] Creating session...');
  yt = await Innertube.create({});
  console.log('[YT] Session ready');
  return yt;
}

getYT().catch(err => { console.error('[YT] Startup failed:', err.message); yt = null; });

// ============ CORE: getBasicInfo + chooseFormat + decipher ============
// This is the proven approach - same as what /stream TRY3 does
async function getStreamUrls(videoId) {
  const instance = await getYT();
  let info;

  try {
    info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
  } catch (e) {
    console.log(`[URL] ANDROID failed ${videoId}: ${e.message}`);
    try {
      info = await instance.getBasicInfo(videoId, { client: 'WEB' });
    } catch (e2) {
      console.log(`[URL] WEB also failed ${videoId}: ${e2.message}`);
      return { audio: null, video: null };
    }
  }

  if (!info?.streaming_data) {
    console.log(`[URL] No streaming_data for ${videoId}`);
    return { audio: null, video: null };
  }

  let audioFmt = null;
  let videoFmt = null;

  try {
    const af = info.chooseFormat({ type: 'audio', quality: 'best' });
    if (af) {
      af.url = await af.decipher(instance.session.player);
      if (af.url) { audioFmt = af; console.log(`[URL] audio OK ${videoId}`); }
    }
  } catch (e) { console.log(`[URL] audio decipher failed ${videoId}: ${e.message}`); }

  try {
    const vf = info.chooseFormat({ type: 'video', quality: 'best' });
    if (vf) {
      vf.url = await vf.decipher(instance.session.player);
      if (vf.url) { videoFmt = vf; console.log(`[URL] video OK ${videoId}`); }
    }
  } catch (e) { console.log(`[URL] video decipher failed ${videoId}: ${e.message}`); }

  return { audio: audioFmt, video: videoFmt };
}

// ============ ROOT ============
app.get('/', (req, res) => {
  res.json({
    name: 'Music Video API', version: '3.0',
    endpoints: {
      search: '/search?q=query&limit=5',
      stream: '/stream/:videoId?type=audio|video',
      details: '/details/:videoId',
      info: '/info/:videoId'
    }
  });
});

// ============ SEARCH — audio+video URLs inline ============
app.get('/search', async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: 'Query "q" required' });
    const limit = Math.min(parseInt(req.query.limit) || 5, 10);

    const instance = await getYT();
    const search = await instance.search(q);

    let videos = [];
    if (search.results) {
      videos = search.results.filter(item => item.type === 'Video').slice(0, limit);
    }

    const results = [];
    for (const v of videos) {
      const videoId = v.id;
      const thumb = v.thumbnail?.contents?.[0] ||
                    v.best_thumbnail ||
                    { url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` };

      const { audio: af, video: vf } = await getStreamUrls(videoId);

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

// ============ STREAM — single format URL ============
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audio';
    const quality = req.query.quality || 'best';
    if (!videoId) return res.status(400).json({ error: 'videoId required' });

    const instance = await getYT();
    let format;

    // TRY 1: ANDROID getStreamingData
    try {
      format = await instance.getStreamingData(videoId, {
        type: type === 'videoandaudio' ? 'video+audio' : type,
        quality, client: 'ANDROID'
      });
      console.log(`[STREAM] ANDROID OK ${videoId}`);
    } catch (e1) {
      console.log(`[STREAM] ANDROID failed: ${e1.message}`);
      // TRY 2: WEB getStreamingData
      try {
        format = await instance.getStreamingData(videoId, {
          type: type === 'videoandaudio' ? 'video+audio' : type,
          quality, client: 'WEB'
        });
        console.log(`[STREAM] WEB OK ${videoId}`);
      } catch (e2) {
        console.log(`[STREAM] WEB failed: ${e2.message}`);
        // TRY 3: getBasicInfo + chooseFormat + decipher
        let info = await instance.getBasicInfo(videoId, { client: 'ANDROID' }).catch(() =>
          instance.getBasicInfo(videoId, { client: 'WEB' })
        );
        format = info.chooseFormat({ type: type === 'videoandaudio' ? 'video+audio' : type, quality });
        if (!format) throw new Error(`No format for type=${type}`);
        format.url = await format.decipher(instance.session.player);
      }
    }

    res.json({
      id: videoId, type, quality,
      url: format.url,
      mime_type: format.mime_type,
      has_audio: format.has_audio,
      has_video: format.has_video,
      content_length: format.content_length,
      bitrate: format.bitrate,
      audio_sample_rate: format.audio_sample_rate,
      width: format.width,
      height: format.height,
      fps: format.fps
    });

  } catch (err) {
    console.error('[STREAM ERROR]', err.message);
    if (err.message?.includes('404')) yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ============ DETAILS — full info + both URLs ============
app.get('/details/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    if (!videoId) return res.status(400).json({ error: 'videoId required' });

    const instance = await getYT();
    let info;
    try {
      info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
    } catch {
      info = await instance.getBasicInfo(videoId, { client: 'WEB' });
    }

    const bi = info?.basic_info || {};
    const thumbs = bi.thumbnail || [];
    const thumbnail = thumbs.find(t => t.width >= 480)?.url || thumbs[0]?.url ||
                      `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;

    const { audio: af, video: vf } = await getStreamUrls(videoId);

    res.json({
      id: videoId,
      title: bi.title || '',
      author: bi.author || '',
      duration: bi.duration || 0,
      duration_text: bi.duration_text || '',
      view_count: bi.view_count || 0,
      thumbnail,
      audio: af ? { url: af.url, mime_type: af.mime_type, bitrate: af.bitrate, content_length: af.content_length, audio_sample_rate: af.audio_sample_rate } : null,
      video: vf ? { url: vf.url, mime_type: vf.mime_type, bitrate: vf.bitrate, content_length: vf.content_length, width: vf.width, height: vf.height, fps: vf.fps } : null
    });

  } catch (err) {
    console.error('[DETAILS ERROR]', err.message);
    if (err.message?.includes('404')) yt = null;
    res.status(500).json({ error: err.message });
  }
});

// ============ INFO — metadata only ============
app.get('/info/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const instance = await getYT();
    const info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
    res.json({
      id: videoId,
      title: info.basic_info?.title,
      duration: info.basic_info?.duration,
      duration_text: info.basic_info?.duration_text,
      thumbnail: info.basic_info?.thumbnail?.[0]?.url || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
      author: info.basic_info?.author,
      view_count: info.basic_info?.view_count,
      is_live: info.basic_info?.is_live
    });
  } catch (err) {
    console.error('[INFO ERROR]', err.message);
    if (err.message?.includes('404')) yt = null;
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
