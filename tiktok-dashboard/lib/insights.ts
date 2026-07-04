export type InsightsResult = {
  pain_points: string[];
  questions: string[];
  content_opportunities: string[];
  hooks: string[];
  buying_signals: string[];
  summary: string;
};

const EMPTY_INSIGHTS: InsightsResult = {
  pain_points: [],
  questions: [],
  content_opportunities: [],
  hooks: [],
  buying_signals: [],
  summary: "",
};

const PAIN_PATTERNS = [
  /\b(confus(ed|ing)|frustrat(ed|ing)|doesn'?t work|not work|hate|annoying|misleading|scam|wrong|waste|struggling|difficult|hard to)\b/i,
  /\b(why is (this|it) so)\b/i,
  /\b(objection|skeptic|doubt)\b/i,
];

const QUESTION_PATTERNS = [
  /^(how|what|why|when|where|who|can|could|is|are|do|does)\b/i,
  /\?$/,
  /\b(can someone explain|explain please|what is this)\b/i,
];

const OPPORTUNITY_PATTERNS = [
  /\b(nobody (talks|mentions|explains)|no one (talks|mentions|explains))\b/i,
  /\b(wish someone|need a video|missing|underserved|never heard)\b/i,
  /\b(should make content|content idea|tutorial on)\b/i,
];

const BUYING_PATTERNS = [
  /\b(i need (this|it)|how much|where can i (get|buy)|does this work|link\??|send link|worth (it|buying)|take my money)\b/i,
  /\b(sign me up|interested|looking for|recommend)\b/i,
];

const HOOK_WORDS =
  /\b(pov|wait|best|honestly|nobody|secret|changed my|game changer|must see|you need)\b/i;

const STOP_WORDS = new Set([
  "the",
  "a",
  "an",
  "and",
  "or",
  "but",
  "in",
  "on",
  "at",
  "to",
  "for",
  "of",
  "is",
  "it",
  "this",
  "that",
  "with",
  "my",
  "your",
  "i",
  "you",
  "so",
  "just",
  "like",
  "im",
  "its",
  "be",
  "are",
  "was",
  "were",
  "have",
  "has",
  "had",
  "do",
  "does",
  "did",
  "can",
  "will",
  "would",
  "could",
  "should",
  "about",
  "from",
  "they",
  "them",
  "their",
  "we",
  "our",
  "me",
  "he",
  "she",
  "his",
  "her",
  "as",
  "if",
  "not",
  "no",
  "yes",
  "all",
  "get",
  "got",
  "one",
  "what",
  "how",
  "why",
  "when",
  "where",
  "who",
]);

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function normalizeInsights(raw: unknown): InsightsResult {
  if (!raw || typeof raw !== "object") {
    return { ...EMPTY_INSIGHTS };
  }

  const data = raw as Record<string, unknown>;
  return {
    pain_points: asStringArray(data.pain_points),
    questions: asStringArray(data.questions),
    content_opportunities: asStringArray(data.content_opportunities),
    hooks: asStringArray(data.hooks),
    buying_signals: asStringArray(data.buying_signals),
    summary: typeof data.summary === "string" ? data.summary.trim() : "",
  };
}

export function extractCommentTexts(comments: Record<string, unknown>[]): string[] {
  const texts: string[] = [];

  for (const item of comments) {
    const direct = item.text ?? item.comment ?? item.content ?? item.desc;
    if (typeof direct === "string" && direct.trim()) {
      texts.push(direct.trim());
    }

    for (const key of ["comments", "commentList", "replies"]) {
      const nested = item[key];
      if (!Array.isArray(nested)) {
        continue;
      }
      for (const entry of nested) {
        if (typeof entry !== "object" || entry === null) {
          continue;
        }
        const nestedText =
          (entry as Record<string, unknown>).text ??
          (entry as Record<string, unknown>).comment ??
          (entry as Record<string, unknown>).content;
        if (typeof nestedText === "string" && nestedText.trim()) {
          texts.push(nestedText.trim());
        }
      }
    }
  }

  return texts;
}

function matchesAny(text: string, patterns: RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(text));
}

function dedupeInsights(items: string[], limit = 8): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const item of items) {
    const key = item.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(item);
    if (result.length >= limit) {
      break;
    }
  }

  return result;
}

function toBusinessPhrase(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 120) {
    return cleaned.endsWith(".") ? cleaned : `${cleaned}.`;
  }
  return `${cleaned.slice(0, 117)}...`;
}

