import express from 'express';
import fetch from 'node-fetch';
import { Innertube } from 'youtubei.js';

const app = express();
const PORT = process.env.PORT || 3000;

let youtube = null;

async function getYoutube() {
  if (!youtube) {
    youtube = await Innertube.create({
      retrieve_player: true,
      client_type: 'ANDROID',
    });
  }
  return youtube;
}

/* -------------------- SEARCH -------------------- */

app.get('/search', async (req, res) => {
  try {
    const query = req.query.q;
    if (!query) return res.json({ error: 'Query parameter required' });

    const yt = await getYoutube();
    const search = await yt.search(query);

    const videos = search.videos.slice(0, 10);

    const results = [];

    for (const v of videos) {
      try {
        const info = await yt.getInfo(v.id, { client: 'ANDROID' });

        if (!info.streaming_data) continue;

        const audioFmt = info.chooseFormat({ type: 'audio', quality: 'best' });
        const avFmt = info.chooseFormat({ type: 'videoandaudio', quality: 'best' });

        if (!audioFmt || !avFmt) continue;

        const audioUrl = await audioFmt.decipher(yt.session.player);
        const videoUrl = await avFmt.decipher(yt.session.player);

        results.push({
          id: v.id,
          title: v.title.text,
          duration: v.duration.text,
          author: {
            name: v.author.name,
            channel_url: `https://www.youtube.com/channel/${v.author.id}`
          },
          thumbnail: `https://img.youtube.com/vi/${v.id}/hqdefault.jpg`,
          thumbnails: v.thumbnails,
          videoUrl,
          audioUrl
        });

      } catch (e) {
        // skip broken videos
      }
    }

    res.json({
      query,
      count: results.length,
      results
    });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/* -------------------- STREAM (FIXED) -------------------- */

app.get('/stream/:videoId', async (req, res) => {
  try {
    const { videoId } = req.params;
    const type = req.query.type || 'audio';

    const yt = await getYoutube();
    const info = await yt.getInfo(videoId, { client: 'ANDROID' });

    const format = info.chooseFormat({ type, quality: 'best' });
    const url = await format.decipher(yt.session.player);

    const r = await fetch(url);

    res.setHeader('Content-Type', format.mime_type);
    res.setHeader('Cache-Control', 'no-cache');

    r.body.pipe(res);

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* -------------------- ROOT -------------------- */

app.get('/', (_, res) => {
  res.json({
    name: 'Music API',
    endpoints: {
      search: '/search?q=query',
      stream: '/stream/:id?type=audio|videoandaudio'
    }
  });
});

app.listen(PORT, () => console.log('Running on', PORT));
