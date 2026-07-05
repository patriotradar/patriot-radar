/**
 * AI Code Governance shared library (Node) — mirrors Python policy engine.
 */

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "..");

const BLOCKED_PATH_FRAGMENTS = [
  "trend_intelligence_engine/",
  "providers/",
  "api/",
  "sql/",
];

const BLOCKED_FILENAME_KEYWORDS = ["scoring", "dedupe", "dedup", "provider"];

const SAFE_FIX_PATTERNS = [
  "?.",
  "??",
  "|| ",
  "typeof ",
  "!= null",
  "!== null",
  "!== undefined",
  "Array.isArray",
  "try {",
  "catch (",
];

function isBlockedPath(filePath) {
  const normalized = String(filePath || "").replace(/\\/g, "/").toLowerCase();
  if (!normalized) return false;
  for (const fragment of BLOCKED_PATH_FRAGMENTS) {
    if (normalized.includes(fragment.toLowerCase())) return true;
  }
  const basename = normalized.split("/").pop() || "";
  for (const keyword of BLOCKED_FILENAME_KEYWORDS) {
    if (basename.includes(keyword)) return true;
  }
  return false;
}

function countDiffLines(diff) {
  let added = 0;
  let removed = 0;
  for (const line of String(diff || "").split("\n")) {
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) continue;
    if (line.startsWith("+")) added += 1;
    else if (line.startsWith("-")) removed += 1;
  }
  return { added, removed };
}

function touchesMultipleFiles(diff) {
  const files = new Set();
  for (const line of String(diff || "").split("\n")) {
    if (line.startsWith("+++ ") || line.startsWith("--- ")) {
      let p = line.slice(4).trim();
      if (p.startsWith("b/") || p.startsWith("a/")) p = p.slice(2);
      if (p && p !== "/dev/null") files.add(p);
    }
  }
  return files.size > 1;
}

function classifyRisk({ sourceFile, proposedFix, issue }) {
  if (isBlockedPath(sourceFile)) return "BLOCKED";
  const diff = proposedFix || "";
  if (touchesMultipleFiles(diff)) return "BLOCKED";
  const { added, removed } = countDiffLines(diff);
  if (added === 0 && removed === 0) return "REVIEW";
  if (added + removed > 2) return "REVIEW";
  const combined = (diff + (issue || "")).toLowerCase();
  if (["schema", "migration", "alter table", "create table"].some((k) => combined.includes(k))) {
    return "BLOCKED";
  }
  if (["dedup", "dedupe", "provider", "scoring"].some((k) => combined.includes(k))) {
    return "BLOCKED";
  }
  if (added <= 1 && removed <= 1) {
    const addedContent = diff
      .split("\n")
      .filter((l) => l.startsWith("+") && !l.startsWith("+++"))
      .map((l) => l.slice(1))
      .join("");
    if (SAFE_FIX_PATTERNS.some((p) => addedContent.includes(p))) return "SAFE";
  }
  return "REVIEW";
}

function computeAutoApplicable({ risk, geminiStatus, sourceFile }) {
  return risk === "SAFE" && geminiStatus === "APPROVED" && !isBlockedPath(sourceFile);
}

function canApplyFix(issue) {
  const reasons = [];
  if (issue.risk !== "SAFE") reasons.push("risk is not SAFE");
  if (issue.gemini_status !== "APPROVED") reasons.push("gemini_status is not APPROVED");
  if (isBlockedPath(issue.source_file)) reasons.push("blocked path");
  if (!String(issue.proposed_fix || "").trim()) reasons.push("empty proposed fix");
  if (touchesMultipleFiles(issue.proposed_fix)) reasons.push("multi-file diff");
  const { added, removed } = countDiffLines(issue.proposed_fix);
  if (added > 1 || removed > 1) reasons.push("diff exceeds single-line SAFE limit");
  return { allowed: reasons.length === 0, reasons };
}

function parseUnifiedDiff(diff) {
  const hunks = [];
  let currentFile = "";
  let currentHunk = null;

  for (const line of String(diff || "").split("\n")) {
    if (line.startsWith("+++ ")) {
      let p = line.slice(4).trim();
      if (p.startsWith("b/")) p = p.slice(2);
      currentFile = p;
      continue;
    }
    if (line.startsWith("@@")) {
      if (currentHunk) hunks.push(currentHunk);
      const m = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (!m) continue;
      currentHunk = { file: currentFile, oldStart: parseInt(m[1], 10), lines: [] };
      continue;
    }
    if (currentHunk && (line.startsWith("+") || line.startsWith("-") || line.startsWith(" "))) {
      currentHunk.lines.push(line);
    }
  }
  if (currentHunk) hunks.push(currentHunk);
  return hunks;
}

