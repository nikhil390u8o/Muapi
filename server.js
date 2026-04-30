import express from "express";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = 8000;

const yt = await Innertube.create();

async function getStreams(id) {
  try {
    const info = await yt.getInfo(id);

    const audioFormat = info.chooseFormat({
      type: "audio",
      quality: "best",
      format: "any",
    });

    const videoFormat = info.chooseFormat({
      type: "video",
      quality: "best",
      format: "any",
    });

    return {
      audio: audioFormat?.url || null,
      video: videoFormat?.url || null,
    };
  } catch (e) {
    return { audio: null, video: null };
  }
}

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });

    const search = await yt.search(q, { type: "video" });
    const videos = search.videos.slice(0, 5);

    let results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let streams = { audio: null, video: null };

      // sirf first video ka stream nikaalna fast response ke liye
      if (i === 0) {
        streams = await getStreams(v.id);
      }

      results.push({
        id: v.id,
        title: v.title.text,
        thumbnail: v.thumbnails[0].url,
        duration: v.duration.text,
        author: v.author.name,
        audio: streams.audio,
        video: streams.video,
      });
    }

    res.json({
      query: q,
      count: results.length,
      results,
    });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.listen(PORT, () =>
  console.log(`Server running on port ${PORT}`)
);
