import express from "express";
import yts from "yt-search";
import { spawn } from "child_process";

const app = express();
const PORT = process.env.PORT || 8000;

// ---------- yt-dlp helper ----------
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

// ---------- SEARCH ----------
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

      // sirf first video ka stream nikalo
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

// ---------- DIRECT STREAM ----------
app.get("/stream/:id", async (req, res) => {
  try {
    const { id } = req.params;
    const type = req.query.type || "audio";

    const format = type === "video" ? "best" : "bestaudio";
    const url = await getYtUrl(format, id);

    res.json({ id, type, url });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.get("/", (req, res) => {
  res.send("YT Music API Running");
});

app.listen(PORT, () =>
  console.log(`Server running on port ${PORT}`)
);