function applySafePatch(issue) {
  const check = canApplyFix(issue);
  if (!check.allowed) {
    return { success: false, error: check.reasons.join("; ") };
  }

  const hunks = parseUnifiedDiff(issue.proposed_fix);
  if (!hunks.length) {
    return { success: false, error: "Could not parse unified diff" };
  }

  const appliedFiles = [];
  try {
    for (const hunk of hunks) {
      const relPath = hunk.file || issue.source_file || "";
      if (!relPath || isBlockedPath(relPath)) {
        return { success: false, error: "Blocked or missing target file" };
      }
      const target = path.resolve(REPO_ROOT, relPath);
      if (!target.startsWith(path.resolve(REPO_ROOT))) {
        return { success: false, error: "Path traversal blocked" };
      }
      if (!fs.existsSync(target)) {
        return { success: false, error: "File not found: " + relPath };
      }

      const content = fs.readFileSync(target, "utf8");
      const lines = content.split(/(?<=\n)/);
      if (!content.endsWith("\n") && lines.length) {
        lines[lines.length - 1] = lines[lines.length - 1];
      }

      const newLines = [];
      let idx = 0;
      let lineNo = 0;
      const oldStart = hunk.oldStart - 1;

      while (lineNo < oldStart && idx < lines.length) {
        newLines.push(lines[idx]);
        idx += 1;
        lineNo += 1;
      }

      for (const hline of hunk.lines) {
        if (hline.startsWith(" ")) {
          if (idx >= lines.length) return { success: false, error: "Context mismatch" };
          newLines.push(lines[idx]);
          idx += 1;
        } else if (hline.startsWith("-")) {
          if (idx >= lines.length) return { success: false, error: "Remove line mismatch" };
          idx += 1;
        } else if (hline.startsWith("+")) {
          const added = hline.slice(1);
          newLines.push(added.endsWith("\n") ? added : added + "\n");
        }
      }

      while (idx < lines.length) {
        newLines.push(lines[idx]);
        idx += 1;
      }

      fs.writeFileSync(target, newLines.join(""), "utf8");
      appliedFiles.push(relPath);
    }

    return { success: true, files: appliedFiles, message: "Applied patch to " + appliedFiles.join(", ") };
  } catch (err) {
    return { success: false, error: String(err.message || err) };
  }
}

function getSupabaseConfig() {
  return {
    url: (
      process.env.SUPABASE_URL ||
      process.env.NEXT_PUBLIC_SUPABASE_URL ||
      ""
    ).replace(/\/$/, ""),
    serviceKey: process.env.SUPABASE_SERVICE_ROLE_KEY || "",
    anonKey:
      process.env.SUPABASE_ANON_KEY ||
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
      "",
  };
}

function governanceTable() {
  return process.env.AI_GOVERNANCE_TABLE || "cr_ai_governance_issues";
}

async function supabaseRequest(method, query, body, authToken) {
  const cfg = getSupabaseConfig();
  const bearer = authToken || cfg.serviceKey || cfg.anonKey;
  const url = cfg.url + "/rest/v1/" + governanceTable() + (query || "");

  const resp = await fetch(url, {
    method,
    headers: {
      apikey: cfg.anonKey || cfg.serviceKey,
      Authorization: "Bearer " + bearer,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error("Supabase " + method + " failed (" + resp.status + "): " + text.slice(0, 300));
  }

  const text = await resp.text();
  return text ? JSON.parse(text) : [];
}

async function listGovernanceIssues(limit) {
  const query =
    "?select=*&order=created_at.desc&limit=" + encodeURIComponent(String(limit || 50));
  const rows = await supabaseRequest("GET", query);
  return Array.isArray(rows) ? rows : [];
}

async function getGovernanceIssue(id, authToken) {
  const query = "?select=*&id=eq." + encodeURIComponent(id) + "&limit=1";
  const rows = await supabaseRequest("GET", query, null, authToken);
  return Array.isArray(rows) && rows.length ? rows[0] : null;
}

async function updateGovernanceIssue(id, updates, authToken) {
  const query = "?id=eq." + encodeURIComponent(id);
  const payload = Object.assign({}, updates, { updated_at: new Date().toISOString() });
  const rows = await supabaseRequest("PATCH", query, payload, authToken);
  return Array.isArray(rows) && rows.length ? rows[0] : null;
}

function toIssueOutput(row) {
  return {
    id: row.id,
    issue: row.issue || "",
    root_cause: row.root_cause || "",
    risk: row.risk || "REVIEW",
    proposed_fix: row.proposed_fix || "",
    gemini_status: row.gemini_status || "PENDING",
    warnings: row.warnings || [],
    auto_applicable: Boolean(row.auto_applicable),
    source_file: row.source_file || "",
    scan_source: row.scan_source || "",
    admin_status: row.admin_status || "pending",
    apply_error: row.apply_error || "",
    admin_email: row.admin_email || "",
    created_at: row.created_at,
    updated_at: row.updated_at,
    applied_at: row.applied_at,
  };
}

module.exports = {
  isBlockedPath,
  classifyRisk,
  computeAutoApplicable,
  canApplyFix,
  applySafePatch,
  listGovernanceIssues,
  getGovernanceIssue,
  updateGovernanceIssue,
  toIssueOutput,
  getSupabaseConfig,
  governanceTable,
};
