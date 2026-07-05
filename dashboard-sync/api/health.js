/** Lightweight health check for Vercel deployment verification. */
module.exports = function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ status: "ok" });
};
