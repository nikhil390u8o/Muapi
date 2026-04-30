import express from "express";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = 8000;

// 🔥 IMPORTANT — Android client
const yt = await Innertube.create({
  client_type: "ANDROID",
});

async function getStreams(id) {
  try {
    const info = await yt.getInfo(id);

    const formats = info.streaming_data?.adaptive_formats || [];

    let audio = null;
    let video = null;

    for (const f of formats) {
      if (!audio && f.mime_type?.includes("audio")) {
        audio = f.url;
      }
      if (!video && f.mime_type?.includes("video")) {
        video = f.url;
      }
    }

    return { audio, video };
  } catch {
    return { audio: null, video: null };
  }
}

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });

    const search = await yt.search(q, { type: "video" });
    const videos = search.videos.slice(0, 5);

    const results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let streams = { audio: null, video: null };

      // first id ka stream nikaalo
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

    res.json({ query: q, count: results.length, results });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.listen(PORT, () => console.log("Server running"));
