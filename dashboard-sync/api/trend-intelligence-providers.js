/**
 * Server-side trend data providers for /api/trend-intelligence.
 * All external fetches run in Vercel serverless — never in the browser.
 */

const DEFAULT_TRENDS_JSON_URL =
  "https://raw.githubusercontent.com/patriotradar/patriot-radar-dashboard/main/results.json";

const DEFAULT_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  Accept: "application/rss+xml, application/xml, text/xml, application/json, text/plain, */*",
};

const NICHE_NEWS_QUERIES = {
  patriotic: ["UK politics", "UK news today", "British news", "UK government"],
  patriot: ["UK politics", "UK news today", "British news", "UK government"],
  "uk politics": ["UK politics", "UK news today", "British news", "UK government"],
  crypto: ["cryptocurrency news", "bitcoin news", "crypto market", "blockchain news"],
  cryptocurrency: ["cryptocurrency news", "bitcoin news", "crypto market", "blockchain news"],
  bitcoin: ["cryptocurrency news", "bitcoin news", "crypto market", "blockchain news"],
  finance: ["finance news", "stock market news", "investing news", "economy news"],
  investing: ["finance news", "stock market news", "investing news", "economy news"],
  tech: ["tech news today", "technology news", "AI news", "startup news"],
  technology: ["tech news today", "technology news", "AI news", "startup news"],
  gaming: ["gaming news", "video game news", "esports news"],
  fitness: ["fitness news", "health news", "wellness trending"],
  health: ["fitness news", "health news", "wellness trending"],
};

const REDDIT_SUBREDDITS = [
  "unitedkingdom",
  "CasualUK",
  "ukpolitics",
  "BritishMilitary",
  "AskUK",
  "BritishSuccess",
  "britishproblems",
];

const UK_NEWS_RSS_FEEDS = [
  ["https://feeds.bbci.co.uk/news/uk/rss.xml", "BBC UK"],
  ["https://feeds.bbci.co.uk/news/politics/rss.xml", "BBC Politics"],
  ["https://feeds.skynews.com/feeds/rss/uk.xml", "Sky UK"],
  ["https://www.theguardian.com/uk-news/rss", "Guardian UK"],
];

function decodeEntities(text) {
  return String(text || "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#\d+;/g, "")
    .replace(/<!\[CDATA\[|\]\]>/g, "");
}

function extractRssTitles(xml, limit) {
  const titles = [];
  const re = /<title>([^<]+)<\/title>/gi;
  let match;
  while ((match = re.exec(xml)) && titles.length < (limit || 30)) {
    titles.push(decodeEntities(match[1]).trim());
  }
  return titles.slice(1);
}

function newsQueriesForNiche(niche) {
  const key = String(niche || "general").toLowerCase().trim();
  if (NICHE_NEWS_QUERIES[key]) return NICHE_NEWS_QUERIES[key];
  return [key + " news", key + " trending today", key + " latest"];
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(function () {
    controller.abort();
  }, timeoutMs || 8000);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: { ...DEFAULT_HEADERS, ...(options && options.headers) },
    });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchGoogleTrendsSnapshot() {
  const url =
    process.env.TRENDS_JSON_URL ||
    process.env.RESULTS_JSON_URL ||
    DEFAULT_TRENDS_JSON_URL;

  try {
    const resp = await fetchWithTimeout(url, { cache: "no-store" }, 10000);
    if (!resp.ok) {
      return { ok: false, error: "http_" + resp.status, results: [], emerging: [], product_trends: [] };
    }
    const data = await resp.json();
    return {
      ok: true,
      url: url,
      last_updated: data.last_updated || null,
      results: Array.isArray(data.results) ? data.results : [],
      emerging: Array.isArray(data.emerging) ? data.emerging : [],
      product_trends: Array.isArray(data.product_trends) ? data.product_trends : [],
      creator_insights: Array.isArray(data.creator_insights) ? data.creator_insights : [],
    };
  } catch (err) {
    return {
      ok: false,
      error: String(err && err.message ? err.message : err),
      results: [],
      emerging: [],
      product_trends: [],
    };
  }
}

