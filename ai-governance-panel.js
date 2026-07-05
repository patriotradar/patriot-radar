/**
 * AI Code Governance Panel — admin dashboard section.
 * Displays detected issues, diffs, Gemini validation, and approval controls.
 */
(function () {
  "use strict";

  var RISK_COLORS = {
    SAFE: "var(--green)",
    REVIEW: "var(--amber)",
    BLOCKED: "#ff4757",
  };

  var GEMINI_COLORS = {
    APPROVED: "var(--green)",
    REJECTED: "#ff4757",
    PENDING: "var(--muted)",
  };

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function getAuthHeaders() {
    var headers = { "Content-Type": "application/json" };
    if (typeof supabaseClient !== "undefined" && supabaseClient.auth) {
      return supabaseClient.auth.getSession().then(function (res) {
        var token = res.data && res.data.session && res.data.session.access_token;
        if (token) headers.Authorization = "Bearer " + token;
        return headers;
      });
    }
    return Promise.resolve(headers);
  }

  function governanceApi(method, body) {
    return getAuthHeaders().then(function (headers) {
      return fetch("/api/ai-governance", {
        method: method,
        headers: headers,
        body: body ? JSON.stringify(body) : undefined,
      }).then(function (r) {
        return r.json();
      });
    });
  }

  function renderGovernancePanelShell() {
    return (
      '<div class="card" style="margin-bottom:16px;border:1px solid rgba(0,255,136,.15)">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<div>' +
      '<h2 style="font-size:14px;color:var(--green);margin-bottom:4px">&#129302; AI Code Governance Panel</h2>' +
      '<p style="font-size:10px;color:var(--muted)">Monitored issues, proposed fixes, Gemini validation — explicit approval required</p>' +
      "</div>" +
      '<button id="governanceScanBtn" onclick="AiGovernancePanel.runScan()" style="padding:8px 14px;border-radius:8px;border:none;background:var(--green);color:#000;font-weight:700;font-size:11px;cursor:pointer">RUN SCAN</button>' +
      "</div>" +
      '<div id="governancePanelStatus" style="font-size:10px;color:var(--muted);margin-bottom:10px"></div>' +
      '<div id="governanceIssuesList"><p style="color:var(--muted);font-size:12px">Loading governance queue...</p></div>' +
      "</div>"
    );
  }

  function renderIssueCard(item, idx) {
    var riskCol = RISK_COLORS[item.risk] || "var(--muted)";
    var gemCol = GEMINI_COLORS[item.gemini_status] || "var(--muted)";
    var autoBadge = item.auto_applicable
      ? '<span style="font-size:8px;padding:2px 6px;border-radius:3px;background:rgba(0,255,136,.1);color:var(--green);margin-left:6px">AUTO-ELIGIBLE</span>'
      : '<span style="font-size:8px;padding:2px 6px;border-radius:3px;background:rgba(255,71,87,.08);color:#ff4757;margin-left:6px">MANUAL ONLY</span>';

    var warnings = item.warnings || [];
    var warnHtml = "";
    if (warnings.length) {
      warnHtml =
        '<div style="margin-top:8px;padding:8px;background:rgba(255,140,0,.05);border:1px solid rgba(255,140,0,.15);border-radius:6px">' +
        '<div style="font-size:9px;color:var(--amber);font-weight:700;margin-bottom:4px">WARNINGS</div>';
      for (var w = 0; w < warnings.length; w++) {
        warnHtml += '<div style="font-size:9px;color:var(--muted)">• ' + escapeHtml(warnings[w]) + "</div>";
      }
      warnHtml += "</div>";
    }

    var adminStatus = item.admin_status || "pending";
    var statusCol =
      adminStatus === "applied"
        ? "var(--green)"
        : adminStatus === "failed"
          ? "#ff4757"
          : adminStatus === "approved"
            ? "var(--blue)"
            : "var(--muted)";

    var canApprove =
      adminStatus === "pending" &&
      item.risk === "SAFE" &&
      item.gemini_status === "APPROVED" &&
      item.auto_applicable;
    var canReject = adminStatus === "pending";

    var h = '<div style="padding:12px;border:1px solid rgba(0,255,136,.12);border-radius:10px;margin-bottom:10px;background:rgba(0,255,136,.02)">';
    h += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;flex-wrap:wrap;gap:6px">';
    h += '<div style="font-size:12px;font-weight:800;color:var(--white);max-width:70%">' + escapeHtml(item.issue) + autoBadge + "</div>";
    h += '<span style="font-size:9px;padding:3px 8px;border-radius:4px;background:rgba(0,255,136,.08);color:' + statusCol + ';font-weight:700;text-transform:uppercase">' + escapeHtml(adminStatus) + "</span>";
    h += "</div>";

    h += '<div style="font-size:10px;color:var(--muted);margin-bottom:4px">Root cause: ' + escapeHtml(item.root_cause) + "</div>";
    if (item.source_file) {
      h += '<div style="font-size:9px;color:var(--muted);margin-bottom:4px">File: ' + escapeHtml(item.source_file) + " | Source: " + escapeHtml(item.scan_source) + "</div>";
    }

    h += '<div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">';
    h += '<span style="font-size:9px;padding:3px 8px;border-radius:4px;border:1px solid ' + riskCol + ";color:" + riskCol + '">RISK: ' + escapeHtml(item.risk) + "</span>";
    h += '<span style="font-size:9px;padding:3px 8px;border-radius:4px;border:1px solid ' + gemCol + ";color:" + gemCol + '">GEMINI: ' + escapeHtml(item.gemini_status) + "</span>";
    h += "</div>";

    h += warnHtml;

    h += '<div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">';
    h += '<button onclick="AiGovernancePanel.viewDiff(' + idx + ')" style="padding:6px 12px;font-size:10px;background:rgba(99,102,241,.12);color:#a5b4fc;border:1px solid rgba(99,102,241,.25);border-radius:6px;cursor:pointer;font-weight:700">VIEW DIFF</button>';
    if (canApprove) {
      h +=
        '<button onclick="AiGovernancePanel.approve(\'' +
        escapeHtml(item.id) +
        '\')" style="padding:6px 12px;font-size:10px;background:var(--green);color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:700">APPROVE</button>';
    }
    if (canReject) {
      h +=
        '<button onclick="AiGovernancePanel.reject(\'' +
        escapeHtml(item.id) +
        '\')" style="padding:6px 12px;font-size:10px;background:rgba(255,71,87,.08);color:#ff4757;border:1px solid rgba(255,71,87,.2);border-radius:6px;cursor:pointer;font-weight:600">REJECT</button>';
    }
    h += "</div>";

    if (item.apply_error) {
      h += '<div style="font-size:9px;color:#ff4757;margin-top:6px">Apply error: ' + escapeHtml(item.apply_error) + "</div>";
    }

    h += "</div>";
    return h;
  }

  function renderIssuesList(issues) {
    var container = document.getElementById("governanceIssuesList");
    if (!container) return;

    window._governanceIssues = issues || [];

    if (!issues || !issues.length) {
      container.innerHTML =
        '<p style="color:var(--muted);font-size:11px">No governance issues in queue. Run a scan to detect issues from tests, health checks, and logs.</p>';
      return;
    }

    var h = '<div style="font-size:10px;color:var(--muted);margin-bottom:10px">' + issues.length + " issue(s) in queue</div>";
    for (var i = 0; i < issues.length; i++) {
      h += renderIssueCard(issues[i], i);
    }
    container.innerHTML = h;
  }

  function setStatus(msg, isError) {
    var el = document.getElementById("governancePanelStatus");
    if (!el) return;
    el.style.color = isError ? "#ff4757" : "var(--muted)";
    el.textContent = msg || "";
  }

  function loadIssues() {
    setStatus("Loading...");
    governanceApi("GET")
      .then(function (data) {
        if (!data.success) {
          setStatus(data.error || "Failed to load issues", true);
          renderIssuesList([]);
          return;
        }
        setStatus("Last refreshed: " + new Date().toLocaleTimeString());
        renderIssuesList(data.issues || []);
      })
      .catch(function (err) {
        setStatus(String(err), true);
      });
  }

  function runScan() {
    var btn = document.getElementById("governanceScanBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "SCANNING...";
    }
    setStatus("Running governance scan (tests, health, logs)...");
    governanceApi("POST", { action: "scan" })
      .then(function (data) {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "RUN SCAN";
        }
        if (!data.success) {
          setStatus(data.error || "Scan failed", true);
        } else {
          setStatus("Scan complete: " + (data.issues || []).length + " issue(s) detected");
        }
        loadIssues();
      })
      .catch(function (err) {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "RUN SCAN";
        }
        setStatus(String(err), true);
      });
  }

  function approve(issueId) {
    if (!confirm("Approve and apply this SAFE fix? This will modify source files.")) return;
    setStatus("Applying approved fix...");
    governanceApi("POST", { action: "approve", issue_id: issueId })
      .then(function (data) {
        if (!data.success) {
          setStatus(data.error || "Approval failed", true);
        } else {
          setStatus(data.message || "Fix applied successfully");
        }
        loadIssues();
      })
      .catch(function (err) {
        setStatus(String(err), true);
      });
  }

  function reject(issueId) {
    if (!confirm("Reject this proposed fix?")) return;
    governanceApi("POST", { action: "reject", issue_id: issueId })
      .then(function () {
        setStatus("Issue rejected");
        loadIssues();
      })
      .catch(function (err) {
        setStatus(String(err), true);
      });
  }

  function viewDiff(idx) {
    var issues = window._governanceIssues || [];
    var item = issues[idx];
    if (!item) return;
    var diff = item.proposed_fix || "(no diff proposed)";
    var overlay = document.getElementById("governanceDiffOverlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "governanceDiffOverlay";
      overlay.style.cssText =
        "position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px";
      overlay.innerHTML =
        '<div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;max-width:90vw;max-height:85vh;overflow:auto;padding:16px;width:700px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
        '<h3 style="font-size:13px;color:var(--green)">Proposed Fix Diff</h3>' +
        '<button onclick="document.getElementById(\'governanceDiffOverlay\').style.display=\'none\'" style="padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--white);cursor:pointer">CLOSE</button>' +
        "</div>" +
        '<pre id="governanceDiffContent" style="font-size:10px;color:var(--white);white-space:pre-wrap;word-break:break-all;background:var(--panel2);padding:12px;border-radius:8px;max-height:60vh;overflow:auto"></pre>' +
        "</div>";
      document.body.appendChild(overlay);
    }
    document.getElementById("governanceDiffContent").textContent = diff;
    overlay.style.display = "flex";
  }

  function mountAdminSection() {
    return renderGovernancePanelShell();
  }

  function init() {
    loadIssues();
  }

  window.AiGovernancePanel = {
    mountAdminSection: mountAdminSection,
    init: init,
    loadIssues: loadIssues,
    runScan: runScan,
    approve: approve,
    reject: reject,
    viewDiff: viewDiff,
  };
})();
