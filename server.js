import express from "express";
import yts from "yt-search";
import ytdlp from "@distube/yt-dlp";

const app = express();
const PORT = process.env.PORT || 8000;

app.get("/", (req, res) => {
  res.send("API running");
});

async function getUrls(id) {
  try {
    const url = `https://www.youtube.com/watch?v=${id}`;

    const audio = await ytdlp(url, {
      format: "bestaudio",
      getUrl: true,
    });

    const video = await ytdlp(url, {
      format: "best",
      getUrl: true,
    });

    return { audio, video };
  } catch {
    return { audio: null, video: null };
  }
}

app.get("/search", async (req, res) => {
  const q = req.query.q;
  if (!q) return res.json({ error: "No query" });

  const search = await yts(q);
  const videos = search.videos.slice(0, 5);

  const results = [];

  for (let i = 0; i < videos.length; i++) {
    const v = videos[i];

    let streams = { audio: null, video: null };

    // first video ke liye urls nikalo
    if (i === 0) {
      streams = await getUrls(v.videoId);
    }

    results.push({
      id: v.videoId,
      title: v.title,
      thumbnail: v.thumbnail,
      duration: v.timestamp,
      author: v.author.name,
      audio: streams.audio,
      video: streams.video,
    });
  }

  res.json({ query: q, count: results.length, results });
});

app.listen(PORT, () => console.log("Server running"));
