import express from "express";
import yts from "yt-search";
import ytdlp from "yt-dlp-exec";

const app = express();

app.get("/search", async (req, res) => {
  const q = req.query.q;
  if (!q) return res.json({ error: "No query" });

  const r = await yts(q);
  const v = r.videos[0];

  res.json({
    title: v.title,
    videoId: v.videoId,
    url: v.url,
    thumbnail: v.thumbnail,
  });
});

app.get("/stream", async (req, res) => {
  const q = req.query.query;
  if (!q) return res.json({ error: "No query" });

  try {
    const r = await yts(q);
    const url = r.videos[0].url;

    const out = await ytdlp(url, {
      dumpSingleJson: true,
      noWarnings: true,
      preferFreeFormats: true,
      addHeader: ["referer:youtube.com", "user-agent:googlebot"],
    });

    const audio = out.formats.find(f => f.acodec !== "none" && f.vcodec === "none");

    res.json({
      title: out.title,
      audio_url: audio.url,
      thumbnail: out.thumbnail,
    });
  } catch (e) {
    res.json({ error: e.toString() });
  }
});

app.listen(3000, () => console.log("API running"));
