import express from "express";
import { Innertube } from 'youtubei.js';
import yts from "yt-search";

const app = express();
const PORT = process.env.PORT || 10000;

// YouTube instance initialize करें
let youtube;
Innertube.create().then((ins) => {
  youtube = ins;
  console.log("✅ YouTube Instance Ready");
});

app.get("/", (req, res) => res.send("API is Live! Use /search?q=query"));

app.get("/search", async (req, res) => {
  try {
    const q = req.query.q;
    if (!q) return res.json({ error: "No query" });
    if (!youtube) return res.json({ error: "YouTube not ready, wait 5s" });

    const search = await yts(q);
    const videos = search.videos.slice(0, 5);
    let results = [];

    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];
      let audio = null;
      let video = null;

      // सिर्फ पहली वीडियो के लिए लिंक्स निकालें
      if (i === 0) {
        try {
          const info = await youtube.getInfo(v.videoId);
          // Best Audio URL
          const audioFormat = info.chooseFormat({ type: 'audio', quality: 'best' });
          audio = audioFormat ? audioFormat.url : null;

          // Best Video URL (with audio)
          const videoFormat = info.chooseFormat({ type: 'video+audio', quality: 'best' });
          video = videoFormat ? videoFormat.url : null;
        } catch (err) {
          console.error("Fetch Error:", err.message);
        }
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

    res.json({ query: q, count: results.length, results });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));
