/**
 * Account-stage classification and audit output rules injected into
 * audience-intelligence report requests before they reach the model.
 */

export const AUDIT_STAGE_INSTRUCTIONS = `
MANDATORY FIRST STEP — ACCOUNT STAGE CLASSIFICATION (do this BEFORE any advice)
Analyse the account using all available signals: post scores, caption patterns, analytics/screenshot data (views, likes, comments, shares, followers if provided), and consistency of engagement.

Classify into exactly ONE stage:
- NO_TRACTION: very low real engagement — e.g. roughly 1–10 likes per post, very low views, no consistent audience response, flat or near-zero growth signals. Content may exist but the account has not yet found an audience.
- GROWING: consistent engagement signals — recurring likes/comments/shares, identifiable top vs weak posts, audience responding to specific themes/formats, or clear momentum even if modest.

STAGE-BASED ADVICE RULES
If NO_TRACTION:
- Do NOT give optimisation tips about hooks, hashtags, captions, CTA tweaks, or "polish what you have" advice. Those assume an audience already exists.
- Instead deliver a "Growth Starter Plan" focused on:
  1) Niche clarity / repositioning — who is this for, what unique angle, what to stop being vague about
  2) How to get initial reach — discovery mechanics, platform-native distribution, posting volume for learning
  3) Content format strategy for early growth — simple repeatable formats that work before you have followers
  4) First 10 post strategy — a sequenced plan for posts 1–10, not random posting
  5) Distribution tactics — trends, replies, collaborations, community entry points
- Leave hookInsight empty or use it only for niche-positioning (NOT hook optimisation).
- hookRecommendations: exactly ONE entry — the full Next Post Script (see below). No hook formula lists.
- doubleDown / stopPosting: frame around niche, reach, and distribution — NOT hook/hashtag/caption micro-optimisation.

If GROWING:
- Proceed with normal engagement/audit analysis: patterns, psychology, hooks, formats, what to double down on and what to stop.
- hookRecommendations may include formulas plus one Next Post Script entry.

STRICT OUTPUT STRUCTURE (map into the JSON schema you were given)
Populate these conceptual sections — use the JSON field mapping below so the report renders correctly:

1. Problem — put in "headline" (start with "Problem: ")
2. Stage — put in "growthVerdict" as exactly "Stage: NO_TRACTION" or "Stage: GROWING" (optionally add one short sentence after)
3. Why this stage — first item in "evidenceBullets" must start with "Why this stage: " and cite the engagement signals you used
4. Action Plan — put in "thirtyDayPlan":
   - NO_TRACTION: title the plan implicitly as Growth Starter Plan; week1=niche clarity & repositioning, week2=initial reach & distribution, week3=content format strategy + first 10 post sequence (posts 1–5), week4=first 10 post sequence (posts 6–10) + collaborations/trends/replies
   - GROWING: standard 4-week optimisation plan (week1 quick wins, week2 build, week3 experiment, week4 scale)
5. 3 Content Ideas — exactly 3 objects in "contentIdeas" (tailored to stage; NO_TRACTION ideas should prioritise reach/discovery, not hook polish)
6. 1 Next Post Script — exactly one full ready-to-post script in hookRecommendations[0]: use "formula" for a short label, "example" for the complete script (caption + visual/format note), "why" for why this fits their stage

Also set these optional fields when present in the schema:
- "stage": "NO_TRACTION" or "GROWING"
- "stageReason": one paragraph explaining the classification
- "problem": same as headline without the "Problem: " prefix
- "nextPostScript": duplicate of the full script from hookRecommendations[0].example

Additional bullets in evidenceBullets (after "Why this stage") should support the Action Plan for the classified stage. Never contradict the stage classification.
`.trim();

function messageText(messages, role) {
  if (!Array.isArray(messages)) return "";
  const match = messages.find((m) => m && m.role === role);
  return typeof match?.content === "string" ? match.content : "";
}

export function isAuditReportRequest(body) {
  const messages = body?.messages;
  if (!Array.isArray(messages) || messages.length === 0) return false;

  const system = messageText(messages, "system");
  const user = messageText(messages, "user");

  const isAuditSystem =
    /content strategist|social media strategist/i.test(system) &&
    /NEVER just list scores/i.test(system);

  const isAuditUser =
    /POST SCORES:/i.test(user) &&
    /Return ONLY valid JSON/i.test(user) &&
    /Analyze this (creator|local business)/i.test(user);

  return isAuditSystem && isAuditUser;
}

export function augmentAuditMessages(body) {
  if (!isAuditReportRequest(body)) return body;

  const messages = body.messages.map((m) => ({ ...m }));
  const systemIdx = messages.findIndex((m) => m.role === "system");

  if (systemIdx >= 0) {
    const existing = messages[systemIdx].content || "";
    if (!existing.includes("MANDATORY FIRST STEP — ACCOUNT STAGE CLASSIFICATION")) {
      messages[systemIdx] = {
        ...messages[systemIdx],
        content: `${existing}\n\n${AUDIT_STAGE_INSTRUCTIONS}`,
      };
    }
  } else {
    messages.unshift({ role: "system", content: AUDIT_STAGE_INSTRUCTIONS });
  }

  return { ...body, messages };
}