async function fetchGoogleSuggest(seed, region) {
  const gl = region || "GB";
  const url =
    "https://suggestqueries.google.com/complete/search?client=firefox&q=" +
    encodeURIComponent(seed) +
    "&hl=en&gl=" +
    encodeURIComponent(gl);

  try {
    const resp = await fetchWithTimeout(url, {}, 5000);
    if (!resp.ok) return [];
    const data = await resp.json();
    if (!Array.isArray(data) || !Array.isArray(data[1])) return [];
    return data[1].map(function (item) {
      return Array.isArray(item) ? item[0] : item;
    });
  } catch {
    return [];
  }
}

function defaultSuggestSeeds(niche) {
  const n = String(niche || "general").toLowerCase().trim();
  return [
    n + " trending right now",
    n + " latest news today",
    n + " content ideas 2026",
    "best " + n + " tips today",
    n + " viral tiktok",
  ];
}

async function fetchGoogleSuggestTrends(niche, region) {
  const seeds = defaultSuggestSeeds(niche);
  const seen = {};
  const discovered = [];

  for (let i = 0; i < Math.min(4, seeds.length); i++) {
    const suggestions = await fetchGoogleSuggest(seeds[i], region);
    for (const s of suggestions) {
      const keyword = String(s || "").trim();
      if (!keyword) continue;
      const key = keyword.toLowerCase();
      if (seen[key]) continue;
      seen[key] = true;
      discovered.push({
        keyword: keyword.charAt(0).toUpperCase() + keyword.slice(1),
        source: "Google Suggest",
        source_keyword: seeds[i],
        rise_value: 120,
        discovery_type: "google_suggest",
        viral_score: Math.max(30, 75 - discovered.length * 3),
        rise_percent: Math.max(5, 35 - discovered.length * 2),
        search_volume: Math.max(15, 70 - discovered.length * 3),
        content_score: Math.max(25, 65 - discovered.length * 2),
      });
    }
  }

  return {
    ok: discovered.length > 0,
    results: discovered.slice(0, 15),
    error: discovered.length ? null : "no_suggestions",
  };
}

async function fetchRedditTrends() {
  const discovered = [];
  const seen = {};

  for (const sub of REDDIT_SUBREDDITS.slice(0, 4)) {
    try {
      const url = "https://www.reddit.com/r/" + sub + "/hot/.rss?limit=25";
      const resp = await fetchWithTimeout(url, {}, 8000);
      if (!resp.ok) continue;

      const titles = extractRssTitles(await resp.text(), 20);
      for (const titleRaw of titles) {
        const title = titleRaw.toLowerCase();
        if (title.length < 12) continue;
        const words = title.split(/\s+/);
        const clean = (words.length > 10 ? words.slice(0, 10).join(" ") : title).slice(0, 60).trim();
        if (!clean || seen[clean]) continue;
        seen[clean] = true;
        discovered.push({
          keyword: clean.charAt(0).toUpperCase() + clean.slice(1),
          source: "Reddit r/" + sub,
          source_keyword: "Reddit r/" + sub,
          rise_value: 200,
          discovery_type: "reddit",
          description: "Hot topic on r/" + sub,
        });
      }
    } catch {
      /* continue next subreddit */
    }
  }

  return {
    ok: discovered.length > 0,
    results: discovered.slice(0, 10),
    error: discovered.length ? null : "reddit_unavailable",
  };
}

async function fetchRssFeedItems(feedUrl, sourceName, limit) {
  const items = [];
  try {
    const resp = await fetchWithTimeout(feedUrl, {}, 8000);
    if (!resp.ok) return items;

    const xml = await resp.text();
    const titleRe = /<title>([^<]+)<\/title>/gi;
    const linkRe = /<link>([^<]+)<\/link>/gi;
    const pubRe = /<pubDate>([^<]+)<\/pubDate>/gi;

    const titles = [];
    let m;
    while ((m = titleRe.exec(xml))) titles.push(decodeEntities(m[1]).trim());

    const links = [];
    while ((m = linkRe.exec(xml))) links.push(m[1].trim());

    const pubs = [];
    while ((m = pubRe.exec(xml))) pubs.push(m[1].trim());

    for (let i = 1; i < Math.min(titles.length, (limit || 8) + 1); i++) {
      const title = titles[i];
      if (!title) continue;
      const cleanTitle = title.replace(/ - .*$/, "").trim();
      const pubDate = pubs[i - 1] ? new Date(pubs[i - 1]) : new Date();
      const hoursAgo = Math.max(0, Math.round((Date.now() - pubDate.getTime()) / 3600000));
      const sourceMatch = title.match(/ - (.+)$/);
      items.push({
        title: cleanTitle,
        source: sourceMatch ? sourceMatch[1] : sourceName || "News",
        link: links[i - 1] || links[i] || "",
        hoursAgo: hoursAgo,
        pubDate: pubDate.toISOString(),
      });
    }
  } catch {
    /* skip feed */
  }
  return items;
}

