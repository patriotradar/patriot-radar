/**
 * Early Virality Prediction Engine — isolated dashboard section.
 * Multi-signal trend detection from niche_comment_raw at query time.
 * Does not modify existing TikTok trend pipeline or Niche Comment Intelligence UI.
 */
(function () {
  "use strict";

  var MOUNT_ID = "nicheCommentViralityPrediction";
  var TABLE = "niche_comment_raw";
  var RAW_LIMIT = 3000;
  var DEBOUNCE_MS = 350;

  var rawCache = [];
  var currentNiche = "";
  var debounceTimer = null;
  var initialized = false;

  var CURIOSITY_PHRASES = [
    "what is this", "what's this", "wait what", "how do", "how does", "how did",
    "why is", "why does", "why did", "can someone explain", "explain this",
    "i don't understand", "i dont understand", "confused", "what happened",
    "who is", "where is", "is this real", "am i missing"
  ];

  var CONTROVERSY_PHRASES = [
    "this is fake", "its fake", "it's fake", "no way", "this doesn't work",
    "doesnt work", "doesn't work", "cap", "that's cap", "thats cap",
    "not real", "scam", "clickbait", "misleading", "wrong", "that's wrong",
    "thats wrong", "disagree", "stop lying", "liar", "bull", "bs",
    "skeptical", "doubt", "doesn't make sense", "doesnt make sense", "fake news"
  ];

  var NICHE_SYNONYMS = {
    fitness: ["workout", "gym", "exercise", "training", "muscle", "cardio", "lift"],
    skincare: ["skin", "acne", "serum", "moisturizer", "routine", "glow", "derma"],
    crypto: ["bitcoin", "btc", "ethereum", "eth", "blockchain", "token", "web3"],
    finance: ["money", "budget", "saving", "invest", "wealth", "income", "debt"],
    cooking: ["recipe", "food", "meal", "kitchen", "bake", "chef", "cook"],
    beauty: ["makeup", "glam", "cosmetic", "lipstick", "foundation", "mua"],
    gaming: ["game", "gamer", "playstation", "xbox", "nintendo", "stream"],
    fashion: ["style", "outfit", "clothing", "wear", "streetwear", "ootd"],
    health: ["wellness", "nutrition", "diet", "mental", "medical", "doctor"],
    tech: ["technology", "gadget", "software", "app", "ai", "device"],
    parenting: ["parent", "baby", "kids", "child", "mom", "dad", "toddler"],
    travel: ["trip", "vacation", "destination", "flight", "hotel", "explore"],
    education: ["learn", "study", "school", "teacher", "student", "course"],
    motivation: ["mindset", "discipline", "habits", "goals", "success", "grind"],
    pets: ["dog", "cat", "puppy", "kitten", "pet", "animal"],
    music: ["song", "artist", "beat", "album", "producer", "rap"],
    business: ["entrepreneur", "startup", "brand", "marketing", "sales", "client"],
    patriotic: ["patriot", "patriotism", "british", "britain", "uk", "england", "pride"],
    history: ["heritage", "historical", "past", "ancient", "war", "culture"]
  };

  var STOPWORDS = {
    a: 1, an: 1, the: 1, and: 1, or: 1, but: 1, in: 1, on: 1, at: 1, to: 1,
    for: 1, of: 1, is: 1, it: 1, this: 1, that: 1, with: 1, as: 1, be: 1,
    are: 1, was: 1, were: 1, i: 1, you: 1, he: 1, she: 1, they: 1, we: 1,
    my: 1, your: 1, so: 1
  };

  var GENERIC_NOISE = {
    nice: 1, cool: 1, lol: 1, lmao: 1, haha: 1, wow: 1, omg: 1, yes: 1, no: 1,
    ok: 1, okay: 1, true: 1, same: 1, fr: 1, real: 1, fire: 1, slay: 1, yep: 1,
    nope: 1, yeah: 1, nah: 1, first: 1, early: 1, following: 1, follow: 1,
    part: 1, pov: 1, fyp: 1, foryou: 1, foryoupage: 1
  };

  var WEIGHTS = {
    velocity: 0.25,
    acceleration: 0.20,
    cross_video: 0.20,
    niche_relevance: 0.20,
    curiosity: 0.15
  };

  var MIN_COMMENTS = 3;
  var MIN_RELEVANCE = 15;
  var MIN_COMMENT_LEN = 4;

  function getClient() {
    if (typeof supabaseClient !== "undefined" && supabaseClient) return supabaseClient;
    return null;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tokenize(text) {
    var matches = String(text || "").toLowerCase().match(/[a-z0-9']+/g) || [];
    var out = [];
    for (var i = 0; i < matches.length; i++) {
      if (!STOPWORDS[matches[i]] && matches[i].length > 1) out.push(matches[i]);
    }
    return out;
  }

  function buildNicheKeywords(niche) {
    var nicheClean = String(niche || "").trim().toLowerCase();
    if (!nicheClean) return [];

    var keywords = [nicheClean];
    var tokens = tokenize(nicheClean);
    for (var i = 0; i < tokens.length; i++) keywords.push(tokens[i]);

    var synonyms = NICHE_SYNONYMS[nicheClean] || [];
    for (var j = 0; j < synonyms.length; j++) keywords.push(synonyms[j]);

    var keys = Object.keys(NICHE_SYNONYMS);
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k];
      var values = NICHE_SYNONYMS[key];
      var matched = false;
      for (var v = 0; v < values.length; v++) {
        if (nicheClean.indexOf(values[v]) !== -1) matched = true;
      }
      if (matched || values.indexOf(nicheClean) !== -1) {
        keywords.push(key);
        for (var s = 0; s < values.length; s++) keywords.push(values[s]);
      }
    }

    var seen = {};
    var unique = [];
    for (var u = 0; u < keywords.length; u++) {
      if (keywords[u] && !seen[keywords[u]]) {
        seen[keywords[u]] = true;
        unique.push(keywords[u]);
      }
    }
    return unique;
  }

  function ngrams(tokens, n) {
    if (tokens.length < n) return [];
    var grams = [];
    for (var i = 0; i <= tokens.length - n; i++) {
      grams.push(tokens.slice(i, i + n).join(" "));
    }
    return grams;
  }

  function parseTimestamp(comment) {
    var ts = comment.commented_at;
    if (!ts) return null;
    try {
      return new Date(ts).getTime() / 1000;
    } catch (e) {
      return null;
    }
  }

  function filterSignalComments(comments) {
    var filtered = [];
    for (var i = 0; i < comments.length; i++) {
      var text = (comments[i].comment_text || "").trim();
      if (text.length < MIN_COMMENT_LEN) continue;
      var tokens = tokenize(text);
      if (!tokens.length) continue;
      if (tokens.length === 1 && GENERIC_NOISE[tokens[0]]) continue;
      var allNoise = true;
      for (var t = 0; t < tokens.length; t++) {
        if (!GENERIC_NOISE[tokens[t]]) { allNoise = false; break; }
      }
      if (allNoise) continue;
      filtered.push(comments[i]);
    }
    return filtered;
  }

  function velocityAndAcceleration(comments) {
    var timestamps = [];
    for (var i = 0; i < comments.length; i++) {
      var ts = parseTimestamp(comments[i]);
      if (ts !== null) timestamps.push(ts);
    }

    if (!timestamps.length) {
      return { velocity_per_hour: 0, velocity_score: 0, acceleration_score: 0, acceleration_raw: 0 };
    }

    timestamps.sort(function (a, b) { return a - b; });
    var spanSeconds = Math.max(timestamps[timestamps.length - 1] - timestamps[0], 60);
    var spanHours = spanSeconds / 3600;
    var overallVelocity = timestamps.length / spanHours;

    var mid = timestamps[0] + spanSeconds / 2;
    var early = [];
    var recent = [];
    for (var j = 0; j < timestamps.length; j++) {
      if (timestamps[j] <= mid) early.push(timestamps[j]);
      else recent.push(timestamps[j]);
    }

    var earlySpan = early.length ? Math.max((mid - timestamps[0]) / 3600, 0.25) : 0.25;
    var recentSpan = recent.length ? Math.max((timestamps[timestamps.length - 1] - mid) / 3600, 0.25) : 0.25;
    var earlyVelocity = early.length ? early.length / earlySpan : 0;
    var recentVelocity = recent.length ? recent.length / recentSpan : 0;

    var accelerationRaw = 0;
    if (earlyVelocity > 0) {
      accelerationRaw = ((recentVelocity - earlyVelocity) / earlyVelocity) * 100;
    } else if (recentVelocity > 0) {
      accelerationRaw = 100;
    }

    var velocityScore = Math.min(100, Math.round((overallVelocity / 50) * 100 * 100) / 100);
    var accelerationScore;
    if (accelerationRaw >= 50) {
      accelerationScore = Math.min(100, 60 + (accelerationRaw - 50) * 0.8);
    } else if (accelerationRaw >= 0) {
      accelerationScore = Math.min(100, 40 + accelerationRaw * 0.4);
    } else {
      accelerationScore = Math.max(0, 40 + accelerationRaw * 0.5);
    }

    return {
      velocity_per_hour: Math.round(overallVelocity * 100) / 100,
      velocity_score: velocityScore,
      acceleration_score: Math.round(accelerationScore * 100) / 100,
      acceleration_raw: Math.round(accelerationRaw * 100) / 100
    };
  }

  function semanticNicheRelevance(comments, caption, niche, keywords) {
    if (!String(niche || "").trim()) return 0;

    var nicheTokens = tokenize(niche);
    var semanticProfile = {};
    for (var i = 0; i < nicheTokens.length; i++) semanticProfile[nicheTokens[i]] = true;
    for (var k = 0; k < keywords.length; k++) {
      var kwt = tokenize(keywords[k]);
      for (var kt = 0; kt < kwt.length; kt++) semanticProfile[kwt[kt]] = true;
    }

    var synKeys = Object.keys(NICHE_SYNONYMS);
    for (var sk = 0; sk < synKeys.length; sk++) {
      var synList = NICHE_SYNONYMS[synKeys[sk]];
      for (var nt = 0; nt < nicheTokens.length; nt++) {
        if (synList.indexOf(nicheTokens[nt]) !== -1 || synKeys[sk] === nicheTokens[nt]) {
          for (var sl = 0; sl < synList.length; sl++) semanticProfile[synList[sl]] = true;
        }
      }
    }

    var texts = [caption || ""];
    for (var c = 0; c < comments.length; c++) texts.push(comments[c].comment_text || "");

    var combinedTokens = {};
    for (var t = 0; t < texts.length; t++) {
      var toks = tokenize(texts[t]);
      for (var ti = 0; ti < toks.length; ti++) combinedTokens[toks[ti]] = true;
    }

    var combinedKeys = Object.keys(combinedTokens);
    if (!combinedKeys.length) return 0;

    var overlap = 0;
    var profileKeys = Object.keys(semanticProfile);
    for (var o = 0; o < combinedKeys.length; o++) {
      if (semanticProfile[combinedKeys[o]]) overlap++;
    }
    var union = combinedKeys.length + profileKeys.length - overlap;
    var jaccard = union ? (overlap / union) * 100 : 0;

    var combinedLower = texts.join(" ").toLowerCase();
    var keywordHits = 0;
    for (var kh = 0; kh < keywords.length; kh++) {
      if (combinedLower.indexOf(keywords[kh]) !== -1) keywordHits++;
    }
    var keywordScore = Math.min(100, (keywordHits / Math.max(keywords.length, 1)) * 100);

    var prefixMatches = 0;
    for (var ck = 0; ck < combinedKeys.length; ck++) {
      for (var pk = 0; pk < profileKeys.length; pk++) {
        var ct = combinedKeys[ck];
        var st = profileKeys[pk];
        if (ct.length >= 4 && st.length >= 4 && (ct.indexOf(st.slice(0, 4)) === 0 || st.indexOf(ct.slice(0, 4)) === 0)) {
          prefixMatches++;
          break;
        }
      }
    }
    var prefixBonus = Math.min(15, prefixMatches * 3);

    var commentMatches = 0;
    for (var cm = 0; cm < comments.length; cm++) {
      var ctokens = tokenize(comments[cm].comment_text || "");
      for (var cti = 0; cti < ctokens.length; cti++) {
        if (semanticProfile[ctokens[cti]]) { commentMatches++; break; }
      }
    }
    var densityBonus = Math.min(15, (commentMatches / Math.max(comments.length, 1)) * 15);

    return Math.min(100, Math.round((jaccard * 0.35 + keywordScore * 0.40 + prefixBonus + densityBonus) * 100) / 100);
  }

  function curiosityScore(comments) {
    if (!comments.length) return 0;
    var matches = 0;
    for (var i = 0; i < comments.length; i++) {
      var lower = (comments[i].comment_text || "").toLowerCase();
      for (var p = 0; p < CURIOSITY_PHRASES.length; p++) {
        if (lower.indexOf(CURIOSITY_PHRASES[p]) !== -1) { matches++; break; }
      }
    }
    return Math.min(100, Math.round((matches / comments.length) * 100 * 100) / 100);
  }

  function controversyScore(comments) {
    if (!comments.length) return 0;
    var matches = 0;
    for (var i = 0; i < comments.length; i++) {
      var lower = (comments[i].comment_text || "").toLowerCase();
      for (var p = 0; p < CONTROVERSY_PHRASES.length; p++) {
        if (lower.indexOf(CONTROVERSY_PHRASES[p]) !== -1) { matches++; break; }
      }
    }
    return Math.min(100, Math.round((matches / comments.length) * 100 * 100) / 100);
  }

  function buildCrossVideoClusters(videos) {
    var phraseData = {};
    for (var v = 0; v < videos.length; v++) {
      var video = videos[v];
      var videoId = String(video.video_id || "");
      var comments = video.comments || [];
      var localPhrases = {};
      for (var c = 0; c < comments.length; c++) {
        var tokens = tokenize(comments[c].comment_text || "");
        for (var n = 2; n <= 3; n++) {
          var grams = ngrams(tokens, n);
          for (var g = 0; g < grams.length; g++) {
            localPhrases[grams[g]] = (localPhrases[grams[g]] || 0) + 1;
          }
        }
      }
      var phraseKeys = Object.keys(localPhrases);
      for (var pk = 0; pk < phraseKeys.length; pk++) {
        if (localPhrases[phraseKeys[pk]] < 2) continue;
        var phrase = phraseKeys[pk];
        if (!phraseData[phrase]) {
          phraseData[phrase] = { count: 0, videoIds: {} };
        }
        phraseData[phrase].count += localPhrases[phrase];
        phraseData[phrase].videoIds[videoId] = true;
      }
    }

    var clusters = [];
    var allPhrases = Object.keys(phraseData);
    for (var i = 0; i < allPhrases.length; i++) {
      var ph = allPhrases[i];
      var data = phraseData[ph];
      var videoCount = Object.keys(data.videoIds).length;
      if (videoCount < 2) continue;
      var crossScore = Math.min(100, videoCount * 25 + Math.min(data.count, 20) * 2.5);
      clusters.push({
        phrase: ph,
        total_count: data.count,
        video_count: videoCount,
        cross_video_score: Math.round(crossScore * 100) / 100,
        video_ids: Object.keys(data.videoIds)
      });
    }
    clusters.sort(function (a, b) {
      return b.cross_video_score - a.cross_video_score || b.video_count - a.video_count;
    });
    return { phraseData: phraseData, clusters: clusters };
  }

  function crossVideoScoreForVideo(phrases, phraseData) {
    if (!phrases.length) return 0;
    var scores = [];
    for (var i = 0; i < phrases.length; i++) {
      var data = phraseData[phrases[i].phrase];
      if (data) {
        var vc = Object.keys(data.videoIds).length;
        if (vc >= 2) {
          scores.push(Math.min(100, vc * 25 + Math.min(data.count, 20) * 2.5));
        }
      }
    }
    if (!scores.length) return 0;
    var sum = 0;
    for (var s = 0; s < scores.length; s++) sum += scores[s];
    return Math.round((sum / scores.length) * 100) / 100;
  }

  function viralityScore(velocity, acceleration, crossVideo, niche, curiosity) {
    var raw = velocity * WEIGHTS.velocity + acceleration * WEIGHTS.acceleration +
      crossVideo * WEIGHTS.cross_video + niche * WEIGHTS.niche_relevance + curiosity * WEIGHTS.curiosity;
    return Math.min(100, Math.round(raw * 100) / 100);
  }

  function earlyWarningLevel(virality, velocity, acceleration) {
    if (virality >= 75 || (velocity >= 70 && acceleration >= 50)) {
      return { level: 4, label: "Viral Now", color: "#ef4444" };
    }
    if (virality >= 50 || (velocity >= 45 && acceleration >= 35)) {
      return { level: 3, label: "Breakout Candidate", color: "#f97316" };
    }
    if (virality >= 25 || velocity >= 20 || acceleration >= 20) {
      return { level: 2, label: "Warming", color: "#fbbf24" };
    }
    return { level: 1, label: "Noise", color: "#6b7280" };
  }

  function timeToViralStatus(velocity, acceleration, virality, accelerationRaw) {
    if (virality >= 75 && velocity >= 60) {
      return { status: "already_viral", label: "Already Viral", color: "#ef4444" };
    }
    if (accelerationRaw >= 30 && velocity >= 25) {
      return { status: "likely_viral_soon", label: "Likely Viral Soon", color: "#22c55e" };
    }
    if (accelerationRaw < -20 && velocity >= 30) {
      return { status: "fading", label: "Fading", color: "#94a3b8" };
    }
    if (virality < 20 && velocity < 15) {
      return { status: "low_potential", label: "Low Potential", color: "#6b7280" };
    }
    if (accelerationRaw >= 10) {
      return { status: "likely_viral_soon", label: "Likely Viral Soon", color: "#22c55e" };
    }
    return { status: "low_potential", label: "Low Potential", color: "#6b7280" };
  }

  function topRepeatedPhrases(comments, limit) {
    var phraseCounts = {};
    for (var i = 0; i < comments.length; i++) {
      var tokens = tokenize(comments[i].comment_text || "");
      for (var n = 2; n <= 3; n++) {
        var grams = ngrams(tokens, n);
        for (var g = 0; g < grams.length; g++) {
          phraseCounts[grams[g]] = (phraseCounts[grams[g]] || 0) + 1;
        }
      }
    }
    var sorted = [];
    var keys = Object.keys(phraseCounts);
    for (var k = 0; k < keys.length; k++) {
      if (phraseCounts[keys[k]] >= 2) {
        sorted.push({ phrase: keys[k], count: phraseCounts[keys[k]] });
      }
    }
    sorted.sort(function (a, b) { return b.count - a.count; });
    return sorted.slice(0, limit || 5);
  }

  function groupByVideo(rawRows) {
    var byVideo = {};
    for (var i = 0; i < rawRows.length; i++) {
      var row = rawRows[i];
      var videoId = String(row.video_id || "");
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
        comment_author: row.comment_author || "",
        comment_like_count: Number(row.comment_like_count || 0),
        commented_at: row.commented_at
      });
    }
    return Object.keys(byVideo).map(function (id) { return byVideo[id]; });
  }

  function computeViralityPredictions(rawRows, niche) {
    var keywords = buildNicheKeywords(niche);
    var nicheClean = String(niche || "").trim();

    if (!nicheClean) {
      return { niche: "", keywords: [], videos: [], ranked_trends: [], cross_video_clusters: [], video_count: 0 };
    }

    var videos = groupByVideo(rawRows);
    var filteredVideos = [];
    for (var i = 0; i < videos.length; i++) {
      var filtered = filterSignalComments(videos[i].comments || []);
      if (filtered.length >= MIN_COMMENTS) {
        filteredVideos.push({
          video_id: videos[i].video_id,
          url: videos[i].url,
          caption: videos[i].caption,
          author: videos[i].author,
          comments: filtered
        });
      }
    }

    var clusterResult = buildCrossVideoClusters(filteredVideos);
    var phraseData = clusterResult.phraseData;
    var crossClusters = clusterResult.clusters;

    var results = [];
    for (var v = 0; v < filteredVideos.length; v++) {
      var video = filteredVideos[v];
      var comments = video.comments;
      var motion = velocityAndAcceleration(comments);
      var relevance = semanticNicheRelevance(comments, video.caption, nicheClean, keywords);
      if (relevance < MIN_RELEVANCE) continue;

      var curiosity = curiosityScore(comments);
      var controversy = controversyScore(comments);
      var phrases = topRepeatedPhrases(comments, 5);
      var crossVideo = crossVideoScoreForVideo(phrases, phraseData);
      var virality = viralityScore(
        motion.velocity_score, motion.acceleration_score, crossVideo, relevance, curiosity
      );
      var warning = earlyWarningLevel(virality, motion.velocity_score, motion.acceleration_score);
      var viralStatus = timeToViralStatus(
        motion.velocity_score, motion.acceleration_score, virality, motion.acceleration_raw
      );

      results.push({
        video_id: video.video_id,
        video_url: video.url,
        author: video.author,
        caption_preview: (video.caption || "").slice(0, 200),
        comments_analyzed: comments.length,
        virality_score: virality,
        early_warning: warning,
        time_to_viral: viralStatus,
        signals: {
          velocity_per_hour: motion.velocity_per_hour,
          velocity_score: motion.velocity_score,
          acceleration_score: motion.acceleration_score,
          acceleration_raw: motion.acceleration_raw,
          cross_video_score: crossVideo,
          niche_relevance_score: relevance,
          curiosity_score: curiosity,
          controversy_score: controversy
        },
        top_repeated_phrases: phrases
      });
    }

    results.sort(function (a, b) { return b.virality_score - a.virality_score; });

    var nicheClusters = [];
    for (var nc = 0; nc < crossClusters.length; nc++) {
      var cluster = crossClusters[nc];
      var matchesNiche = false;
      for (var kw = 0; kw < keywords.length; kw++) {
        if (cluster.phrase.indexOf(keywords[k]) !== -1) { matchesNiche = true; break; }
      }
      if (matchesNiche) nicheClusters.push(cluster);
    }
    if (!nicheClusters.length) nicheClusters = crossClusters.slice(0, 15);
    else nicheClusters = nicheClusters.slice(0, 15);

    var rankedTrends = [];
    for (var r = 0; r < results.length; r++) {
      rankedTrends.push({
        type: "video",
        topic: (results[r].caption_preview || "").slice(0, 80) || ("Video " + results[r].video_id),
        virality_score: results[r].virality_score,
        early_warning: results[r].early_warning,
        time_to_viral: results[r].time_to_viral,
        video_id: results[r].video_id,
        video_url: results[r].video_url,
        author: results[r].author,
        signals: results[r].signals
      });
    }

    for (var ct = 0; ct < Math.min(nicheClusters.length, 10); ct++) {
      var c = nicheClusters[ct];
      var clusterVirality = Math.min(100, c.cross_video_score * 0.6 + c.video_count * 8);
      rankedTrends.push({
        type: "cluster",
        topic: c.phrase,
        virality_score: Math.round(clusterVirality * 100) / 100,
        early_warning: earlyWarningLevel(clusterVirality, c.cross_video_score, 30),
        video_count: c.video_count,
        total_mentions: c.total_count,
        signals: { cross_video_score: c.cross_video_score }
      });
    }

    rankedTrends.sort(function (a, b) { return b.virality_score - a.virality_score; });

    return {
      niche: nicheClean,
      keywords: keywords,
      video_count: results.length,
      videos: results,
      cross_video_clusters: nicheClusters,
      ranked_trends: rankedTrends.slice(0, 25),
      weights: WEIGHTS
    };
  }

  function levelBadge(warning) {
    if (!warning) return "";
    return '<span class="tag" style="border-color:' + warning.color + ';color:' + warning.color + '">L' +
      warning.level + ' · ' + escapeHtml(warning.label) + '</span>';
  }

  function statusBadge(status) {
    if (!status) return "";
    return '<span class="tag" style="border-color:' + status.color + ';color:' + status.color + '">' +
      escapeHtml(status.label) + '</span>';
  }

  function metricBar(label, value, color) {
    var v = Math.min(100, Math.max(0, Number(value) || 0));
    return (
      '<div style="margin-bottom:6px">' +
      '<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:2px">' +
      '<span style="color:var(--muted)">' + label + '</span>' +
      '<span style="color:' + color + ';font-weight:600">' + v.toFixed(0) + '</span></div>' +
      '<div class="feed-bar" style="height:3px"><div class="feed-bar-fill" style="width:' +
      v + '%;background:' + color + '"></div></div></div>'
    );
  }

  function renderResults(data) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var niche = data.niche || currentNiche;
    var keywords = data.keywords || [];
    var ranked = data.ranked_trends || [];
    var videos = data.videos || [];
    var clusters = data.cross_video_clusters || [];

    var h = '<div class="card card-glow" style="border-color:rgba(249,115,22,.4)">';
    h += '<div class="card-header">';
    h += '<h2 style="color:#f97316">Early Virality Prediction</h2>';
    h += '<div class="section-icon" style="background:rgba(249,115,22,.1);border-color:rgba(249,115,22,.3);color:#f97316">&#9889;</div>';
    h += '</div>';

    h += '<p style="font-size:11px;color:var(--muted);margin-bottom:12px">Multi-signal early trend detection from <code style="color:var(--green)">niche_comment_raw</code> — velocity, acceleration, cross-video clustering, semantic niche matching, and controversy signals. Isolated from trend pipeline.</p>';

    h += '<div style="margin-bottom:14px">';
    h += '<label style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:6px">Niche Query</label>';
    h += '<div style="display:flex;gap:8px;flex-wrap:wrap">';
    h += '<input id="viralityNicheInput" type="text" list="nicheList" placeholder="Enter niche (e.g. fitness, skincare, crypto)" value="' + escapeHtml(niche) + '" style="flex:1;min-width:200px;padding:12px;border:1px solid var(--border);border-radius:10px;background:var(--panel2);color:#fff;font-size:13px" autocomplete="off">';
    h += '<button id="viralityNicheBtn" style="padding:12px 18px;border:none;border-radius:10px;background:linear-gradient(135deg,#f97316,#ea580c);color:#fff;font-size:12px;font-weight:800;cursor:pointer;white-space:nowrap">Predict Virality</button>';
    h += '</div>';
    if (keywords.length) {
      h += '<div style="margin-top:8px;font-size:10px;color:var(--muted)">Semantic keywords: <span style="color:#f97316">' + escapeHtml(keywords.slice(0, 12).join(", ")) + '</span></div>';
    }
    h += '<div style="margin-top:6px;font-size:10px;color:var(--muted)">' + rawCache.length + ' raw comments · signal-first filtering active</div>';
    h += '</div>';

    if (!niche.trim()) {
      h += '<p style="font-size:12px;color:var(--muted);padding:8px 0">Enter a niche to see ranked emerging trends with virality scores and early warning levels.</p>';
      h += '</div>';
      el.innerHTML = h;
      bindSearchEvents();
      return;
    }

    if (!ranked.length) {
      h += '<p style="font-size:12px;color:var(--amber);padding:8px 0">No high-signal virality predictions for <strong>' + escapeHtml(niche) + '</strong>. Try another niche or wait for more comment data.</p>';
      h += '</div>';
      el.innerHTML = h;
      bindSearchEvents();
      return;
    }

    var levelCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };
    for (var lc = 0; lc < ranked.length; lc++) {
      var lvl = ranked[lc].early_warning ? ranked[lc].early_warning.level : 1;
      levelCounts[lvl] = (levelCounts[lvl] || 0) + 1;
    }

    h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:16px">';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#f97316">' + ranked.length + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Ranked Trends</div></div>';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid rgba(239,68,68,.3);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#ef4444">' + (levelCounts[4] || 0) + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Viral Now</div></div>';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid rgba(249,115,22,.3);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#f97316">' + (levelCounts[3] || 0) + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Breakout</div></div>';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid rgba(34,197,94,.3);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#22c55e">' + clusters.length + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Cross-Video</div></div>';
    h += '</div>';

    h += '<div style="font-size:10px;color:#f97316;font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">Ranked Emerging Trends</div>';
    for (var i = 0; i < Math.min(ranked.length, 15); i++) {
      var trend = ranked[i];
      h += '<div class="feed-item" style="border-left:3px solid ' + (trend.early_warning ? trend.early_warning.color : "#6b7280") + '">';
      h += '<div class="feed-header">';
      h += '<span class="feed-keyword" style="max-width:70%">' + escapeHtml(trend.topic) + '</span>';
      h += '<span class="tag" style="border-color:rgba(249,115,22,.4);color:#f97316">Score ' + Number(trend.virality_score || 0).toFixed(0) + '</span>';
      h += '</div>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0">';
      h += levelBadge(trend.early_warning);
      if (trend.time_to_viral) h += statusBadge(trend.time_to_viral);
      if (trend.type === "cluster") {
        h += '<span class="tag" style="border-color:rgba(34,197,94,.4);color:#22c55e">Cross-Video ×' + (trend.video_count || 0) + '</span>';
      }
      h += '</div>';
      if (trend.signals) {
        h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:8px">';
        if (trend.signals.velocity_score !== undefined) h += metricBar("Velocity", trend.signals.velocity_score, "#22d3ee");
        if (trend.signals.acceleration_score !== undefined) h += metricBar("Acceleration", trend.signals.acceleration_score, "#a78bfa");
        if (trend.signals.cross_video_score !== undefined) h += metricBar("Cross-Video", trend.signals.cross_video_score, "#22c55e");
        if (trend.signals.niche_relevance_score !== undefined) h += metricBar("Niche Match", trend.signals.niche_relevance_score, "#34d399");
        if (trend.signals.curiosity_score !== undefined) h += metricBar("Curiosity", trend.signals.curiosity_score, "#fbbf24");
        if (trend.signals.controversy_score !== undefined) h += metricBar("Controversy", trend.signals.controversy_score, "#ef4444");
        h += '</div>';
      }
      if (trend.video_url) {
        h += '<div style="margin-top:6px;font-size:10px;color:var(--muted)">@' + escapeHtml(trend.author || "unknown") +
          ' · <a href="' + escapeHtml(trend.video_url) + '" target="_blank" rel="noopener" style="color:#f97316">View video</a></div>';
      }
      h += '</div>';
    }

    if (videos.length) {
      h += '<div style="font-size:10px;color:#f97316;font-weight:700;margin:16px 0 8px;text-transform:uppercase;letter-spacing:1px">Video-Level Predictions</div>';
      for (var vi = 0; vi < Math.min(videos.length, 8); vi++) {
        var vid = videos[vi];
        var sig = vid.signals || {};
        h += '<div class="feed-item" style="border-left:3px solid rgba(249,115,22,.4);padding:10px;margin-bottom:8px">';
        h += '<div style="font-size:12px;color:var(--white);line-height:1.4">' + escapeHtml(vid.caption_preview || "Untitled") + '</div>';
        h += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0">';
        h += levelBadge(vid.early_warning);
        h += statusBadge(vid.time_to_viral);
        h += '<span class="tag" style="color:#f97316;border-color:rgba(249,115,22,.4)">' + Number(vid.virality_score || 0).toFixed(0) + ' pts</span>';
        h += '</div>';
        h += '<div style="font-size:10px;color:var(--muted)">' + (vid.comments_analyzed || 0) + ' comments · ' +
          Number(sig.velocity_per_hour || 0).toFixed(1) + ' c/hr · accel ' + Number(sig.acceleration_raw || 0).toFixed(0) + '%</div>';
        h += '</div>';
      }
    }

    h += '</div>';
    el.innerHTML = h;
    bindSearchEvents();
  }

  function bindSearchEvents() {
    var input = document.getElementById("viralityNicheInput");
    var btn = document.getElementById("viralityNicheBtn");
    if (!input) return;

    function runQuery() {
      currentNiche = (input.value || "").trim();
      if (typeof localStorage !== "undefined") {
        localStorage.setItem("cr_virality_niche_query", currentNiche);
      }
      if (!currentNiche) {
        renderResults({ niche: "", keywords: [], ranked_trends: [], videos: [], cross_video_clusters: [] });
        return;
      }
      renderResults(computeViralityPredictions(rawCache, currentNiche));
    }

    input.onkeydown = function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); runQuery(); }
    };
    input.oninput = function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runQuery, DEBOUNCE_MS);
    };
    if (btn) btn.onclick = runQuery;
  }

  function describeError(error) {
    if (!error) return "No raw comment data available yet.";
    var code = error.code || "";
    var msg = error.message || String(error);
    if (code === "PGRST205" || msg.indexOf("Could not find the table") !== -1) {
      return "Supabase table niche_comment_raw not found. Run sql/niche_comment_raw.sql first.";
    }
    if (code === "42501" || /permission|policy|JWT/i.test(msg)) {
      return "Cannot read niche_comment_raw — please log in or check Supabase RLS.";
    }
    return "Virality prediction error: " + msg;
  }

  function renderShell(message, isError) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    el.innerHTML =
      '<div class="card" style="border-color:rgba(249,115,22,.3)">' +
      '<div class="card-header"><h2 style="color:#f97316">Early Virality Prediction</h2>' +
      '<div class="section-icon" style="background:rgba(249,115,22,.1);border-color:rgba(249,115,22,.3);color:#f97316">&#9889;</div></div>' +
      '<p style="font-size:12px;color:' + (isError ? "var(--red)" : "var(--muted)") + ';padding:8px 0">' + message + '</p></div>';
  }

  async function refreshViralityPrediction() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    if (!window.TikTokLiveState) {
      renderShell("Waiting for live state client...");
      return;
    }

    renderShell("Loading comment data for virality analysis...");

    try {
      var client = getClient();
      if (client) {
        var session = await client.auth.getSession();
        if (!session.data || !session.data.session) {
          renderShell("Login required to load virality predictions.");
          return;
        }
      }

      var savedNiche = "";
      if (typeof localStorage !== "undefined") {
        savedNiche = localStorage.getItem("cr_virality_niche_query") ||
          localStorage.getItem("cr_niche_comment_query") || "";
      }
      if (!savedNiche && typeof USER_NICHE !== "undefined" && USER_NICHE) {
        savedNiche = USER_NICHE;
      }
      currentNiche = savedNiche;

      var liveState = await window.TikTokLiveState.fetch(currentNiche || "general");
      rawCache = (liveState && liveState.niche_comment_raw) || [];

      if (currentNiche) {
        renderResults(computeViralityPredictions(rawCache, currentNiche));
      } else {
        renderResults({ niche: "", keywords: [], ranked_trends: [], videos: [], cross_video_clusters: [] });
      }
    } catch (err) {
      renderShell(describeError(err), true);
    }
  }

  function isTrendsTabVisible() {
    var tab = document.getElementById("tab-tiktok");
    return tab && tab.classList.contains("active");
  }

  function hookTabObserver() {
    var tab = document.getElementById("tab-tiktok");
    if (!tab || typeof MutationObserver === "undefined") return;
    var observer = new MutationObserver(function () {
      if (isTrendsTabVisible()) refreshViralityPrediction();
    });
    observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
  }

  function init() {
    if (initialized) return;
    initialized = true;
    if (!document.getElementById(MOUNT_ID)) return;
    hookTabObserver();
    if (isTrendsTabVisible()) {
      refreshViralityPrediction();
    } else {
      setTimeout(function () {
        if (getClient()) refreshViralityPrediction();
      }, 2500);
    }
  }

  window.refreshViralityPrediction = refreshViralityPrediction;
  window.computeViralityPredictions = computeViralityPredictions;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
