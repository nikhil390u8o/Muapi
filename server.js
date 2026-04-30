import express from "express";
import { execSync } from "child_process";
import yts from "yt-search";

const app = express();
const PORT = 7000;

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });

    const search = await yts(q);
    const videos = search.videos.slice(0, 5);

    let results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let audio = null;
      let video = null;

      // 🔥 sirf first video ka stream nikalo
      if (i === 0) {
        try {
          audio = execSync(
            `yt-dlp -f bestaudio -g https://www.youtube.com/watch?v=${v.videoId}`
          ).toString().trim();

          video = execSync(
            `yt-dlp -f best -g https://www.youtube.com/watch?v=${v.videoId}`
          ).toString().trim();
        } catch {}
      }

      results.push({
        id: v.videoId,
        title: v.title,
        thumbnail: v.thumbnail,
        duration: v.timestamp,
        author: v.author.name,
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

app.listen(PORT, () =>
  console.log(`Server running on port ${PORT}`)
);
