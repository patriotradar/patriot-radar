/**
 * TikTok Insights Hardening — client-side safety layer + UI.
 * Mirrors tiktok_pipeline_hardening.py for dashboard fail-safe rendering.
 */
(function () {
  "use strict";

  var MOUNT_ID = "tiktokInsightsHardening";
  var QUALITY_THRESHOLD = 0.4;
  var DEFAULT_AGE_HOURS = 168;

  var CURIOSITY_PHRASES = [
    "what is this", "what's this", "wait what", "how do", "how does", "how did",
    "why is", "why does", "why did", "can someone explain", "explain this",
    "i don't understand", "i dont understand", "confused", "what happened"
  ];

  function safeInt(v, d) {
    var n = parseInt(v, 10);
    return isNaN(n) ? (d || 0) : n;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function videoViews(video) {
    var e = video.engagement || {};
    return safeInt(video.play_count || video.playCount || video.views || e.play_count || e.playCount, 0);
  }

  function videoLikes(video) {
    var e = video.engagement || {};
    return safeInt(video.digg_count || video.diggCount || video.likes || e.digg_count || e.diggCount, 0);
  }

  function videoCommentsCount(video) {
    var e = video.engagement || {};
    return Math.max(
      safeInt(video.comment_count || video.commentCount || e.comment_count || e.commentCount, 0),
      (video.comments || []).length
    );
  }

  function videoIdentifier(video) {
    return String(video.video_id || video.id || video.url || video.webVideoUrl || "").trim();
  }

  function computeQualityScore(video) {
    var checks = [
      !!videoIdentifier(video),
      !!String(video.url || video.webVideoUrl || "").trim(),
      !!String(video.caption || video.description || video.text || "").trim(),
      !!String(video.author || "").trim(),
      videoViews(video) > 0 || videoLikes(video) > 0 || videoCommentsCount(video) > 0,
      !!(video.create_time || video.createTime || video.posted_at)
    ];
    var present = 0;
    for (var i = 0; i < checks.length; i++) if (checks[i]) present++;
    return Math.round((present / checks.length) * 1000) / 1000;
  }

  function validateVideos(videos) {
    var accepted = [];
    var rejected = [];
    for (var i = 0; i < (videos || []).length; i++) {
      var video = videos[i];
      if (!video || typeof video !== "object") {
        rejected.push({ video: video, reason: "invalid_type" });
        continue;
      }
      var caption = String(video.caption || video.description || video.text || "").trim();
      var id = videoIdentifier(video);
      var url = String(video.url || video.webVideoUrl || "").trim();
      var views = videoViews(video);
      var likes = videoLikes(video);
      var comments = videoCommentsCount(video);

      if (!id && !url && !caption) {
        rejected.push({ video: video, reason: "missing_identifier_and_url" });
        continue;
      }
      if (views <= 0 && likes <= 0 && comments <= 0 && !caption) {
        rejected.push({ video: video, reason: "no_engagement_metrics" });
        continue;
      }

      var qualityScore = computeQualityScore(video);
      if (caption && !views && !likes && !comments) {
        qualityScore = Math.max(qualityScore, 0.5);
      }
      var enriched = {};
      for (var k in video) enriched[k] = video[k];
      enriched.quality_score = qualityScore;

      if (qualityScore <= QUALITY_THRESHOLD) {
        rejected.push({ video: enriched, reason: "quality_below_threshold", quality_score: qualityScore });
        continue;
      }
      accepted.push(enriched);
    }
    return {
      accepted: accepted,
      rejected: rejected,
      stats: {
        input_count: (videos || []).length,
        accepted_count: accepted.length,
        rejected_count: rejected.length,
        threshold: QUALITY_THRESHOLD
      },
      errors: []
    };
  }

  function parseAgeHours(video) {
    var ts = video.create_time || video.createTime || video.posted_at || video.timestamp;
    if (!ts) return { age_hours: DEFAULT_AGE_HOURS, low_confidence: true };
    try {
      var ms = typeof ts === "string" ? Date.parse(ts) : (ts > 1e12 ? ts : ts * 1000);
      var age = (Date.now() - ms) / 3600000;
      return { age_hours: Math.max(age, 0.01), low_confidence: false };
    } catch (e) {
      return { age_hours: DEFAULT_AGE_HOURS, low_confidence: true };
    }
  }

  function computeTrendScore(video) {
    var views = Math.max(videoViews(video), 0);
    var likes = Math.max(videoLikes(video), 0);
    var comments = Math.max(videoCommentsCount(video), 0);
    var ageInfo = parseAgeHours(video);
    var ageDenom = Math.max(ageInfo.age_hours, 1);
    var viewsDenom = Math.max(views, 1);
    var velocity = Math.round((views / ageDenom) * 10000) / 10000;
    var engagement = Math.round(((likes + comments) / viewsDenom) * 10000) / 10000;
    var freshness = Math.round((1 / ageDenom) * 10000) / 10000;
    return {
      video_id: videoIdentifier(video),
      url: String(video.url || video.webVideoUrl || ""),
      trend_score: Math.round((velocity + engagement + freshness) * 10000) / 10000,
      velocity_score: velocity,
      engagement_score: engagement,
      freshness_score: freshness,
      age_hours: Math.round(ageInfo.age_hours * 100) / 100,
      low_confidence: ageInfo.low_confidence,
      quality_score: video.quality_score || computeQualityScore(video),
      views: views,
      likes: likes,
      comments: comments
    };
  }

  function isEmojiOnly(text) {
    var stripped = String(text || "").trim();
    if (!stripped) return true;
    if (/[a-z0-9]/i.test(stripped)) return false;
    return true;
  }

  function isSpamLike(text) {
    var lowered = String(text || "").toLowerCase().trim();
    var tokens = lowered.split(/\s+/);
    if (tokens.length >= 3) {
      var counts = {};
      for (var i = 0; i < tokens.length; i++) counts[tokens[i]] = (counts[tokens[i]] || 0) + 1;
      var max = 0;
      var keys = Object.keys(counts);
      for (var j = 0; j < keys.length; j++) max = Math.max(max, counts[keys[j]]);
      if (max >= 3 && keys.length <= 2) return true;
    }
    return false;
  }

  function cleanComments(comments) {
    var cleaned = [];
    var seen = {};
    for (var i = 0; i < (comments || []).length; i++) {
      var comment = comments[i] || {};
      var raw = String(comment.comment_text || comment.text || comment.content || "").trim();
      if (raw.length < 3) continue;
      if (isEmojiOnly(raw)) continue;
      if (isSpamLike(raw)) continue;
      var normalized = raw.toLowerCase();
      if (seen[normalized]) continue;
      seen[normalized] = true;
      var out = {};
      for (var k in comment) out[k] = comment[k];
      out.comment_text = normalized;
      out.text = normalized;
      cleaned.push(out);
    }
    return cleaned;
  }

  function confidenceFromCount(count) {
    if (count >= 10) return "high";
    if (count >= 3) return "medium";
    return "low";
  }

  function generateInsights(videos, comments, niche) {
    var insights = [];
    var texts = [];
    for (var i = 0; i < (comments || []).length; i++) {
      var t = String((comments[i].comment_text || comments[i].text || "")).trim();
      if (t) texts.push(t);
    }
    if (!texts.length) return insights;

    var phraseMap = {};
    for (var c = 0; c < texts.length; c++) {
      var tokens = texts[c].toLowerCase().match(/[a-z0-9']+/g) || [];
      for (var n = 2; n <= 3; n++) {
        for (var p = 0; p <= tokens.length - n; p++) {
          var phrase = tokens.slice(p, p + n).join(" ");
          if (phrase.length < 5) continue;
          if (!phraseMap[phrase]) phraseMap[phrase] = { count: 0, examples: [] };
          phraseMap[phrase].count++;
          if (phraseMap[phrase].examples.length < 5) phraseMap[phrase].examples.push(texts[c].slice(0, 160));
        }
      }
    }

    var phrases = Object.keys(phraseMap).sort(function (a, b) {
      return phraseMap[b].count - phraseMap[a].count;
    });

    for (var pi = 0; pi < Math.min(phrases.length, 15); pi++) {
      var key = phrases[pi];
      var data = phraseMap[key];
      if (!data.count) continue;
      var who = niche ? ("people in " + niche) : "viewers";
      var insightText = who + " repeatedly mention \"" + key + "\" in comments";
      insights.push({
        insight: insightText,
        evidence_count: data.count,
        confidence: confidenceFromCount(data.count),
        based_on_examples: data.examples,
        phrase: key,
        video_count: 1
      });
    }

    return insights.filter(function (i) { return i.evidence_count > 0; });
  }

  function validateInsights(insights, comments) {
    var validated = [];
    var texts = (comments || []).map(function (c) {
      return String(c.comment_text || c.text || "").toLowerCase();
    });
    for (var i = 0; i < (insights || []).length; i++) {
      var insight = insights[i];
      var phrase = String(insight.phrase || "").toLowerCase();
      var matches = 0;
      for (var t = 0; t < texts.length; t++) {
        if (phrase && texts[t].indexOf(phrase) !== -1) matches++;
      }
      if (matches >= 3 || (insight.evidence_count || 0) >= 10 || (insight.video_count || 0) >= 2) {
        validated.push(insight);
      }
    }
    return validated;
  }

  function generatePostRecommendations(insights) {
    if (!insights || !insights.length) return { recommended_posts: [] };
    var posts = [];
    var formats = ["talking_head", "voiceover", "listicle", "story", "demo"];
    var hooks = ["curiosity", "pain", "authority", "shock"];
    for (var i = 0; i < Math.min(insights.length, 8); i++) {
      var insight = insights[i];
      posts.push({
        title: "Content idea: " + String(insight.insight || "").slice(0, 60),
        hook: "Your audience keeps saying this — here's what to post about it",
        script_outline: [
          "Hook: Call out the specific pain point from comments",
          "Context: Show real comment examples on screen",
          "Solution: 2-3 actionable steps",
          "CTA: Ask viewers to share their experience"
        ],
        why_it_works: "Grounded in " + (insight.evidence_count || 0) + " comment signals (" + (insight.confidence || "medium") + " confidence)",
        target_pain_point: insight.insight || "",
        format: formats[i % formats.length],
        based_on: [insight.insight || ""].concat((insight.based_on_examples || []).slice(0, 2)),
        hook_type: hooks[i % hooks.length]
      });
    }
    return { recommended_posts: posts };
  }

  function emptyPipelineResponse() {
    return {
      videos: [],
      insights: [],
      recommended_posts: [],
      trend_scores: [],
      errors: [],
      niche: { niche: "unknown", confidence: 0.0, keywords: [] },
      emerging_products: [],
      trending_products: [],
      content_pack: { captions: [], hashtags: [], hook_variations: [] }
    };
  }

  var STOP_WORDS = {
    "the": 1, "and": 1, "for": 1, "are": 1, "but": 1, "not": 1, "you": 1, "all": 1, "can": 1,
    "had": 1, "her": 1, "was": 1, "one": 1, "our": 1, "out": 1, "day": 1, "get": 1, "has": 1,
    "him": 1, "his": 1, "how": 1, "its": 1, "may": 1, "new": 1, "now": 1, "old": 1, "see": 1,
    "two": 1, "way": 1, "who": 1, "that": 1, "this": 1, "with": 1, "have": 1, "from": 1, "they": 1,
    "been": 1, "said": 1, "each": 1, "which": 1, "their": 1, "will": 1, "other": 1, "about": 1,
    "many": 1, "then": 1, "them": 1, "these": 1, "some": 1, "would": 1, "make": 1, "like": 1,
    "into": 1, "time": 1, "very": 1, "when": 1, "come": 1, "here": 1, "just": 1, "what": 1,
    "know": 1, "take": 1, "people": 1, "year": 1, "good": 1, "could": 1, "than": 1, "first": 1,
    "down": 1, "did": 1, "more": 1, "being": 1, "only": 1, "those": 1, "going": 1, "really": 1,
    "still": 1, "even": 1, "your": 1, "there": 1, "where": 1, "why": 1, "back": 1, "much": 1,
    "before": 1, "right": 1, "too": 1, "any": 1, "same": 1, "also": 1, "after": 1, "over": 1,
    "such": 1, "give": 1, "most": 1, "tell": 1, "does": 1, "work": 1, "well": 1, "video": 1,
    "videos": 1, "comment": 1, "comments": 1, "tiktok": 1, "lol": 1, "omg": 1, "yes": 1, "yeah": 1
  };

  var PRODUCT_HINT_WORDS = {
    "serum": 1, "cream": 1, "lotion": 1, "protein": 1, "powder": 1, "brand": 1, "product": 1,
    "bought": 1, "buy": 1, "recommend": 1, "recommended": 1, "amazon": 1, "love": 1, "favorite": 1,
    "dupe": 1, "routine": 1, "spf": 1, "retinol": 1, "collagen": 1, "whey": 1, "vitamin": 1
  };

  function clampVal(v, lo, hi) {
    lo = lo || 0;
    hi = hi || 1;
    return Math.max(lo, Math.min(hi, v));
  }

  function extractProductPhrases(text) {
    var tokens = String(text || "").toLowerCase().match(/[a-z0-9']+/g) || [];
    var filtered = [];
    for (var ti = 0; ti < tokens.length; ti++) {
      if (tokens[ti].length >= 2 && !STOP_WORDS[tokens[ti]]) filtered.push(tokens[ti]);
    }
    var phrases = [];
    for (var n = 2; n <= 3; n++) {
      for (var p = 0; p <= filtered.length - n; p++) {
        var phrase = filtered.slice(p, p + n).join(" ");
        if (phrase.length >= 5) phrases.push(phrase);
      }
    }
    return phrases;
  }

  function generateTrendingProducts(videos, comments, niche, trendScores) {
    try {
      var videosList = videos || [];
      var commentsList = comments || [];
      var scoresList = trendScores || [];
      if (!commentsList.length && !videosList.length) return [];

      var trendByVideo = {};
      for (var si = 0; si < scoresList.length; si++) {
        var ts = scoresList[si];
        var tsVid = String(ts.video_id || "").trim();
        if (tsVid) trendByVideo[tsVid] = ts;
      }

      var videoById = {};
      for (var vi = 0; vi < videosList.length; vi++) {
        var vid = videoIdentifier(videosList[vi]);
        if (vid) videoById[vid] = videosList[vi];
      }
      var totalVideos = Math.max(Object.keys(videoById).length, 1);
      var phraseData = {};

      for (var ci = 0; ci < commentsList.length; ci++) {
        var text = String(commentsList[ci].comment_text || commentsList[ci].text || "").trim().toLowerCase();
        if (!text) continue;
        var cVid = String(commentsList[ci].video_id || "").trim();
        var extracted = extractProductPhrases(text);
        for (var ei = 0; ei < extracted.length; ei++) {
          var phrase = extracted[ei];
          if (!phraseData[phrase]) phraseData[phrase] = { mention_count: 0, video_ids: {}, examples: [] };
          phraseData[phrase].mention_count++;
          if (cVid) phraseData[phrase].video_ids[cVid] = true;
          if (phraseData[phrase].examples.length < 5) phraseData[phrase].examples.push(text.slice(0, 160));
        }
      }

      var phraseKeys = Object.keys(phraseData);
      if (!phraseKeys.length) return [];

      var maxMentions = 1;
      var maxVelocity = 1;
      var maxEngagement = 1;
      for (var pk = 0; pk < phraseKeys.length; pk++) {
        if (phraseData[phraseKeys[pk]].mention_count > maxMentions) maxMentions = phraseData[phraseKeys[pk]].mention_count;
      }
      for (var si2 = 0; si2 < scoresList.length; si2++) {
        var vel = Number(scoresList[si2].velocity_score) || 0;
        if (vel > maxVelocity) maxVelocity = vel;
      }
      var vidKeys = Object.keys(videoById);
      for (var vk = 0; vk < vidKeys.length; vk++) {
        var eng = (videoLikes(videoById[vidKeys[vk]]) + videoCommentsCount(videoById[vidKeys[vk]])) / Math.max(videoViews(videoById[vidKeys[vk]]), 1);
        if (eng > maxEngagement) maxEngagement = eng;
      }
      if (maxVelocity <= 0) maxVelocity = 1;
      if (maxEngagement <= 0) maxEngagement = 1;

      var nicheTokens = {};
      if (niche) {
        var nt = String(niche).toLowerCase().match(/[a-z0-9']+/g) || [];
        for (var ni = 0; ni < nt.length; ni++) nicheTokens[nt[ni]] = true;
      }
      var nicheTokenCount = Object.keys(nicheTokens).length;

      var results = [];
      for (var pi = 0; pi < phraseKeys.length; pi++) {
        var key = phraseKeys[pi];
        var data = phraseData[key];
        var mentionCount = data.mention_count;
        var videoIds = Object.keys(data.video_ids);
        var videoCount = videoIds.length;
        var mentionFreq = mentionCount / maxMentions;
        var videoSpread = videoCount / totalVideos;

        var velSum = 0;
        for (var vli = 0; vli < videoIds.length; vli++) {
          velSum += Number((trendByVideo[videoIds[vli]] || {}).velocity_score) || 0;
        }
        var trendVelocityNorm = (velSum / Math.max(videoIds.length, 1)) / maxVelocity;

        var engSum = 0;
        var engCount = 0;
        for (var eli = 0; eli < videoIds.length; eli++) {
          if (videoById[videoIds[eli]]) {
            engSum += (videoLikes(videoById[videoIds[eli]]) + videoCommentsCount(videoById[videoIds[eli]])) / Math.max(videoViews(videoById[videoIds[eli]]), 1);
            engCount++;
          }
        }
        var engagementNorm = (engSum / Math.max(engCount, 1)) / maxEngagement;

        var phraseParts = key.split(" ");
        var nicheRelevance;
        if (nicheTokenCount) {
          var overlap = 0;
          for (var pt = 0; pt < phraseParts.length; pt++) {
            if (nicheTokens[phraseParts[pt]]) overlap++;
          }
          var hintBonus = 0;
          for (var ph = 0; ph < phraseParts.length; ph++) {
            if (PRODUCT_HINT_WORDS[phraseParts[ph]]) { hintBonus = 0.3; break; }
          }
          nicheRelevance = clampVal(overlap / Math.max(nicheTokenCount, 1) + hintBonus);
        } else {
          nicheRelevance = 0.2;
          for (var ph2 = 0; ph2 < phraseParts.length; ph2++) {
            if (PRODUCT_HINT_WORDS[phraseParts[ph2]]) { nicheRelevance = 0.5; break; }
          }
        }

        var score = clampVal(0.4 * mentionFreq + 0.2 * videoSpread + 0.2 * trendVelocityNorm + 0.1 * engagementNorm + 0.1 * nicheRelevance);
        if (!(mentionCount >= 2 || videoCount >= 2 || score >= 0.6)) continue;

        var confidence = clampVal(0.3 * mentionFreq + 0.3 * videoSpread + 0.2 * trendVelocityNorm + 0.2 * engagementNorm);
        var evidence = data.examples.slice(0, 3);
        if (videoCount >= 2) evidence.push("Mentioned across " + videoCount + " videos");
        if (trendVelocityNorm > 0.7) evidence.push("Associated with high-velocity trending videos");
        if (nicheRelevance > 0.5 && niche) evidence.push("Aligned with niche: " + niche);

        results.push({
          name: key.replace(/\b\w/g, function (c) { return c.toUpperCase(); }),
          mention_count: mentionCount,
          video_count: videoCount,
          trend_velocity: Math.round(trendVelocityNorm * 10000) / 10000,
          niche_relevance: Math.round(nicheRelevance * 10000) / 10000,
          confidence: Math.round(confidence * 10000) / 10000,
          evidence: evidence,
          score: Math.round(score * 10000) / 10000
        });
      }

      results.sort(function (a, b) { return b.score - a.score; });
      return results.slice(0, 20);
    } catch (e) {
      return [];
    }
  }

  function groupRawRowsByVideo(rows) {
    var byVideo = {};
    for (var i = 0; i < (rows || []).length; i++) {
      var row = rows[i] || {};
      var videoId = String(row.video_id || "").trim();
      if (!videoId) continue;
      if (!byVideo[videoId]) {
        byVideo[videoId] = {
          video_id: videoId,
          url: row.video_url || "",
          caption: row.video_caption || "",
          author: row.video_author || "",
          comments: []
        };
      }
      byVideo[videoId].comments.push({
        comment_text: row.comment_text || "",
        comment_like_count: safeInt(row.comment_like_count, 0),
        commented_at: row.commented_at
      });
    }
    var out = [];
    for (var vid in byVideo) out.push(byVideo[vid]);
    return out;
  }

  function runHardenedPipeline(rawRows, niche) {
    try {
      var videos = groupRawRowsByVideo(rawRows);
      var gate = validateVideos(videos);
      var accepted = gate.accepted || [];
      var cleanedVideos = [];
      for (var i = 0; i < accepted.length; i++) {
        var v = accepted[i];
        var copy = {};
        for (var k in v) copy[k] = v[k];
        copy.comments = cleanComments(v.comments || []);
        cleanedVideos.push(copy);
      }
      var flatComments = [];
      for (var vi = 0; vi < cleanedVideos.length; vi++) {
        var cv = cleanedVideos[vi];
        for (var ci = 0; ci < (cv.comments || []).length; ci++) {
          var cc = cv.comments[ci];
          flatComments.push({
            comment_text: cc.comment_text || cc.text || "",
            video_id: cv.video_id
          });
        }
      }
      var rawInsights = generateInsights(cleanedVideos, flatComments, niche);
      var validated = validateInsights(rawInsights, flatComments);
      var trendScores = accepted.map(function (v) { return computeTrendScore(v); });
      var trendingProducts = generateTrendingProducts(cleanedVideos, flatComments, niche, trendScores);
      var recs = generatePostRecommendations(validated);
      return {
        videos: cleanedVideos,
        insights: validated,
        recommended_posts: recs.recommended_posts || [],
        trend_scores: trendScores,
        trending_products: trendingProducts.length ? trendingProducts : [],
        errors: gate.errors || [],
        success: true,
        niche: { niche: niche || "unknown", confidence: 0.0, keywords: [] },
        emerging_products: [],
        content_pack: { captions: [], hashtags: [], hook_variations: [] }
      };
    } catch (err) {
      var resp = emptyPipelineResponse();
      resp.errors = [String(err && err.message ? err.message : err)];
      resp.success = false;
      return resp;
    }
  }

  function renderResults(data) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var insights = data.insights || [];
    var posts = data.recommended_posts || [];
    var scores = data.trend_scores || [];
    var errors = data.errors || [];
    var nicheInfo = data.niche || {};
    var emergingProducts = data.emerging_products || [];
    var trendingProducts = data.trending_products || [];
    var contentPack = data.content_pack || {};

    var h = '<div class="card" style="margin-top:16px">';
    h += '<div class="card-header"><h2>Evidence-Based Insights</h2><div class="section-icon" style="color:var(--amber)">&#9889;</div></div>';

    if (nicheInfo.niche && nicheInfo.niche !== "unknown") {
      h += '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">Account niche: <strong>' + escapeHtml(nicheInfo.niche) + '</strong>';
      if (nicheInfo.confidence) {
        h += ' (' + Math.round((nicheInfo.confidence || 0) * 100) + '% confidence)';
      }
      h += '</p>';
    }

    if (errors.length) {
      h += '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">Pipeline completed with ' + errors.length + ' non-blocking warning(s).</p>';
    }

    if (!insights.length) {
      h += '<p style="font-size:12px;color:var(--muted);line-height:1.6">No evidence-based insights yet. Insights appear when comment signals reach sufficient confidence across multiple comments.</p>';
    } else {
      h += '<div style="display:grid;gap:10px">';
      for (var i = 0; i < Math.min(insights.length, 8); i++) {
        var ins = insights[i];
        h += '<div style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px">';
        h += '<div style="font-size:13px;color:var(--text);margin-bottom:6px">' + escapeHtml(ins.insight) + '</div>';
        h += '<div style="display:flex;gap:8px;flex-wrap:wrap">';
        h += '<span class="tag">' + escapeHtml(ins.confidence || "low") + ' confidence</span>';
        h += '<span class="tag">' + safeInt(ins.evidence_count, 0) + ' signals</span>';
        h += '</div></div>';
      }
      h += '</div>';
    }

    if (posts.length) {
      h += '<div style="margin-top:16px"><h3 style="font-size:14px;margin-bottom:10px;color:var(--green)">Recommended Posts</h3>';
      h += '<div style="display:grid;gap:10px">';
      for (var p = 0; p < Math.min(posts.length, 5); p++) {
        var post = posts[p];
        h += '<div style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px">';
        h += '<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px">' + escapeHtml(post.title) + '</div>';
        h += '<div style="font-size:12px;color:var(--muted);margin-bottom:6px">' + escapeHtml(post.hook) + '</div>';
        h += '<span class="tag">' + escapeHtml(post.format) + '</span> ';
        h += '<span class="tag">' + escapeHtml(post.hook_type) + '</span>';
        h += '</div>';
      }
      h += '</div></div>';
    }

    if (emergingProducts.length > 0) {
      h += '<div style="margin-top:16px"><h3 style="font-size:14px;margin-bottom:10px;color:var(--amber)">Emerging Products</h3>';
      h += '<div style="display:grid;gap:10px">';
      for (var ep = 0; ep < Math.min(emergingProducts.length, 5); ep++) {
        var emerg = emergingProducts[ep];
        h += '<div style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px">';
        h += '<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px">' + escapeHtml(emerg.product || "") + '</div>';
        h += '<span class="tag">' + escapeHtml(emerg.velocity_state || "emerging") + '</span> ';
        h += '<span class="tag">' + Math.round((emerg.signal_strength || 0) * 100) + '% signal</span>';
        h += '</div>';
      }
      h += '</div></div>';
    }

    if (trendingProducts && trendingProducts.length > 0) {
      h += '<div style="margin-top:16px"><h3 style="font-size:14px;margin-bottom:10px;color:var(--amber)">Trending Products</h3>';
      h += '<div style="display:grid;gap:10px">';
      for (var tp = 0; tp < Math.min(trendingProducts.length, 8); tp++) {
        var product = trendingProducts[tp];
        h += '<div style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px">';
        h += '<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px">' + escapeHtml(product.name || product.product || "") + '</div>';
        h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px">';
        h += '<span class="tag">score ' + escapeHtml(String(product.score)) + '</span>';
        h += '<span class="tag">' + safeInt(product.mention_count, 0) + ' mentions</span>';
        h += '<span class="tag">' + safeInt(product.video_count, 0) + ' videos</span>';
        h += '</div>';
        if (product.evidence && product.evidence.length) {
          h += '<div style="font-size:11px;color:var(--muted)">' + escapeHtml(product.evidence[0]) + '</div>';
        }
        h += '</div>';
      }
      h += '</div></div>';
    }

    var captions = contentPack.captions || [];
    if (captions.length > 0) {
      h += '<div style="margin-top:16px"><h3 style="font-size:14px;margin-bottom:10px;color:var(--cyan)">Content Pack</h3>';
      h += '<div style="display:grid;gap:8px">';
      for (var cc = 0; cc < Math.min(captions.length, 4); cc++) {
        h += '<div style="font-size:12px;color:var(--text);background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:10px">' + escapeHtml(captions[cc]) + '</div>';
      }
      var hashtags = contentPack.hashtags || [];
      if (hashtags.length > 0) {
        h += '<p style="font-size:11px;color:var(--muted);margin-top:8px">' + escapeHtml(hashtags.slice(0, 8).join(" ")) + '</p>';
      }
      h += '</div></div>';
    }

    if (scores.length) {
      h += '<p style="font-size:11px;color:var(--muted);margin-top:12px">' + scores.length + ' video(s) scored with trend_score (velocity + engagement + freshness).</p>';
    }

    h += '</div>';
    el.innerHTML = h;
  }

  function refreshTiktokInsightsHardening(rawRows, niche) {
    var data = runHardenedPipeline(rawRows || [], niche || "");
    renderResults(data);
    return data;
  }

  function renderFromLiveState(liveState) {
    var data = {
      videos: (liveState && liveState.videos) || [],
      insights: (liveState && liveState.insights) || [],
      recommended_posts: (liveState && liveState.recommended_posts) || [],
      trend_scores: (liveState && liveState.trend_scores) || [],
      trending_products: (liveState && liveState.trending_products) || [],
      errors: (liveState && liveState.errors) || [],
      success: liveState ? liveState.success !== false : true,
    };
    renderResults(data);
    return data;
  }

  window.TikTokInsightsHardening = {
    validateVideos: validateVideos,
    cleanComments: cleanComments,
    computeTrendScore: computeTrendScore,
    generateInsights: generateInsights,
    validateInsights: validateInsights,
    generatePostRecommendations: generatePostRecommendations,
    generateTrendingProducts: generateTrendingProducts,
    runHardenedPipeline: runHardenedPipeline,
    emptyPipelineResponse: emptyPipelineResponse,
    refresh: refreshTiktokInsightsHardening,
    renderFromLiveState: renderFromLiveState
  };

  function hookNicheRefresh() {
    var original = window.refreshNicheCommentIntelligence;
    if (typeof original !== "function" || original.__hardeningWrapped) return;

    window.refreshNicheCommentIntelligence = async function () {
      try {
        return await original.apply(this, arguments);
      } catch (e) {
        renderResults(emptyPipelineResponse());
      }
    };
    window.refreshNicheCommentIntelligence.__hardeningWrapped = true;
  }

  function init() {
    if (!document.getElementById(MOUNT_ID)) return;
    renderResults(emptyPipelineResponse());
    hookNicheRefresh();
    setTimeout(hookNicheRefresh, 3000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
