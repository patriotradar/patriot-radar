const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const GEMINI_OPENAI_URL =
  "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions";

const DEFAULT_MODEL = process.env.GEMINI_MODEL || "gemini-2.0-flash";
const GROQ_TIMEOUT_MS = 30000;

function setCorsHeaders(res, origin) {
  const allowed = process.env.ALLOWED_ORIGIN || "*";
  const allowOrigin =
    allowed === "*" ? "*" : origin === allowed ? origin : allowed;

  res.setHeader("Access-Control-Allow-Origin", allowOrigin);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  res.setHeader("Access-Control-Max-Age", "86400");
}

function mapModel(clientModel) {
  if (typeof clientModel === "string" && clientModel.startsWith("gemini-")) {
    return clientModel;
  }
  return DEFAULT_MODEL;
}

async function callProvider(url, apiKey, payload, timeoutMs) {
  const options = {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
  };
  if (timeoutMs) {
    options.signal = AbortSignal.timeout(timeoutMs);
  }

  const upstream = await fetch(url, options);

  const text = await upstream.text();
  return { status: upstream.status, text };
}

export default async function handler(req, res) {
  const origin = req.headers.origin || "";

  if (req.method === "OPTIONS") {
    setCorsHeaders(res, origin);
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    setCorsHeaders(res, origin);
    return res.status(405).json({ error: { message: "Method not allowed" } });
  }

  const groqKey = process.env.GROQ_API_KEY;
  const geminiKey = process.env.GEMINI_API_KEY;
  if (!groqKey && !geminiKey) {
    setCorsHeaders(res, origin);
    return res.status(500).json({
      error: { message: "GROQ_API_KEY or GEMINI_API_KEY must be configured" },
    });
  }

  setCorsHeaders(res, origin);

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      return res.status(400).json({ error: { message: "Invalid JSON body" } });
    }
  }

  if (!body || typeof body !== "object") {
    return res.status(400).json({ error: { message: "Request body required" } });
  }

  if (groqKey) {
    try {
      const groqResult = await callProvider(GROQ_URL, groqKey, body, GROQ_TIMEOUT_MS);
      if (groqResult.status === 200) {
        res.status(200);
        res.setHeader("Content-Type", "application/json");
        return res.end(groqResult.text);
      }
      console.error(
        "Groq upstream failed:",
        groqResult.status,
        groqResult.text.slice(0, 200)
      );
    } catch (err) {
      console.error("Groq proxy error:", err);
    }
  }

  if (!geminiKey) {
    return res.status(502).json({ error: { message: "Upstream request failed" } });
  }

  const payload = {
    ...body,
    model: mapModel(body.model),
  };

  try {
    const geminiResult = await callProvider(
      GEMINI_OPENAI_URL,
      geminiKey,
      payload,
      null
    );
    res.status(geminiResult.status);
    res.setHeader("Content-Type", "application/json");
    return res.end(geminiResult.text);
  } catch (err) {
    console.error("Gemini proxy error:", err);
    return res.status(502).json({ error: { message: "Upstream request failed" } });
  }
}
