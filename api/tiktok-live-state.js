/**
 * GET /api/tiktok-live-state?account_id=...
 * Returns assembleLiveState(account_id) — single deterministic UI contract.
 * Never throws; always returns the full contract with safe defaults.
 */

const { assembleLiveState } = require("./tiktok-live-state-assembler");

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");

  const accountId =
    (req.query && req.query.account_id) ||
    (req.body && req.body.account_id) ||
    "";

  try {
    const state = await assembleLiveState(String(accountId || ""));
    return res.status(200).json(state);
  } catch {
    const { emptyContract } = require("./tiktok-live-state-assembler");
    return res.status(200).json(emptyContract());
  }
};