async function fetchBreakingNews(niche) {
  const queries = newsQueriesForNiche(niche);
  const allNews = [];
  const seen = {};

  for (let q = 0; q < Math.min(2, queries.length); q++) {
    const rssUrl =
      "https://news.google.com/rss/search?q=" +
      encodeURIComponent(queries[q]) +
      "&hl=en&gl=GB";
    const items = await fetchRssFeedItems(rssUrl, "Google News", 5);
    for (const item of items) {
      const key = item.title.toLowerCase();
      if (!item.title || seen[key]) continue;
      seen[key] = true;
      allNews.push(item);
    }
  }

  for (const pair of UK_NEWS_RSS_FEEDS.slice(0, 2)) {
    const items = await fetchRssFeedItems(pair[0], pair[1], 4);
    for (const item of items) {
      const key = item.title.toLowerCase();
      if (!item.title || seen[key]) continue;
      seen[key] = true;
      allNews.push(item);
    }
  }

  allNews.sort(function (a, b) {
    return a.hoursAgo - b.hoursAgo;
  });

  return {
    ok: allNews.length > 0,
    items: allNews.slice(0, 8),
    error: allNews.length ? null : "no_news",
  };
}

async function fetchNewsTrendKeywords(niche) {
  const news = await fetchBreakingNews(niche);
  const results = (news.items || []).map(function (item, idx) {
    return {
      keyword: item.title,
      source: item.source || "News RSS",
      source_keyword: "News RSS",
      rise_value: 180,
      discovery_type: "news",
      description: "Breaking news in " + (niche || "your niche"),
      viral_score: Math.max(35, 80 - idx * 4),
      rise_percent: Math.max(10, 45 - idx * 3),
    };
  });

  return {
    ok: results.length > 0,
    results: results,
    error: results.length ? null : news.error,
  };
}

async function fetchApifyTikTokPreview() {
  const token = process.env.APIFY_API_TOKEN || "";
  if (!token) {
    return { ok: false, skipped: true, error: "apify_token_missing", videos: [] };
  }

  const actorId = encodeURIComponent(
    process.env.APIFY_TIKTOK_ACTOR_ID || "clockworks/tiktok-scraper"
  );
  const hashtags = (process.env.TIKTOK_APIFY_HASHTAGS || "britishpride,patriotism")
    .split(",")
    .map(function (h) {
      return h.trim();
    })
    .filter(Boolean)
    .slice(0, 2);

  const input = {
    hashtags: hashtags,
    resultsPerPage: Number(process.env.TIKTOK_APIFY_RESULTS_PER_PAGE) || 5,
    shouldDownloadVideos: false,
    shouldDownloadCovers: false,
  };

  try {
    const runResp = await fetchWithTimeout(
      "https://api.apify.com/v2/acts/" + actorId + "/runs?token=" + encodeURIComponent(token),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
      15000
    );

    if (!runResp.ok) {
      return { ok: false, error: "apify_run_" + runResp.status, videos: [] };
    }

    const runData = await runResp.json();
    const runId = runData && runData.data && runData.data.id;
    const datasetId = runData && runData.data && runData.data.defaultDatasetId;
    if (!runId || !datasetId) {
      return { ok: false, error: "apify_run_invalid", videos: [] };
    }

    let status = "RUNNING";
    for (let attempt = 0; attempt < 8 && status === "RUNNING"; attempt++) {
      await new Promise(function (r) {
        setTimeout(r, 2000);
      });
      const statusResp = await fetchWithTimeout(
        "https://api.apify.com/v2/actor-runs/" +
          runId +
          "?token=" +
          encodeURIComponent(token),
        {},
        8000
      );
      if (!statusResp.ok) break;
      const statusData = await statusResp.json();
      status = (statusData && statusData.data && statusData.data.status) || "FAILED";
    }

    if (status !== "SUCCEEDED") {
      return { ok: false, error: "apify_status_" + status, videos: [] };
    }

    const itemsResp = await fetchWithTimeout(
      "https://api.apify.com/v2/datasets/" +
        datasetId +
        "/items?token=" +
        encodeURIComponent(token) +
        "&limit=10",
      {},
      10000
    );
    if (!itemsResp.ok) {
      return { ok: false, error: "apify_dataset_" + itemsResp.status, videos: [] };
    }

    const videos = await itemsResp.json();
    return {
      ok: Array.isArray(videos) && videos.length > 0,
      videos: Array.isArray(videos) ? videos : [],
      error: null,
    };
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err), videos: [] };
  }
}

