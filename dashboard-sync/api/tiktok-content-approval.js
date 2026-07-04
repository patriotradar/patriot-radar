/**
 * Content approval API for dashboard orchestration.
 * POST /api/tiktok-content-approval  { content_id, decision }
 */

const { approveQueuedContent } = require("./tiktok-live-dashboard-state");

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");

  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ success: false, error: "method_not_allowed" });
  }

  try {
    const body = req.body || {};
    const contentId = String(body.content_id || "").trim();
    const decision = String(body.decision || "").trim().toLowerCase();
    const result = await approveQueuedContent(contentId, decision);
    return res.status(200).json(result);
  } catch (err) {
    return res.status(200).json({
      success: false,
      content_id: "",
      decision: "",
      status: "",
      error: String(err?.message || err),
    });
  }
};
