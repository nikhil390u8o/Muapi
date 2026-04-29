import express from "express";
import ytsr from "ytsr";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = process.env.PORT || 3000;

let yt;

async function getYT() {
  if (!yt) {
    yt = await Innertube.create({
      client_type: "ANDROID"
    });
  }
  return yt;
}

/* ───────── SEARCH API (FAST + STABLE) ───────── */
app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.status(400).json({ error: "query required" });

    const search = await ytsr(q, { limit: 10 });

    const results = search.items
      .filter(v => v.type === "video")
      .slice(0, 10)
      .map(v => ({
        id: v.id,
        title: v.title,
        duration: v.duration || null,
        thumbnail: v.bestThumbnail?.url || "",
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

/* ───────── STREAM API (NO YT-DLP, NO COOKIES) ───────── */
app.get("/stream/:id", async (req, res) => {
  try {
    const id = req.params.id;

    const yt = await getYT();
    const info = await yt.getInfo(id);

    const formats = info.streaming_data?.adaptive_formats || [];

    // AUDIO BEST
    const audio = formats
      .filter(f => f.mime_type?.includes("audio"))
      .sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0))[0];

    // VIDEO BEST
    const video = formats
      .filter(f => f.mime_type?.includes("video"))
      .sort((a, b) => (b.height || 0) - (a.height || 0))[0];

    if (!audio && !video) {
      return res.status(500).json({ error: "stream not available" });
    }

    res.json({
      query: id,
      count: 1,
      results: [
        {
          id,
          title: info.basic_info?.title || "",
          duration: info.basic_info?.duration || "",
          author: {
            name: info.basic_info?.author || "",
            channel_url: ""
          },
          thumbnail: `https://i.ytimg.com/vi/${id}/hq720.jpg`,
          audio_url: audio?.url || null,
          video_url: video?.url || null
        }
      ]
    });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* ───────── HOME ───────── */
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
  console.log("Server running on port", PORT);
});
