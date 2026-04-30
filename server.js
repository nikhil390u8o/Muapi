import express from "express";
import { Innertube } from "youtubei.js";

const app = express();
const PORT = process.env.PORT || 8000;

const yt = await Innertube.create();

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });

    // 🔎 Search videos
    const search = await yt.search(q);
    const videos = search.videos.slice(0, 5);

    let results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let audio = null;
      let video = null;

      // ✅ Sirf first video ka stream nikaalo
      if (i === 0) {
        const info = await yt.getInfo(v.id);

        audio = info.streaming_data.adaptive_formats
          .filter(f => f.mime_type.includes("audio"))
          .sort((a, b) => b.bitrate - a.bitrate)[0]?.url || null;

        video = info.streaming_data.formats
          .sort((a, b) => b.bitrate - a.bitrate)[0]?.url || null;
      }

      results.push({
        id: v.id,
        title: v.title,
        thumbnail: v.thumbnails[0]?.url,
        duration: v.duration?.text,
        author: v.author?.name,
        audio,
        video,
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

app.listen(PORT, () => console.log("Server running"));
