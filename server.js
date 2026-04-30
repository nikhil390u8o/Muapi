import express from "express";
import { spawn } from "child_process";
import yts from "yt-search";

const app = express();
const PORT = process.env.PORT || 8000;

function getYtUrl(format, id) {
  return new Promise((resolve) => {
    const ytdlp = spawn("yt-dlp", [
      "-f",
      format,
      "-g",
      `https://www.youtube.com/watch?v=${id}`,
    ]);

    let data = "";

    ytdlp.stdout.on("data", (chunk) => {
      data += chunk.toString();
    });

    ytdlp.on("close", () => {
      resolve(data.trim() || null);
    });

    ytdlp.on("error", () => resolve(null));
  });
}

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });

    const search = await yts(q);
    const videos = search.videos.slice(0, 5);

    const results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];

      let audio = null;
      let video = null;

      // sirf first video ke liye stream nikalo (fast response)
      if (i === 0) {
        audio = await getYtUrl("bestaudio", v.videoId);
        video = await getYtUrl("best", v.videoId);
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
