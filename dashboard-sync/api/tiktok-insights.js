/**
 * Hardened TikTok insights API — always returns the output safety contract.
 * POST /api/tiktok-insights  { niche?: string, videos?: object[], account_id?: string }
 */

const { emptyLiveState, buildLiveState } = require("./tiktok-live-dashboard-state");

const QUALITY_THRESHOLD = 0.4;
const DEFAULT_AGE_HOURS = 168;

function safeInt(v, d = 0) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : d;
}

function emptyResponse() {
  return {
    videos: [],
    insights: [],
    recommended_posts: [],
    trend_scores: [],
    errors: [],
    niche: { niche: "unknown", confidence: 0.0, keywords: [] },
    emerging_products: [],
    trending_products: [],
    content_pack: { captions: [], hashtags: [], hook_variations: [] },
    live_state: emptyLiveState(),
  };
}

function videoViews(video) {
  const e = video.engagement || {};
  return safeInt(video.play_count ?? video.playCount ?? video.views ?? e.play_count ?? e.playCount);
}

function videoLikes(video) {
  const e = video.engagement || {};
  return safeInt(video.digg_count ?? video.diggCount ?? video.likes ?? e.digg_count ?? e.diggCount);
}

function videoCommentsCount(video) {
  const e = video.engagement || {};
  return Math.max(
    safeInt(video.comment_count ?? video.commentCount ?? e.comment_count ?? e.commentCount),
    (video.comments || []).length
  );
}

function videoIdentifier(video) {
  return String(video.video_id || video.id || video.url || video.webVideoUrl || "").trim();
}

function computeQualityScore(video) {
  const checks = [
    !!videoIdentifier(video),
    !!String(video.url || video.webVideoUrl || "").trim(),
    !!String(video.caption || video.description || video.text || "").trim(),
    !!String(video.author || "").trim(),
    videoViews(video) > 0 || videoLikes(video) > 0 || videoCommentsCount(video) > 0,
    !!(video.create_time || video.createTime || video.posted_at),
  ];
  const present = checks.filter(Boolean).length;
  return Math.round((present / checks.length) * 1000) / 1000;
}

function validateVideos(videos) {
  const accepted = [];
  const rejected = [];
  for (const video of videos || []) {
    if (!video || typeof video !== "object") {
      rejected.push({ video, reason: "invalid_type" });
      continue;
    }
    const caption = String(video.caption || video.description || video.text || "").trim();
    const id = videoIdentifier(video);
    const url = String(video.url || video.webVideoUrl || "").trim();
    const views = videoViews(video);
    const likes = videoLikes(video);
    const comments = videoCommentsCount(video);

    if (!id && !url && !caption) {
      rejected.push({ video, reason: "missing_identifier_and_url" });
      continue;
    }
    if (views <= 0 && likes <= 0 && comments <= 0 && !caption) {
      rejected.push({ video, reason: "no_engagement_metrics" });
      continue;
    }

    let qualityScore = computeQualityScore(video);
    if (caption && !views && !likes && !comments) qualityScore = Math.max(qualityScore, 0.5);
    const enriched = { ...video, quality_score: qualityScore };
    if (qualityScore <= QUALITY_THRESHOLD) {
      rejected.push({ video: enriched, reason: "quality_below_threshold", quality_score: qualityScore });
      continue;
    }
    accepted.push(enriched);
  }
  return { accepted, rejected };
}

function parseAgeHours(video) {
  const ts = video.create_time || video.createTime || video.posted_at || video.timestamp;
  if (!ts) return { age_hours: DEFAULT_AGE_HOURS, low_confidence: true };
  try {
    const ms = typeof ts === "string" ? Date.parse(ts) : (ts > 1e12 ? ts : ts * 1000);
    return { age_hours: Math.max((Date.now() - ms) / 3600000, 0.01), low_confidence: false };
  } catch {
    return { age_hours: DEFAULT_AGE_HOURS, low_confidence: true };
  }
}

function computeTrendScore(video) {
  const views = Math.max(videoViews(video), 0);
  const likes = Math.max(videoLikes(video), 0);
  const comments = Math.max(videoCommentsCount(video), 0);
  const { age_hours, low_confidence } = parseAgeHours(video);
  const ageDenom = Math.max(age_hours, 1);
  const viewsDenom = Math.max(views, 1);
  const velocity_score = Math.round((views / ageDenom) * 10000) / 10000;
  const engagement_score = Math.round(((likes + comments) / viewsDenom) * 10000) / 10000;
  const freshness_score = Math.round((1 / ageDenom) * 10000) / 10000;
  return {
    video_id: videoIdentifier(video),
    url: String(video.url || video.webVideoUrl || ""),
    trend_score: Math.round((velocity_score + engagement_score + freshness_score) * 10000) / 10000,
    velocity_score,
    engagement_score,
    freshness_score,
    age_hours: Math.round(age_hours * 100) / 100,
    low_confidence,
    quality_score: video.quality_score || computeQualityScore(video),
    views,
    likes,
    comments,
  };
}

function isEmojiOnly(text) {
  const stripped = String(text || "").trim();
  if (!stripped) return true;
  return !/[a-z0-9]/i.test(stripped);
}

function isSpamLike(text) {
  const tokens = String(text || "").toLowerCase().trim().split(/\s+/);
  if (tokens.length < 3) return false;
  const counts = {};
  for (const t of tokens) counts[t] = (counts[t] || 0) + 1;
  const max = Math.max(...Object.values(counts));
  return max >= 3 && Object.keys(counts).length <= 2;
}

