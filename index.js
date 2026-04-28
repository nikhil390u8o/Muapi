import express from "express";
import ytsr from "ytsr";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = process.env.PORT || 6000;

let yt = null;

// init youtube client
async function getYT() {
  if (!yt) {
    yt = await Innertube.create({
      client_type: "ANDROID",
    });
  }
  return yt;
}

/* ---------------- SEARCH API ---------------- */
app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "query required" });

    const search = await ytsr(q, { limit: 10 });

    const videos = search.items
      .filter(i => i.type === "video")
      .slice(0, 10);

    const results = videos.map(v => ({
      id: v.id,
      title: v.title,
      duration: v.duration || null,
      thumbnail: v.bestThumbnail?.url,
      streamApi: `/stream/${v.id}`
    }));

    res.json({
      query: q,
      count: results.length,
      results
    });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* ---------------- STREAM API (STABLE) ---------------- */
app.get("/stream/:id", async (req, res) => {
  try {
    const yt = await getYT();
    const id = req.params.id;

    const info = await yt.getInfo(id);

    const formats = info.streaming_data?.formats || [];
    const adaptive = info.streaming_data?.adaptive_formats || [];

    // AUDIO (best)
    const audio = adaptive
      .filter(f => f.audio_codec && !f.video_codec)
      .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0))[0];

    // VIDEO (best)
    const video = formats
      .filter(f => f.video_codec && f.audio_codec)
      .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0))[0];

    res.json({
      videoId: id,
      audioUrl: audio?.url || null,
      videoUrl: video?.url || null,
      thumbnails: info.basic_info?.thumbnail || []
    });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* ---------------- ROOT ---------------- */
app.get("/", (req, res) => {
  res.json({
    name: "Stable Music API",
    status: "running",
    endpoints: {
      search: "/search?q=query",
      stream: "/stream/:id"
    }
  });
});

app.listen(PORT, () => {
  console.log("API running on", PORT);
});
