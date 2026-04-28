import express from "express";
import ytsr from "ytsr";
import { exec } from "child_process";

const app = express();
const PORT = process.env.PORT || 6000;

// yt-dlp command helper
function getStreamUrls(id) {
  return new Promise((resolve, reject) => {
    const cmd = `yt-dlp -j https://www.youtube.com/watch?v=${id}`;
    exec(cmd, (err, stdout) => {
      if (err) return reject(err);

      const data = JSON.parse(stdout);

      // best video + best audio
      const formats = data.formats;

      const audio = formats.find(f => f.acodec !== "none" && f.vcodec === "none");
      const video = formats.find(f => f.vcodec !== "none" && f.acodec !== "none");

      resolve({
        audioUrl: audio?.url || null,
        videoUrl: video?.url || null,
        thumbnails: data.thumbnails || []
      });
    });
  });
}

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "query required" });

    const search = await ytsr(q, { limit: 10 });

    const videos = search.items.filter(i => i.type === "video").slice(0, 10);

    const results = [];

    for (const v of videos) {
      const streams = await getStreamUrls(v.id);

      results.push({
        id: v.id,
        title: v.title,
        duration: v.duration,
        author: {
          name: v.author.name,
          channel_url: v.author.url
        },
        thumbnail: v.bestThumbnail.url,
        thumbnails: streams.thumbnails,
        videoUrl: streams.videoUrl,
        audioUrl: streams.audioUrl
      });
    }

    res.json({
      query: q,
      count: results.length,
      results
    });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => console.log("API running on", PORT));
