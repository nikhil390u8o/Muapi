import express from 'express';
import cors from 'cors';
import { Innertube, YTNodes } from 'youtubei.js';

const app = express();
app.use(cors());

let youtube;

async function initYoutube() {
  youtube = await Innertube.create({});
  console.log('✅ YouTube InnerTube initialized');
}
await initYoutube();

function extractVideoData(item) {
  try {
    const id = item.id;
    if (!id) return null;

    let title = '';
    let duration = null;
    let author = '';
    let thumbnails = [];

    if (item.title) title = item.title.toString();
    if (item.duration) {
      duration = typeof item.duration === 'object' ? item.duration.seconds : item.duration;
    }
    if (item.author) {
      author = item.author.name || item.author.toString() || '';
    }
    if (item.thumbnails) thumbnails = item.thumbnails;

    const bestThumb = thumbnails.length > 0
      ? thumbnails.reduce((a, b) => ((a.width || 0) > (b.width || 0) ? a : b)).url
      : `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

    return {
      id,
      title,
      duration,
      author,
      thumbnails,
      thumbnail: bestThumb,
      videoUrl: `/stream/${id}?type=videoandaudio&quality=best`,
      audioUrl: `/stream/${id}?type=audio&quality=best`,
    };
  } catch (e) {
    return null;
  }
}

app.get('/search', async (req, res) => {
  try {
    const query = req.query.q;
    if (!query) return res.status(400).json({ error: 'Query parameter required' });

    const search = await youtube.search(query);
    let videoItems = [];

    // Approach 1: search.results se
    if (search.results && search.results.length > 0) {
      videoItems = search.results.filter(item => item && item.id);
    }

    // Approach 2: memo se directly (agar results empty)
    if (videoItems.length === 0 && search.memo) {
      const videoTypes = [
        YTNodes.Video, YTNodes.GridVideo, YTNodes.CompactVideo,
        YTNodes.ReelItem, YTNodes.ShortsLockupView,
        YTNodes.WatchCardCompactVideo
      ];
      for (const type of videoTypes) {
        const nodes = search.memo.getType(type);
        if (nodes && nodes.length > 0) videoItems.push(...nodes);
      }
    }

    // Approach 3: shelves se
    if (videoItems.length === 0 && search.shelves) {
      for (const shelf of search.shelves) {
        if (shelf.contents && shelf.contents.length > 0) {
          for (const item of shelf.contents) {
            if (item && item.id) videoItems.push(item);
          }
        }
      }
    }

    // Dedup by id
    const seen = new Set();
    const uniqueItems = videoItems.filter(item => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });

    const mapped = uniqueItems.map(extractVideoData).filter(Boolean);

    res.json({ query, count: mapped.length, results: mapped });
  } catch (err) {
    console.error('Search error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audioandaudio';
    const quality = req.query.quality || 'best';

    const info = await youtube.getBasicInfo(videoId);
    let url;

    if (type === 'audio') {
      const format = info.chooseFormat({ type: 'audio', quality: 'best' });
      url = format?.decipher(youtube.session.player);
    } else {
      const format = info.chooseFormat({ type: 'video+audio', quality });
      url = format?.decipher(youtube.session.player);
    }

    if (!url) return res.status(404).json({ error: 'No stream URL found' });
    res.redirect(url);
  } catch (err) {
    console.error('Stream error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/thumbnail/:videoId', async (req, res) => {
  const { videoId } = req.params;
  res.redirect(`https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🎵 Music Video API running on port ${PORT}`);
});