function cleanComments(comments) {
  const cleaned = [];
  const seen = new Set();
  for (const comment of comments || []) {
    const raw = String(comment.comment_text || comment.text || comment.content || "").trim();
    if (raw.length < 3 || isEmojiOnly(raw) || isSpamLike(raw)) continue;
    const normalized = raw.toLowerCase();
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    cleaned.push({ ...comment, comment_text: normalized, text: normalized });
  }
  return cleaned;
}

function confidenceFromCount(count) {
  if (count >= 10) return "high";
  if (count >= 3) return "medium";
  return "low";
}

function generateInsights(videos, comments, niche) {
  const insights = [];
  const texts = (comments || [])
    .map((c) => String(c.comment_text || c.text || "").trim())
    .filter(Boolean);
  if (!texts.length) return insights;

  const phraseMap = {};
  for (const text of texts) {
    const tokens = text.toLowerCase().match(/[a-z0-9']+/g) || [];
    for (let n = 2; n <= 3; n++) {
      for (let p = 0; p <= tokens.length - n; p++) {
        const phrase = tokens.slice(p, p + n).join(" ");
        if (phrase.length < 5) continue;
        if (!phraseMap[phrase]) phraseMap[phrase] = { count: 0, examples: [] };
        phraseMap[phrase].count++;
        if (phraseMap[phrase].examples.length < 5) phraseMap[phrase].examples.push(text.slice(0, 160));
      }
    }
  }

  const phrases = Object.keys(phraseMap).sort((a, b) => phraseMap[b].count - phraseMap[a].count);
  for (const key of phrases.slice(0, 15)) {
    const data = phraseMap[key];
    if (!data.count) continue;
    const who = niche ? `people in ${niche}` : "viewers";
    insights.push({
      insight: `${who} repeatedly mention "${key}" in comments`,
      evidence_count: data.count,
      confidence: confidenceFromCount(data.count),
      based_on_examples: data.examples,
      phrase: key,
      video_count: 1,
    });
  }
  return insights.filter((i) => i.evidence_count > 0);
}

function validateInsights(insights, comments) {
  const texts = (comments || []).map((c) => String(c.comment_text || c.text || "").toLowerCase());
  return (insights || []).filter((insight) => {
    const phrase = String(insight.phrase || "").toLowerCase();
    const matches = texts.filter((t) => phrase && t.includes(phrase)).length;
    return matches >= 3 || (insight.evidence_count || 0) >= 10 || (insight.video_count || 0) >= 2;
  });
}

function generatePostRecommendations(insights) {
  if (!insights || !insights.length) return { recommended_posts: [] };
  const formats = ["talking_head", "voiceover", "listicle", "story", "demo"];
  const hooks = ["curiosity", "pain", "authority", "shock"];
  const recommended_posts = insights.slice(0, 8).map((insight, i) => ({
    title: `Content idea: ${String(insight.insight || "").slice(0, 60)}`,
    hook: "Your audience keeps saying this — here's what to post about it",
    script_outline: [
      "Hook: Call out the specific pain point from comments",
      "Context: Show real comment examples on screen",
      "Solution: 2-3 actionable steps",
      "CTA: Ask viewers to share their experience",
    ],
    why_it_works: `Grounded in ${insight.evidence_count || 0} comment signals (${insight.confidence || "medium"} confidence)`,
    target_pain_point: insight.insight || "",
    format: formats[i % formats.length],
    based_on: [insight.insight || "", ...(insight.based_on_examples || []).slice(0, 2)],
    hook_type: hooks[i % hooks.length],
  }));
  return { recommended_posts };
}

function runPipeline(videos, niche) {
  const gate = validateVideos(videos);
  const accepted = gate.accepted || [];
  const cleanedVideos = accepted.map((v) => ({ ...v, comments: cleanComments(v.comments || []) }));
  const flatComments = cleanedVideos.flatMap((v) =>
    (v.comments || []).map((c) => ({ ...c, video_id: v.video_id }))
  );
  const rawInsights = generateInsights(cleanedVideos, flatComments, niche);
  const validated = validateInsights(rawInsights, flatComments);
  const recs = generatePostRecommendations(validated);
  return {
    videos: cleanedVideos,
    insights: validated,
    recommended_posts: recs.recommended_posts || [],
    trend_scores: accepted.map(computeTrendScore),
    errors: [],
    success: true,
    niche: { niche: niche || "unknown", confidence: 0.0, keywords: [] },
    emerging_products: [],
    trending_products: [],
    content_pack: { captions: [], hashtags: [], hook_variations: [] },
  };
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");

  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(204).end();
  }

  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ ...emptyResponse(), errors: ["method_not_allowed"] });
  }

  try {
    const body = req.method === "POST" ? (req.body || {}) : {};
    const niche = String(body.niche || req.query?.niche || "").trim();
    const accountId = String(body.account_id || req.query?.account_id || "").trim();
    const videos = Array.isArray(body.videos) ? body.videos : [];

    if (!videos.length) {
      const liveState = accountId
        ? await buildLiveState(accountId, {})
        : emptyLiveState();
      return res.status(200).json({
        ...emptyResponse(),
        live_state: liveState,
        success: true,
        message: "no_videos_provided",
      });
    }

    const result = runPipeline(videos, niche);
    const derivedAccount =
      accountId ||
      String((result.videos || []).find((v) => v.author)?.author || "").trim();
    result.live_state = derivedAccount
      ? await buildLiveState(derivedAccount, {})
      : emptyLiveState();
    return res.status(200).json(result);
  } catch (err) {
    return res.status(200).json({ ...emptyResponse(), errors: [String(err?.message || err)], success: false });
  }
};
