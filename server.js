import express from "express";
import { execSync } from "child_process";
import yts from "yt-search";
import fs from "fs";

const app = express();
const PORT = process.env.PORT || 7000;

// 🔥 SECURITY: Environment variable se cookies.txt create karna
// Render dashboard me 'COOKIES_CONTENT' नाम का variable बनायें और अपनी कुकीज़ वहां पेस्ट करें
if (process.env.COOKIES_CONTENT) {
  try {
    fs.writeFileSync("./cookies.txt", process.env.COOKIES_CONTENT);
    console.log("✅ cookies.txt has been generated from Env Var.");
  } catch (err) {
    console.error("❌ Failed to create cookies file:", err);
  }
}

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

      // सिर्फ पहली वीडियो का लिंक निकालें
      if (i === 0) {
        try {
          // Check if cookies file exists to use it
          const cookieFlag = fs.existsSync("./cookies.txt") ? "--cookies ./cookies.txt" : "";

          audio = execSync(
            `yt-dlp ${cookieFlag} -f bestaudio -g "https://youtube.com{v.videoId}"`
          ).toString().trim();

          video = execSync(
            `yt-dlp ${cookieFlag} -f best -g "https://youtube.com{v.videoId}"`
          ).toString().trim();
        } catch (err) {
          console.error(`Error fetching links for ${v.videoId}:`, err.message);
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

    res.json({
      query: q,
      count: results.length,
      results,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () =>
  console.log(`🚀 Server running on port ${PORT}`)
);