function normalizeKeywordResult(item, niche, defaultSource) {
  if (!item || typeof item !== "object") return null;
  const keyword = String(item.keyword || "").trim();
  if (!keyword) return null;

  return {
    keyword: keyword.charAt(0).toUpperCase() + keyword.slice(1),
    viral_score: Number(item.viral_score) || 50,
    rise_percent: Number(item.rise_percent) || Number(item.rise_value) / 5 || 20,
    search_volume: Number(item.search_volume) || Math.min(99, 50 + (Number(item.viral_score) || 0) / 2),
    source: item.source || item.source_keyword || defaultSource || "Trend Intelligence",
    content_score: Number(item.content_score) || Number(item.viral_score) || 50,
    fresh: Number(item.fresh) || 55,
    emotion: Number(item.emotion) || 45,
    debate: Number(item.debate) || 35,
    product: item.product || "",
    trend_state: item.trend_state || item.discovery_type || "emerging",
    niche: niche || "general",
    discovery_type: item.discovery_type || null,
  };
}

function mergeProviderKeywords(providerLists, niche) {
  const keywordMap = {};
  const order = [];

  function addItem(item, defaultSource) {
    const normalized = normalizeKeywordResult(item, niche, defaultSource);
    if (!normalized) return;
    const key = normalized.keyword.toLowerCase();
    if (!keywordMap[key]) {
      keywordMap[key] = {
        ...normalized,
        platform_count: 1,
        sources: [normalized.source],
      };
      order.push(key);
    } else {
      const existing = keywordMap[key];
      existing.platform_count += 1;
      if (existing.sources.indexOf(normalized.source) === -1) {
        existing.sources.push(normalized.source);
      }
      existing.viral_score = Math.max(existing.viral_score, normalized.viral_score);
      existing.rise_percent = Math.max(existing.rise_percent, normalized.rise_percent);
      existing.content_score = Math.max(existing.content_score, normalized.content_score);
      if (existing.platform_count >= 2) {
        existing.viral_score = Math.min(95, Math.round(existing.viral_score * 1.15));
        existing.rise_percent = Math.min(99, Math.round(existing.rise_percent * 1.2));
      }
      existing.source = existing.sources.join(" + ");
    }
  }

  for (const batch of providerLists) {
    const list = (batch && batch.results) || [];
    const source = (batch && batch.source) || "provider";
    for (const item of list) addItem(item, source);
  }

  const results = order.map(function (k) {
    return keywordMap[k];
  });
  results.sort(function (a, b) {
    return (b.viral_score || 0) - (a.viral_score || 0);
  });

  const emerging = results.slice(5, 15).map(function (r) {
    return {
      keyword: r.keyword,
      source: r.source,
      source_keyword: r.source,
      discovery_type: r.discovery_type || "cross_platform",
      description: r.discovery_type
        ? "Discovered via " + r.discovery_type
        : "Emerging signal in " + (niche || "your niche"),
    };
  });

  const productTrends = results
    .filter(function (r) {
      return r.product;
    })
    .slice(0, 8)
    .map(function (r) {
      return {
        keyword: r.keyword,
        product: r.product,
        viral_score: r.viral_score,
        rise_percent: r.rise_percent,
        category: "product",
      };
    });

  return {
    results: results.slice(0, 20),
    emerging: emerging,
    product_trends: productTrends,
    creator_insights: [],
  };
}

module.exports = {
  fetchGoogleTrendsSnapshot,
  fetchGoogleSuggestTrends,
  fetchRedditTrends,
  fetchBreakingNews,
  fetchNewsTrendKeywords,
  fetchApifyTikTokPreview,
  mergeProviderKeywords,
  normalizeKeywordResult,
};
