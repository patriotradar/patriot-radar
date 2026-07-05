const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(__dirname, "..", "data");

const CATEGORY_MAP = {
  "t-shirt": "apparel",
  hoodie: "apparel",
  cap: "apparel",
  mug: "drinkware",
  flask: "drinkware",
  glass: "drinkware",
  flag: "flags and banners",
  banner: "flags and banners",
  book: "books and history guides",
  guide: "books and history guides",
  sticker: "stickers and patches",
  patch: "stickers and patches",
  poster: "home decor",
  decor: "home decor",
  digital: "digital products",
};

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function loadOptionalJson(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      return loadJson(filePath);
    }
  } catch {
    // ignore optional signal files
  }
  return null;
}

function pickViralPattern(productCategory, patterns) {
  const canonical =
    CATEGORY_MAP[productCategory.toLowerCase()] || productCategory.toLowerCase();
  for (const pattern of patterns) {
    if ((pattern.best_for || []).includes(canonical)) {
      return pattern;
    }
  }
  return patterns[0];
}

function buildGeminiPrompt(product, topic, audience, pattern, recentTrends, recentBuyerQuestions) {
  const trendText = recentTrends.length
    ? "\n - " + recentTrends.slice(0, 8).join("\n - ")
    : "";
  const questionText = recentBuyerQuestions.length
    ? "\n - " + recentBuyerQuestions.slice(0, 6).join("\n - ")
    : "";

  return `You are a TikTok content strategist for a British patriotic audience.

AUDIENCE PROFILE:
- Primary: ${audience.demographics.female_pct}% female, ${audience.demographics.male_pct}% male
- Age: ${audience.demographics.age_55_plus}% are 55+
- Location: ${audience.demographics.location}
- Best posting time: ${audience.active_times.best_day}, ${audience.active_times.best_hours}
- Content triggers: ${audience.content_triggers.join(", ")}

VIRAL FORMAT TO USE: ${pattern.name}
Format description: ${pattern.description}
Recommended duration: ${pattern.duration_seconds} seconds
Elements to include: ${pattern.elements.join(", ")}

CURRENT TRENDING CONTEXT:${trendText}

BUYER QUESTIONS PEOPLE ARE ASKING:${questionText}

TASK:
Create a complete TikTok post for this product/topic: **${product}**
Angle or theme: **${topic}**

Return ONLY raw JSON in this exact structure (no markdown, no code fences, no commentary):

{
  "hook": "first 3 seconds text overlay/voiceover hook",
  "caption": "full TikTok caption under 300 characters, with emotional CTA",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "imagePrompt": "detailed image generation prompt for Gemini to create the main visual. British, patriotic, suitable for 55+ audience. No text in image.",
  "animationPrompt": "short follow-up prompt to paste back into Gemini: 'Animate this image: [describe motion, camera, mood]'. Keep subtle and emotional.",
  "voiceover": "words the creator should speak or use TikTok text-to-speech. Under 40 words. Slow, clear.",
  "stockSearchTerms": ["term1", "term2", "term3"],
  "postingTime": "Saturday 12am-1am UK time",
  "videoDurationSeconds": ${pattern.duration_seconds},
  "whyItWorks": "one sentence explaining why this post should work for this audience"
}`;
}

async function callGemini(prompt, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.85,
        maxOutputTokens: 1200,
        responseMimeType: "text/plain",
      },
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(
      `Gemini API error: ${response.status} ${JSON.stringify(data).slice(0, 300)}`
    );
  }

  const candidates = data.candidates || [];
  if (!candidates.length) {
    throw new Error("Gemini returned no candidates");
  }

  const text = candidates[0]?.content?.parts?.[0]?.text || "";
  if (!text) {
    throw new Error("Gemini returned empty text");
  }
  return text;
}

function cleanJson(text) {
  let cleaned = text.trim();
  if (cleaned.startsWith("```")) {
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "").trim();
  }
  try {
    return JSON.parse(cleaned);
  } catch (err) {
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start !== -1 && end !== -1 && end > start) {
      return JSON.parse(cleaned.slice(start, end + 1));
    }
    throw new Error(`Could not parse Gemini output as JSON: ${err.message}`);
  }
}

function parseBody(req) {
  let body = req.body;
  if (typeof body === "string") {
    body = JSON.parse(body);
  }
  return body || {};
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: "GEMINI_API_KEY is not configured" });
  }

  let body;
  try {
    body = parseBody(req);
  } catch {
    return res.status(400).json({ error: "Invalid JSON body" });
  }

  const product = String(body.product || "").trim();
  const topic = String(body.topic || "").trim();
  if (!product || !topic) {
    return res.status(400).json({ error: "product and topic are required" });
  }

  try {
    const audience = loadJson(path.join(DATA_DIR, "audience_profile.json"));
    const patterns = loadJson(path.join(DATA_DIR, "viral_pattern_library.json"));

    const feed = loadOptionalJson(path.join(DATA_DIR, "trend_intelligence_feed_latest.json"));
    const buyer = loadOptionalJson(path.join(DATA_DIR, "buyer_intent_signals_latest.json"));
    const recentTrends =
      feed && typeof feed === "object" && Array.isArray(feed.trends)
        ? feed.trends.slice(0, 10).map(String)
        : [];
    const recentBuyerQuestions =
      buyer && typeof buyer === "object" && Array.isArray(buyer.questions)
        ? buyer.questions.slice(0, 8).map(String)
        : [];

    const pattern = pickViralPattern(product, patterns);
    const prompt = buildGeminiPrompt(
      product,
      topic,
      audience,
      pattern,
      recentTrends,
      recentBuyerQuestions
    );
    const raw = await callGemini(prompt, apiKey);
    const result = cleanJson(raw);

    result.product = product;
    result.topic = topic;
    result.pattern = pattern.name;

    return res.status(200).json(result);
  } catch (err) {
    console.error("generate-post error:", err);
    return res.status(502).json({ error: err.message || "Failed to generate post" });
  }
};
