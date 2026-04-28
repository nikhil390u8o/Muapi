import express from "express";
import ytsr from "ytsr";
import { exec } from "child_process";

const app = express();
const PORT = process.env.PORT || 6000;

// ─────────────────────────────────────────────
// yt-dlp helper (Render friendly)
// ─────────────────────────────────────────────
function getStreamUrls(id) {
  return new Promise((resolve, reject) => {
    const cmd = `./yt-dlp -j https://www.youtube.com/watch?v=${id}`;

    exec(cmd, { maxBuffer: 1024 * 1024 * 10 }, (err, stdout) => {
      if (err) return reject(err);

      try {
        const data = JSON.parse(stdout);
        const formats = data.formats;

        const audio = formats
          .filter(f => f.acodec !== "none" && f.vcodec === "none")
          .sort((a, b) => (b.abr || 0) - (a.abr || 0))[0];

        const video = formats
          .filter(f => f.vcodec !== "none" && f.acodec === "none")
          .sort((a, b) => (b.height || 0) - (a.height || 0))[0];

        resolve({
          audioUrl: audio?.url || null,
          videoUrl: video?.url || null,
          thumbnails: data.thumbnails || []
        });
      } catch (e) {
        reject(e);
      }
    });
  });
}

// ─────────────────────────────────────────────
// SEARCH API
// ─────────────────────────────────────────────
app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "query required" });

    const search = await ytsr(q, { limit: 10 });
    const videos = search.items
      .filter(i => i.type === "video")
      .slice(0, 10);

    const results = await Promise.all(
      videos.map(async (v) => {
        try {
          const streams = await getStreamUrls(v.id);

          return {
            id: v.id,
            title: v.title,
            duration: v.duration,
            author: {
              name: v.author?.name || "",
              channel_url: v.author?.url || ""
            },
            thumbnail: v.bestThumbnail?.url || "",
            thumbnails: streams.thumbnails,
            videoUrl: streams.videoUrl,
            audioUrl: streams.audioUrl
          };
        } catch {
          return null;
        }
      })
    );

    const clean = results.filter(Boolean);

    res.json({
      query: q,
      count: clean.length,
      results: clean
    });

  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─────────────────────────────────────────────
app.get("/", (req, res) => {
  res.json({ status: "Music API running" });
});

app.listen(PORT, () => console.log("API running on", PORT));
