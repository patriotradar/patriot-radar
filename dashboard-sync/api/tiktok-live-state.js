/**
 * TikTok live state API — returns assembled live state with features.commerce_mode.
 */
module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");

  if (req.method !== "GET") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  var accountId = (req.query && req.query.account_id) || "default";
  var commerceMode = String(req.query && req.query.commerce_mode || "false").toLowerCase() === "true";

  try {
    var spawnSync = require("child_process").spawnSync;
    var script = [
      "import json, sys",
      "from tiktok_live_state_assembler import assembleLiveState",
      "account_id = sys.argv[1]",
      "commerce_mode = sys.argv[2].lower() == 'true'",
      "print(json.dumps(assembleLiveState(account_id, commerce_mode=commerce_mode)))",
    ].join("\n");

    var result = spawnSync("python3", ["-c", script, accountId, String(commerceMode)], {
      cwd: process.cwd(),
      encoding: "utf-8",
      timeout: 15000,
    });

    if (result.status === 0 && result.stdout) {
      res.status(200).send(result.stdout.trim());
      return;
    }
  } catch (e) {
    /* fall through to safe default */
  }

  res.status(200).json({
    features: { commerce_mode: commerceMode },
    today_flow: {
      step: commerceMode ? "trend → product → content → queue" : "trend → content → plan → insights",
      next_action: "Run trend scan",
      status: "ready",
    },
    trends: [],
    products: [],
    inventory_gaps: [],
    inventory_prevention: [],
    content_queue: [],
    approvals: [],
    performance: {},
    alerts: [],
    revenue_suggestions: [],
    primary_action: { label: "View content plan", action: "view_plan", context_id: "plan" },
    system_health: "degraded",
  });
};