function topKeywordThemes(texts: string[], minCount = 2): string[] {
  const counts = new Map<string, number>();

  for (const text of texts) {
    const words = text
      .toLowerCase()
      .replace(/[^a-z0-9\s']/g, " ")
      .split(/\s+/)
      .filter((word) => word.length > 3 && !STOP_WORDS.has(word));

    const unique = new Set(words);
    for (const word of unique) {
      counts.set(word, (counts.get(word) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .filter(([, count]) => count >= minCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([word, count]) => `${word} (mentioned ${count} times)`);
}

function buildFallbackSummary(
  niche: string,
  insights: Omit<InsightsResult, "summary">,
  commentCount: number,
): string {
  const parts: string[] = [];

  parts.push(
    `We analyzed ${commentCount} TikTok comments in the "${niche}" niche to see what people care about right now.`,
  );

  if (insights.pain_points.length > 0) {
    parts.push(
      `The biggest friction points are around ${insights.pain_points[0].replace(/\.$/, "").toLowerCase()}.`,
    );
  }

  if (insights.questions.length > 0) {
    parts.push(
      `Viewers are actively asking for clarity, especially: "${insights.questions[0].replace(/\.$/, "")}".`,
    );
  }

  if (insights.content_opportunities.length > 0) {
    parts.push(
      `There is a clear content gap you can fill: ${insights.content_opportunities[0].replace(/\.$/, "").toLowerCase()}.`,
    );
  } else if (insights.buying_signals.length > 0) {
    parts.push(
      `People are showing purchase intent, including interest in ${insights.buying_signals[0].replace(/\.$/, "").toLowerCase()}.`,
    );
  } else {
    parts.push(
      "Focus on short, direct videos that answer common questions in plain language.",
    );
  }

  return parts.slice(0, 5).join(" ");
}

export function generateInsightsFallback(
  commentTexts: string[],
  niche: string,
): InsightsResult {
  if (commentTexts.length === 0) {
    return {
      ...EMPTY_INSIGHTS,
      summary: `No comments were available to analyze for "${niche}" yet. Run another scan when more discussion appears on trending videos.`,
    };
  }

  const painCandidates: string[] = [];
  const questionCandidates: string[] = [];
  const opportunityCandidates: string[] = [];
  const hookCandidates: string[] = [];
  const buyingCandidates: string[] = [];

  for (const text of commentTexts) {
    if (matchesAny(text, PAIN_PATTERNS)) {
      painCandidates.push(toBusinessPhrase(text));
    }
    if (matchesAny(text, QUESTION_PATTERNS) || text.includes("?")) {
      questionCandidates.push(toBusinessPhrase(text));
    }
    if (matchesAny(text, OPPORTUNITY_PATTERNS)) {
      opportunityCandidates.push(toBusinessPhrase(text));
    }
    if (matchesAny(text, BUYING_PATTERNS)) {
      buyingCandidates.push(toBusinessPhrase(text));
    }
    if (text.length <= 80 && HOOK_WORDS.test(text)) {
      hookCandidates.push(toBusinessPhrase(text));
    }
  }

  const themes = topKeywordThemes(commentTexts);
  if (themes.length > 0 && opportunityCandidates.length < 3) {
    opportunityCandidates.push(
      `Create explainer content around recurring topics: ${themes.slice(0, 3).join(", ")}.`,
    );
  }

  if (hookCandidates.length < 3) {
    const shortLines = commentTexts
      .filter((text) => text.length >= 20 && text.length <= 70)
      .slice(0, 5)
      .map(toBusinessPhrase);
    hookCandidates.push(...shortLines);
  }

  const pain_points = dedupeInsights(painCandidates);
  const questions = dedupeInsights(questionCandidates);
  const content_opportunities = dedupeInsights(opportunityCandidates);
  const hooks = dedupeInsights(hookCandidates);
  const buying_signals = dedupeInsights(buyingCandidates);

  const partial = { pain_points, questions, content_opportunities, hooks, buying_signals };
  const summary = buildFallbackSummary(niche, partial, commentTexts.length);

  return { ...partial, summary };
}

async function generateInsightsWithLLM(
  commentTexts: string[],
  niche: string,
  videoCaptions: string[],
): Promise<InsightsResult | null> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || commentTexts.length === 0) {
    return null;
  }

  const model = process.env.OPENAI_MODEL ?? "gpt-4o-mini";
  const commentsSample = commentTexts.slice(0, 150).join("\n");
  const captionsSample = videoCaptions.filter(Boolean).slice(0, 10).join("\n");

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        temperature: 0.3,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content: [
              "You turn TikTok comments into business insights for non-technical clients.",
              "Return JSON only with keys: pain_points, questions, content_opportunities, hooks, buying_signals (string arrays, max 8 each), summary (3-5 sentences).",
              "Write in plain, actionable English. No jargon.",
              'Good: "People are struggling to understand pricing and setup".',
              'Bad: "high engagement comment cluster detected".',
            ].join(" "),
          },
          {
            role: "user",
            content: `Niche: ${niche}\n\nTop video captions:\n${captionsSample || "(none)"}\n\nComments:\n${commentsSample}`,
          },
        ],
      }),
    });

    if (!response.ok) {
      return null;
    }

    const json = (await response.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const content = json.choices?.[0]?.message?.content;
    if (!content) {
      return null;
    }

    return normalizeInsights(JSON.parse(content));
  } catch {
    return null;
  }
}

export type GenerateInsightsInput = {
  comments: Record<string, unknown>[];
  niche: string;
  videoCaptions?: string[];
};

export async function generateInsights({
  comments,
  niche,
  videoCaptions = [],
}: GenerateInsightsInput): Promise<InsightsResult> {
  const commentTexts = extractCommentTexts(comments);

  const llmInsights = await generateInsightsWithLLM(commentTexts, niche, videoCaptions);
  if (llmInsights) {
    return normalizeInsights(llmInsights);
  }

  return generateInsightsFallback(commentTexts, niche);
}
