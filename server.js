import express from "express";
import yts from "yt-search";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = process.env.PORT || 8000;

// Android client for streams
const yt = await Innertube.create({
  client_type: "ANDROID",
});

// health route
app.get("/", (req, res) => {
  res.send("API running");
});

async function getStreams(id) {
  try {
    const info = await yt.getInfo(id);
    const formats = info.streaming_data?.adaptive_formats || [];

    let audio = null;
    let video = null;

    for (const f of formats) {
      if (!audio && f.mime_type?.includes("audio")) audio = f.url;
      if (!video && f.mime_type?.includes("video")) video = f.url;
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

    // ✅ search via yt-search
    const search = await yts(q);
    const videos = search.videos.slice(0, 5);

    const results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let streams = { audio: null, video: null };

      // only first result ka stream
      if (i === 0) {
        streams = await getStreams(v.videoId);
      }

      results.push({
        id: v.videoId,
        title: v.title,
        thumbnail: v.thumbnail,
        duration: v.timestamp,
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
