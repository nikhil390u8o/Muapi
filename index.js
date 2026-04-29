// server.js - Music Video API - FIXED VERSION
import express from 'express';
import { Innertube } from 'youtubei.js';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Global yt instance - ek hi baar create karo
let yt = null;
let ytInitialized = false;

async function getYT() {
  if (yt && ytInitialized) return yt;
  yt = await Innertube.create({
    // Optional: agar cache set karna ho to
    // cache: new UniversalCache(false)
  });
  ytInitialized = true;
  console.log('[YT] Session created successfully');
  return yt;
}

// Initialize on startup
getYT().catch(err => {
  console.error('[YT] Initial creation failed:', err.message);
  ytInitialized = false;
});

// ============ SEARCH ENDPOINT ============
app.get('/search', async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: 'Query parameter "q" is required' });

    const instance = yt || await getYT();
    const search = await instance.search(q);
    
    let results = [];
    
    // Primary: search.results
    if (search.results) {
      const videos = search.results.filter(item => item.type === 'Video');
      results = videos.map(v => {
        const thumb = v.thumbnail?.contents?.[0] || 
                      v.best_thumbnail || 
                      { url: `https://i.ytimg.com/vi/${v.id}/hqdefault.jpg` };
        return {
          id: v.id,
          title: v.title?.text || v.title || '',
          duration: v.duration?.seconds || v.duration || 0,
          duration_text: v.duration?.text || '',
          views: v.views || '',
          author: v.author?.name || v.author || '',
          thumbnail: thumb.url,
          streamApi: `https://muapi.onrender.com/stream/${v.id}`
        };
      });
    }
    
    res.json({ 
      query: q, 
      count: results.length, 
      results 
    });
  } catch (err) {
    console.error('[SEARCH ERROR]', err.message);
    // Agar session expired ho to reset karo
    if (err.message?.includes('404') || err.message?.includes('403')) {
      ytInitialized = false;
      yt = null;
    }
    res.status(500).json({ error: err.message });
  }
});

