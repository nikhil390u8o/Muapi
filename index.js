import express from "express";
import ytsr from "ytsr";
import { exec } from "child_process";

const app = express();
const PORT = process.env.PORT || 6000;

// FAST search (no yt-dlp here)
app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    const search = await ytsr(q, { limit: 10 });

    const results = search.items
      .filter(i => i.type === "video")
      .map(v => ({
        id: v.id,
        title: v.title,
        duration: v.duration,
        thumbnail: v.bestThumbnail.url,
        streamApi: `/stream/${v.id}`
      }));

    res.json({ query: q, count: results.length, results });
  } catch (e) {
    res.json({ error: e.message });
  }
});


// STREAM endpoint (yt-dlp used HERE only)
app.get("/stream/:id", (req, res) => {
  const id = req.params.id;

  exec(
    `./yt-dlp -j https://www.youtube.com/watch?v=${id}`,
    { maxBuffer: 1024 * 1024 * 10 },
    (err, stdout) => {
      if (err) {
        return res.json({ error: err.message });
      }

      try {
        const data = JSON.parse(stdout);
        const formats = data.formats;

        const audio = formats
          .filter(f => f.acodec !== "none" && f.vcodec === "none")
          .sort((a, b) => (b.abr || 0) - (a.abr || 0))[0];

        const video = formats
          .filter(f => f.vcodec !== "none" && f.acodec === "none")
          .sort((a, b) => (b.height || 0) - (a.height || 0))[0];

        res.json({
          audioUrl: audio?.url || null,
          videoUrl: video?.url || null,
          thumbnails: data.thumbnails || []
        });

      } catch (e) {
        res.json({ error: "yt-dlp parse error" });
      }
    }
  );
});

app.listen(PORT, () => console.log("API running on", PORT));
