/**
 * GET /api/tiktok-live-state?account_id=...
 * Returns assembleLiveState(account_id) with server-derived RBAC access block.
 * Role is NEVER taken from query/body — only from validated Supabase JWT.
 */

const { assembleLiveState, emptyContract } = require("./tiktok-live-state-assembler");
const { resolveUserFromAuthHeader } = require("./tiktok-access-control");

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");

  const accountId =
    (req.query && req.query.account_id) || (req.body && req.body.account_id) || "";

  try {
    const userRecord = await resolveUserFromAuthHeader(req);
    const resolvedAccountId = String(
      accountId || (userRecord && userRecord.id) || ""
    );
    const state = await assembleLiveState(resolvedAccountId, userRecord);
    return res.status(200).json(state);
  } catch {
    return res.status(200).json(emptyContract());
  }
};
