/**
 * TikTok OAuth login URL generator (Login Kit).
 *
 * Required environment variables:
 *   TIKTOK_CLIENT_KEY
 *   TIKTOK_CLIENT_SECRET
 *   TIKTOK_REDIRECT_URI  (e.g. /api/tiktok-callback on your deployment host)
 */
export default async function handler(req, res) {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const redirectUri = process.env.TIKTOK_REDIRECT_URI;
  const state = req.query.state || "creatorradar";

  if (!clientKey || !redirectUri) {
    return res.status(500).json({ error: "TikTok credentials not configured" });
  }

  const scopes = ["user.info.basic", "video.upload"];
  const loginUrl =
    "https://www.tiktok.com/v2/auth/authorize/" +
    `?client_key=${encodeURIComponent(clientKey)}` +
    `&response_type=code` +
    `&scope=${encodeURIComponent(scopes.join(","))}` +
    `&redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&state=${encodeURIComponent(state)}`;

  res.writeHead(302, { Location: loginUrl });
  res.end();
}
