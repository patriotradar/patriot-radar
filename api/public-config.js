/** Public runtime config for static dashboard (Supabase anon credentials only). */
module.exports = function handler(req, res) {
  const config = {
    supabaseUrl:
      process.env.NEXT_PUBLIC_SUPABASE_URL ||
      process.env.SUPABASE_URL ||
      "https://kdwqnlgdanzigpdwyqbh.supabase.co",
    supabaseAnonKey:
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
      process.env.SUPABASE_ANON_KEY ||
      "sb_publishable_7WtTtv9S4dl5jO-YE9QXRg_Ldy3gU_G",
  };

  res.setHeader("Content-Type", "application/javascript; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).send("window.__SUPABASE_CONFIG__=" + JSON.stringify(config) + ";");
};
