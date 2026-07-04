/**
 * Niche Comment Intelligence — isolated, query-driven dashboard section.
 * Fetches raw comments from niche_comment_raw and computes signals at runtime
 * based on the user's selected niche. Does not modify existing TikTok trend UI.
 */
(function () {
  "use strict";

  var MOUNT_ID = "nicheCommentIntelligence";
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

  function commentVelocity(comments, commentCount) {
    var timestamps = [];
    for (var i = 0; i < comments.length; i++) {
      var ts = comments[i].commented_at;
      if (!ts) continue;
      try {
        timestamps.push(new Date(ts).getTime() / 1000);
      } catch (e) {}
    }
    var count = Math.max(comments.length, commentCount || 0, 1);
    var rate = count / 24;
    if (timestamps.length >= 2) {
      var span = Math.max(Math.max.apply(null, timestamps) - Math.min.apply(null, timestamps), 60);
      rate = count / (span / 3600);
    } else if (timestamps.length === 1) {
      rate = count;
    }
    return Math.min(100, Math.round((rate / 50) * 100 * 100) / 100);
  }

  function repetitionScore(comments) {
    if (!comments.length) return 0;
    var phraseCounts = {};
    for (var i = 0; i < comments.length; i++) {
      var text = comments[i].comment_text || "";
      var tokens = tokenize(text);
      for (var n = 2; n <= 3; n++) {
        var grams = ngrams(tokens, n);
        for (var g = 0; g < grams.length; g++) {
          phraseCounts[grams[g]] = (phraseCounts[grams[g]] || 0) + 1;
        }
      }
    }
    var keys = Object.keys(phraseCounts);
    if (!keys.length) return 0;
    var repeated = 0;
    var maxRepeat = 0;
    for (var k = 0; k < keys.length; k++) {
      if (phraseCounts[keys[k]] >= 2) repeated++;
      if (phraseCounts[keys[k]] > maxRepeat) maxRepeat = phraseCounts[keys[k]];
    }
    var ratio = repeated / keys.length;
    var boost = maxRepeat >= 3 ? Math.min(30, (maxRepeat - 2) * 10) : 0;
    return Math.min(100, Math.round((ratio * 70 + boost) * 100) / 100);
  }

  function curiosityScore(comments) {
    if (!comments.length) return 0;
    var matches = 0;
    for (var i = 0; i < comments.length; i++) {
      var lower = (comments[i].comment_text || "").toLowerCase();
      for (var p = 0; p < CURIOSITY_PHRASES.length; p++) {
        if (lower.indexOf(CURIOSITY_PHRASES[p]) !== -1) {
          matches++;
          break;
        }
      }
    }
    return Math.min(100, Math.round((matches / comments.length) * 100 * 100) / 100);
  }

  function nicheRelevanceScore(comments, caption, keywords) {
    if (!keywords.length) return 0;
    var texts = [caption || ""];
    for (var i = 0; i < comments.length; i++) texts.push(comments[i].comment_text || "");
    var combined = texts.join(" ").toLowerCase();
    if (!combined.trim()) return 0;

    var hits = 0;
    for (var k = 0; k < keywords.length; k++) {
      if (combined.indexOf(keywords[k]) !== -1) hits++;
    }
    var keywordScore = Math.min(100, (hits / Math.max(keywords.length, 1)) * 100);

    var commentMatches = 0;
    for (var c = 0; c < comments.length; c++) {
      var lower = (comments[c].comment_text || "").toLowerCase();
      for (var j = 0; j < keywords.length; j++) {
        if (lower.indexOf(keywords[j]) !== -1) {
          commentMatches++;
          break;
        }
      }
    }
    var densityBonus = Math.min(20, (commentMatches / Math.max(comments.length, 1)) * 20);
    return Math.min(100, Math.round((keywordScore + densityBonus) * 100) / 100);
  }

  function compositeSignal(velocity, repetition, curiosity, niche) {
    return Math.min(100, Math.round((velocity * 0.3 + repetition * 0.2 + curiosity * 0.25 + niche * 0.25) * 100) / 100);
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
    return sorted.slice(0, limit || 8);
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
          comment_count: 0,
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
    var videos = Object.keys(byVideo).map(function (id) {
      var v = byVideo[id];
      v.comment_count = Math.max(v.comment_count, v.comments.length);
      return v;
    });
    return videos;
  }

  function computeSignals(rawRows, niche) {
    var keywords = buildNicheKeywords(niche);
    var videos = groupByVideo(rawRows);
    var results = [];
    var phraseTotals = {};

    for (var i = 0; i < videos.length; i++) {
      var video = videos[i];
      var comments = video.comments || [];
      var velocity = commentVelocity(comments, video.comment_count);
      var repetition = repetitionScore(comments);
      var curiosity = curiosityScore(comments);
      var relevance = nicheRelevanceScore(comments, video.caption, keywords);
      if (relevance < 15) continue;

      var composite = compositeSignal(velocity, repetition, curiosity, relevance);
      var phrases = topRepeatedPhrases(comments, 5);
      for (var p = 0; p < phrases.length; p++) {
        phraseTotals[phrases[p].phrase] = (phraseTotals[phrases[p].phrase] || 0) + phrases[p].count;
      }

      var trending = [];
      for (var c = 0; c < comments.length; c++) {
        var text = comments[c].comment_text || "";
        var lower = text.toLowerCase();
        var rel = 0;
        for (var k = 0; k < keywords.length; k++) {
          if (lower.indexOf(keywords[k]) !== -1) rel++;
        }
        var cur = 0;
        for (var q = 0; q < CURIOSITY_PHRASES.length; q++) {
          if (lower.indexOf(CURIOSITY_PHRASES[q]) !== -1) { cur = 1; break; }
        }
        var score = rel * 25 + cur * 15 + Math.min(comments[c].comment_like_count || 0, 50);
        if (score > 0) {
          trending.push({
            text: text.slice(0, 200),
            author: comments[c].comment_author || "",
            like_count: comments[c].comment_like_count || 0,
            score: score
          });
        }
      }
      trending.sort(function (a, b) { return b.score - a.score; });

      results.push({
        video_id: video.video_id,
        video_url: video.url,
        author: video.author,
        caption_preview: (video.caption || "").slice(0, 200),
        comment_count: video.comment_count,
        comments_analyzed: comments.length,
        signals: {
          comment_velocity: velocity,
          repetition_score: repetition,
          curiosity_score: curiosity,
          niche_relevance_score: relevance,
          composite_signal: composite
        },
        top_repeated_phrases: phrases,
        trending_comments: trending.slice(0, 5)
      });
    }

    results.sort(function (a, b) {
      return b.signals.composite_signal - a.signals.composite_signal;
    });

    var emerging = [];
    var phraseKeys = Object.keys(phraseTotals);
    phraseKeys.sort(function (a, b) { return phraseTotals[b] - phraseTotals[a]; });
    for (var e = 0; e < Math.min(phraseKeys.length, 15); e++) {
      emerging.push({ phrase: phraseKeys[e], count: phraseTotals[phraseKeys[e]] });
    }

    var flatTrending = [];
    for (var v = 0; v < Math.min(results.length, 10); v++) {
      var vid = results[v];
      for (var t = 0; t < (vid.trending_comments || []).length; t++) {
        flatTrending.push({
          text: vid.trending_comments[t].text,
          author: vid.trending_comments[t].author,
          like_count: vid.trending_comments[t].like_count,
          score: vid.trending_comments[t].score,
          video_url: vid.video_url,
          video_author: vid.author
        });
      }
    }
    flatTrending.sort(function (a, b) { return b.score - a.score; });

    return {
      niche: niche,
      keywords: keywords,
      video_count: results.length,
      videos: results,
      emerging_phrases: emerging,
      trending_comments: flatTrending.slice(0, 20)
    };
  }

  function metricBar(label, value, color) {
    var v = Math.min(100, Math.max(0, Number(value) || 0));
    return (
      '<div style="margin-bottom:8px">' +
      '<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">' +
      '<span style="color:var(--muted)">' + label + '</span>' +
      '<span style="color:' + color + ';font-weight:600">' + v.toFixed(0) + '</span>' +
      '</div>' +
      '<div class="feed-bar" style="height:4px"><div class="feed-bar-fill" style="width:' +
      v + '%;background:' + color + '"></div></div></div>'
    );
  }

  function renderResults(data) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var niche = data.niche || currentNiche;
    var keywords = data.keywords || [];
    var videos = data.videos || [];
    var emerging = data.emerging_phrases || [];
    var trending = data.trending_comments || [];

    var h = '<div class="card card-glow" style="border-color:rgba(56,189,248,.35)">';
    h += '<div class="card-header">';
    h += '<h2 style="color:#38bdf8">Niche Comment Intelligence</h2>';
    h += '<div class="section-icon" style="background:rgba(56,189,248,.1);border-color:rgba(56,189,248,.3);color:#38bdf8">&#128172;</div>';
    h += '</div>';

    h += '<p style="font-size:11px;color:var(--muted);margin-bottom:12px">Dynamic comment signals computed at query time from <code style="color:var(--green)">niche_comment_raw</code> — isolated from trend pipeline</p>';

    h += '<div style="margin-bottom:14px">';
    h += '<label style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:6px">Niche Search</label>';
    h += '<div style="display:flex;gap:8px;flex-wrap:wrap">';
    h += '<input id="nicheCommentSearchInput" type="text" list="nicheList" placeholder="Enter niche (e.g. fitness, skincare, crypto, finance)" value="' + escapeHtml(niche) + '" style="flex:1;min-width:200px;padding:12px;border:1px solid var(--border);border-radius:10px;background:var(--panel2);color:#fff;font-size:13px" autocomplete="off">';
    h += '<button id="nicheCommentSearchBtn" style="padding:12px 18px;border:none;border-radius:10px;background:linear-gradient(135deg,#38bdf8,#0ea5e9);color:#031109;font-size:12px;font-weight:800;cursor:pointer;white-space:nowrap">Analyze Niche</button>';
    h += '</div>';
    if (keywords.length) {
      h += '<div style="margin-top:8px;font-size:10px;color:var(--muted)">Matching keywords: <span style="color:#38bdf8">' + escapeHtml(keywords.slice(0, 12).join(", ")) + '</span></div>';
    }
    h += '<div style="margin-top:6px;font-size:10px;color:var(--muted)">' + rawCache.length + ' raw comments loaded</div>';
    h += '</div>';

    if (!niche.trim()) {
      h += '<p style="font-size:12px;color:var(--muted);padding:8px 0">Enter a niche above to see emerging TikTok comment signals for that topic.</p>';
      h += '</div>';
      el.innerHTML = h;
      bindSearchEvents();
      return;
    }

    if (!videos.length) {
      h += '<p style="font-size:12px;color:var(--amber);padding:8px 0">No relevant comment signals found for <strong>' + escapeHtml(niche) + '</strong>. Try a different niche or wait for more raw comment data to be ingested.</p>';
      h += '</div>';
      el.innerHTML = h;
      bindSearchEvents();
      return;
    }

    h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:16px">';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#38bdf8">' + videos.length + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Relevant Videos</div></div>';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#22d3ee">' + emerging.length + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Emerging Phrases</div></div>';
    h += '<div style="padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;text-align:center"><div style="font-size:22px;font-weight:900;color:#f472b6">' + trending.length + '</div><div style="font-size:9px;color:var(--muted);text-transform:uppercase">Trending Comments</div></div>';
    h += '</div>';

    if (emerging.length) {
      h += '<div style="margin-bottom:16px"><div style="font-size:10px;color:var(--green);font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">Emerging Phrases</div>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:6px">';
      for (var e = 0; e < Math.min(emerging.length, 12); e++) {
        h += '<span class="tag" style="border-color:rgba(56,189,248,.4);color:#38bdf8">' + escapeHtml(emerging[e].phrase) + ' <span style="opacity:.7">×' + emerging[e].count + '</span></span>';
      }
      h += '</div></div>';
    }

    if (trending.length) {
      h += '<div style="margin-bottom:16px"><div style="font-size:10px;color:var(--green);font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">Trending Comments</div>';
      for (var t = 0; t < Math.min(trending.length, 8); t++) {
        var tc = trending[t];
        h += '<div class="feed-item" style="border-left:3px solid rgba(56,189,248,.4);padding:10px;margin-bottom:8px">';
        h += '<div style="font-size:12px;color:var(--white);line-height:1.4">"' + escapeHtml(tc.text) + '"</div>';
        h += '<div style="font-size:10px;color:var(--muted);margin-top:4px">@' + escapeHtml(tc.author || tc.video_author || "unknown");
        if (tc.like_count) h += ' · ' + tc.like_count + ' likes';
        if (tc.video_url) h += ' · <a href="' + escapeHtml(tc.video_url) + '" target="_blank" rel="noopener" style="color:#38bdf8">video</a>';
        h += '</div></div>';
      }
      h += '</div>';
    }

    h += '<div style="font-size:10px;color:var(--green);font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">High-Velocity Videos (Niche Relevant)</div>';

    for (var i = 0; i < Math.min(videos.length, 15); i++) {
      var video = videos[i];
      var sig = video.signals || {};
      h += '<div class="feed-item" style="border-left:3px solid rgba(56,189,248,.5)">';
      h += '<div class="feed-header"><span class="feed-keyword">@' + escapeHtml(video.author || "unknown") + '</span>';
      h += '<span class="tag" style="border-color:rgba(56,189,248,.4);color:#38bdf8">Signal ' + Number(sig.composite_signal || 0).toFixed(0) + '</span></div>';
      h += '<div style="font-size:12px;color:var(--white);margin:6px 0;line-height:1.4">' + escapeHtml(video.caption_preview || "Untitled video") + '</div>';
      h += '<div class="feed-metrics" style="margin-bottom:10px">';
      h += '<div class="feed-metric"><div class="fm-label">Comments</div><div class="fm-value">' + (video.comment_count || 0) + '</div></div>';
      h += '<div class="feed-metric"><div class="fm-label">Analyzed</div><div class="fm-value">' + (video.comments_analyzed || 0) + '</div></div>';
      h += '<div class="feed-metric"><div class="fm-label">Relevance</div><div class="fm-value" style="color:#34d399">' + Number(sig.niche_relevance_score || 0).toFixed(0) + '</div></div>';
      h += '</div>';
      h += metricBar("Comment Velocity", sig.comment_velocity, "#22d3ee");
      h += metricBar("Repetition Score", sig.repetition_score, "#f472b6");
      h += metricBar("Curiosity / Confusion", sig.curiosity_score, "#fbbf24");
      h += metricBar("Niche Relevance", sig.niche_relevance_score, "#34d399");
      if (video.video_url) {
        h += '<div style="margin-top:8px"><a href="' + escapeHtml(video.video_url) + '" target="_blank" rel="noopener" style="font-size:10px;color:#38bdf8">View video →</a></div>';
      }
      h += '</div>';
    }

    h += '</div>';
    el.innerHTML = h;
    bindSearchEvents();
  }

  function bindSearchEvents() {
    var input = document.getElementById("nicheCommentSearchInput");
    var btn = document.getElementById("nicheCommentSearchBtn");
    if (!input) return;

    function runQuery() {
      currentNiche = (input.value || "").trim();
      if (typeof localStorage !== "undefined") {
        localStorage.setItem("cr_niche_comment_query", currentNiche);
      }
      if (!currentNiche) {
        renderResults({ niche: "", keywords: [], videos: [], emerging_phrases: [], trending_comments: [] });
        return;
      }
      var data = computeSignals(rawCache, currentNiche);
      renderResults(data);
    }

    input.onkeydown = function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        runQuery();
      }
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
    return "Comment intelligence error: " + msg;
  }

  function renderShell(message, isError) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    el.innerHTML =
      '<div class="card" style="border-color:rgba(56,189,248,.3)">' +
      '<div class="card-header"><h2 style="color:#38bdf8">Niche Comment Intelligence</h2>' +
      '<div class="section-icon" style="background:rgba(56,189,248,.1);border-color:rgba(56,189,248,.3);color:#38bdf8">&#128172;</div></div>' +
      '<p style="font-size:12px;color:' + (isError ? "var(--red)" : "var(--muted)") + ';padding:8px 0">' + message + '</p></div>';
  }

  async function refreshNicheCommentIntelligence() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    if (!window.TikTokLiveState) {
      renderShell("Waiting for live state client...");
      return;
    }

    renderShell("Loading raw TikTok comments...");

    try {
      var client = getClient();
      if (client) {
        var session = await client.auth.getSession();
        if (!session.data || !session.data.session) {
          renderShell("Login required to load niche comment intelligence.");
          return;
        }
      }

      var savedNiche = "";
      if (typeof localStorage !== "undefined") {
        savedNiche = localStorage.getItem("cr_niche_comment_query") || "";
      }
      if (!savedNiche && typeof USER_NICHE !== "undefined" && USER_NICHE) {
        savedNiche = USER_NICHE;
      }
      currentNiche = savedNiche;

      var liveState = await window.TikTokLiveState.fetch(currentNiche || "general");
      rawCache = (liveState && liveState.niche_comment_raw) || [];

      if (currentNiche) {
        renderResults(computeSignals(rawCache, currentNiche));
      } else {
        renderResults({ niche: "", keywords: [], videos: [], emerging_phrases: [], trending_comments: [] });
      }

      if (window.TikTokInsightsHardening && typeof window.TikTokInsightsHardening.refresh === "function") {
        try {
          if (liveState && liveState.insights && liveState.insights.length) {
            window.TikTokInsightsHardening.renderFromLiveState(liveState);
          } else {
            window.TikTokInsightsHardening.refresh(rawCache, currentNiche);
          }
        } catch (hardeningErr) {
          console.warn("[TikTokInsightsHardening]", hardeningErr);
        }
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
      if (isTrendsTabVisible()) refreshNicheCommentIntelligence();
    });
    observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
  }

  function init() {
    if (initialized) return;
    initialized = true;
    if (!document.getElementById(MOUNT_ID)) return;
    hookTabObserver();
    if (isTrendsTabVisible()) {
      refreshNicheCommentIntelligence();
    } else {
      setTimeout(function () {
        if (getClient()) refreshNicheCommentIntelligence();
      }, 2500);
    }
  }

  window.refreshNicheCommentIntelligence = refreshNicheCommentIntelligence;
  window.computeNicheCommentSignals = computeSignals;
  window.getNicheCommentRawCache = function () { return rawCache; };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