// ============ STREAM ENDPOINT - FIXED ============
app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audio';
    const quality = req.query.quality || 'best';
    
    if (!videoId) {
      return res.status(400).json({ error: 'Video ID is required' });
    }
    
    let instance = yt;
    if (!instance) {
      instance = await getYT();
    }
    
    let format;
    let info;
    
    // TRY 1: ANDROID client ke saath getStreamingData()
    try {
      format = await instance.getStreamingData(videoId, {
        type: type === 'videoandaudio' ? 'video+audio' : type,
        quality: quality,
        client: 'ANDROID'
      });
      console.log(`[STREAM] ANDROID client success for ${videoId}`);
    } catch (err1) {
      console.log(`[STREAM] ANDROID failed: ${err1.message}, trying WEB...`);
      
      // TRY 2: WEB client ke saath
      try {
        format = await instance.getStreamingData(videoId, {
          type: type === 'videoandaudio' ? 'video+audio' : type,
          quality: quality,
          client: 'WEB'
        });
        console.log(`[STREAM] WEB client success for ${videoId}`);
      } catch (err2) {
        console.log(`[STREAM] WEB failed: ${err2.message}, trying getBasicInfo fallback...`);
        
        // TRY 3: getBasicInfo se info lo and manually extract
        try {
          info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
          
          if (!info.streaming_data) {
            // TRY 4: WEB client ke saath
            info = await instance.getBasicInfo(videoId, { client: 'WEB' });
          }
          
          if (!info.streaming_data) {
            throw new Error('Streaming data not available in any client');
          }
          
          format = info.chooseFormat({
            type: type === 'videoandaudio' ? 'video+audio' : type,
            quality: quality
          });
          
          if (!format) {
            throw new Error(`No format found for type=${type} quality=${quality}`);
          }
          
          // v17 mein decipher async hai!
          format.url = await format.decipher(instance.session.player);
        } catch (err3) {
          // TRY 5: Session recreate karke try karo
          console.log('[STREAM] All attempts failed, recreating session...');
          ytInitialized = false;
          yt = null;
          instance = await getYT();
          
          format = await instance.getStreamingData(videoId, {
            type: type === 'videoandaudio' ? 'video+audio' : type,
            quality: quality,
            client: 'ANDROID'
          });
        }
      }
    }
    
    // --- RESPONSE ---
    const responseData = {
      id: videoId,
      type: type,
      quality: quality,
      url: format.url,
      mime_type: format.mime_type,
      container: format.container,
      codec: format.codec,
      has_audio: format.has_audio,
      has_video: format.has_video,
      content_length: format.content_length,
      bitrate: format.bitrate,
      audio_sample_rate: format.audio_sample_rate,
      audio_channels: format.audio_channels,
      width: format.width,
      height: format.height,
      fps: format.fps
    };
    
    // Agar info available hai to aur details bhejo
    if (info) {
      responseData.title = info.basic_info?.title;
      responseData.duration = info.basic_info?.duration;
      responseData.thumbnail = info.basic_info?.thumbnail?.find(t => t.width >= 320)?.url || 
                               info.basic_info?.thumbnail?.[0]?.url ||
                               `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
    }
    
    res.json(responseData);
    
  } catch (err) {
    console.error('[STREAM ERROR]', err.message);
    if (err.message?.includes('404')) {
      ytInitialized = false;
      yt = null;
    }
    res.status(500).json({ error: err.message });
  }
});

// ============ VIDEO INFO ENDPOINT ============
app.get('/info/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    
    let instance = yt;
    if (!instance) instance = await getYT();
    
    const info = await instance.getBasicInfo(videoId, { client: 'ANDROID' });
    
    const formats = info.streaming_data ? 
      info.streaming_data.adaptive_formats.map(f => ({
        itag: f.itag,
        mime_type: f.mime_type,
        quality: f.quality || f.quality_label,
        has_audio: f.has_audio,
        has_video: f.has_video,
        bitrate: f.bitrate,
        content_length: f.content_length,
        width: f.width,
        height: f.height,
        fps: f.fps,
        audio_sample_rate: f.audio_sample_rate,
        audio_channels: f.audio_channels,
        container: f.container,
        codec: f.codec,
        approx_duration_ms: f.approx_duration_ms,
        // URL decipher ke baad resolve karo
      })) : [];
    
    res.json({
      id: videoId,
      title: info.basic_info?.title,
      duration: info.basic_info?.duration,
      duration_text: info.basic_info?.duration_text,
      thumbnail: info.basic_info?.thumbnail?.[0]?.url || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
      thumbnails: info.basic_info?.thumbnail,
      author: info.basic_info?.author,
      channel_id: info.basic_info?.channel_id,
      is_live: info.basic_info?.is_live,
      view_count: info.basic_info?.view_count,
      short_description: info.basic_info?.short_description,
      likes: info.basic_info?.like_count,
      streaming_data_available: !!info.streaming_data,
      formats_count: formats.length,
      formats: formats
    });
    
  } catch (err) {
    console.error('[INFO ERROR]', err.message);
    if (err.message?.includes('404')) {
      ytInitialized = false;
      yt = null;
    }
    res.status(500).json({ error: err.message });
  }
});

app.get('/', (req, res) => {
  res.json({
    name: 'Music Video API',
    version: '2.0-fixed',
    endpoints: {
      search: '/search?q=query',
      stream: '/stream/:videoId?type=audio|video|video+audio&quality=best',
      info: '/info/:videoId'
    }
  });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Search: http://localhost:${PORT}/search?q=linkin+park+numb`);
  console.log(`Stream (audio): http://localhost:${PORT}/stream/kXYiU_JCYtU?type=audio&quality=best`);
  console.log(`Stream (video+audio): http://localhost:${PORT}/stream/kXYiU_JCYtU?type=video+audio&quality=best`);
  console.log(`Info: http://localhost:${PORT}/info/kXYiU_JCYtU`);
});
