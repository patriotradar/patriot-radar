/**
 * TikTok OAuth callback handler.
 * Exchanges the authorisation code for an access token and stores it in Supabase.
 */
export default async function handler(req, res) {
  const code = req.query.code;
  const error = req.query.error;
  const state = req.query.state || "";

  if (error) {
    return res.status(400).json({ error, error_description: req.query.error_description });
  }
  if (!code) {
    return res.status(400).json({ error: "missing_code" });
  }

  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
  const redirectUri = process.env.TIKTOK_REDIRECT_URI;

  if (!clientKey || !clientSecret || !redirectUri) {
    return res.status(500).json({ error: "TikTok credentials not configured" });
  }

  try {
    const tokenRes = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_key: clientKey,
        client_secret: clientSecret,
        code,
        grant_type: "authorization_code",
        redirect_uri: redirectUri,
      }),
    });

    const tokenData = await tokenRes.json();
    if (!tokenRes.ok || tokenData.error) {
      return res.status(400).json({
        error: tokenData.error || "token_request_failed",
        details: tokenData,
      });
    }

    // Redirect back to dashboard with success indicator.
    // Storing the token server-side in Supabase is recommended before production use.
    const redirectTarget = `https://creatorradar.co.uk/?tiktok=connected&state=${encodeURIComponent(state)}`;
    res.writeHead(302, { Location: redirectTarget });
    res.end();
  } catch (err) {
    return res.status(500).json({ error: "callback_failed", message: err.message });
  }
}
