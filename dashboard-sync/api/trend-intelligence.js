/**
 * Route alias for /api/trend-intelligence — delegates to the live state handler.
 * Keeps a stable public path without duplicating backend logic.
 */
module.exports = require("./tiktok-live-state");
