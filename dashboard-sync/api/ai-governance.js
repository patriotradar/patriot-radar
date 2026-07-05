/**
 * AI Code Governance API
 * GET  /api/ai-governance — list issues (admin)
 * POST /api/ai-governance — approve | reject | trigger_scan
 */

const { spawn } = require("child_process");
const path = require("path");
const {
  applySafePatch,
  canApplyFix,
  getGovernanceIssue,
  listGovernanceIssues,
  toIssueOutput,
  updateGovernanceIssue,
} = require("./ai-governance-lib");
const { getUserRole, resolveUserFromAuthHeader } = require("./tiktok-access-control");

function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGIN || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  res.setHeader("Cache-Control", "no-store");
}

async function requireAdmin(req) {
  const user = await resolveUserFromAuthHeader(req);
  if (!user) return { ok: false, status: 401, error: "unauthorized" };
  const role = getUserRole("", user);
  if (role !== "admin") return { ok: false, status: 403, error: "admin_required" };
  return { ok: true, user };
}

function runPythonScan() {
  return new Promise((resolve) => {
    const script = path.join(__dirname, "..", "scripts", "run_ai_governance_scan.py");
    const proc = spawn("python3", [script, "--json"], {
      cwd: path.join(__dirname, ".."),
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    proc.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    proc.on("close", (code) => {
      if (code !== 0) {
        resolve({ success: false, error: stderr || "scan failed", results: [] });
        return;
      }
      try {
        const results = JSON.parse(stdout || "[]");
        resolve({ success: true, results });
      } catch {
        resolve({ success: false, error: "invalid scan output", results: [] });
      }
    });
  });
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  setCors(res);

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  const auth = await requireAdmin(req);
  if (!auth.ok) {
    return res.status(auth.status).json({ success: false, error: auth.error });
  }

  const authToken =
    (req.headers.authorization || req.headers.Authorization || "").replace(/^Bearer\s+/i, "") || "";

  try {
    if (req.method === "GET") {
      const limit = parseInt((req.query && req.query.limit) || "50", 10) || 50;
      const rows = await listGovernanceIssues(limit);
      return res.status(200).json({
        success: true,
        issues: rows.map(toIssueOutput),
      });
    }

    if (req.method !== "POST") {
      return res.status(405).json({ success: false, error: "method_not_allowed" });
    }

    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
    const action = String(body.action || "").trim().toLowerCase();

    if (action === "scan") {
      const scan = await runPythonScan();
      return res.status(200).json({
        success: scan.success,
        issues: scan.results || [],
        error: scan.error || "",
      });
    }

    const issueId = String(body.issue_id || "").trim();
    if (!issueId) {
      return res.status(400).json({ success: false, error: "issue_id_required" });
    }

    const issue = await getGovernanceIssue(issueId, authToken);
    if (!issue) {
      return res.status(404).json({ success: false, error: "issue_not_found" });
    }

    if (action === "reject") {
      const updated = await updateGovernanceIssue(
        issueId,
        {
          admin_status: "rejected",
          admin_email: auth.user.email || "",
        },
        authToken
      );
      return res.status(200).json({ success: true, issue: toIssueOutput(updated) });
    }

    if (action === "approve") {
      const normalized = toIssueOutput(issue);

      if (normalized.risk !== "SAFE") {
        return res.status(200).json({
          success: false,
          error: "only_safe_fixes_can_be_approved_for_auto_apply",
          issue: normalized,
        });
      }
      if (normalized.gemini_status !== "APPROVED") {
        return res.status(200).json({
          success: false,
          error: "gemini_not_approved",
          issue: normalized,
        });
      }

      const check = canApplyFix(normalized);
      if (!check.allowed) {
        return res.status(200).json({
          success: false,
          error: check.reasons.join("; "),
          issue: normalized,
        });
      }

      await updateGovernanceIssue(
        issueId,
        {
          admin_status: "approved",
          admin_email: auth.user.email || "",
        },
        authToken
      );

      const patchResult = applySafePatch(normalized);
      if (!patchResult.success) {
        const failed = await updateGovernanceIssue(
          issueId,
          {
            admin_status: "failed",
            apply_error: patchResult.error || "patch failed",
          },
          authToken
        );
        return res.status(200).json({
          success: false,
          error: patchResult.error,
          issue: toIssueOutput(failed),
        });
      }

      const applied = await updateGovernanceIssue(
        issueId,
        {
          admin_status: "applied",
          applied_at: new Date().toISOString(),
          apply_error: "",
        },
        authToken
      );

      return res.status(200).json({
        success: true,
        message: patchResult.message,
        files: patchResult.files,
        issue: toIssueOutput(applied),
      });
    }

    return res.status(400).json({ success: false, error: "invalid_action" });
  } catch (err) {
    return res.status(200).json({
      success: false,
      error: String(err.message || err),
      issues: [],
    });
  }
};
