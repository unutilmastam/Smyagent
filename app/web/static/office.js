// SMY Agent — Virtual Office (CLAUDE.md §13A.3, ADR-0009). Vanilla JS + Canvas 2D.
// Every pose and animation comes from /api/v1/control/office (real DB state). The only
// client-side motion is tweening between real states (walking from desk to kitchen etc.).
// Original art drawn in code: no external images, fonts or libraries (CSP 'self').
(function () {
  "use strict";

  var root = document.getElementById("office");
  var canvas = document.getElementById("office-canvas");
  if (!root || !canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var TXT = {};
  try { TXT = JSON.parse(document.getElementById("office-text").textContent); } catch (e) { TXT = {}; }
  function tr(key, params) {
    var s = TXT[key] || key;
    if (params) Object.keys(params).forEach(function (k) { s = s.split("{" + k + "}").join(params[k]); });
    return s;
  }

  var API = root.dataset.api;
  var IS_OWNER = root.dataset.owner === "1";
  var POLL_MS = 4000;
  var FRAME_MS = 1000 / 30; // 30 fps cap (battery)
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var W = 1280, H = 800, MIN_CSS_W = 760;
  var FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

  // ---- layout (logical 1280 x 800) -------------------------------------------------
  var ROOMS = {
    open: { x: 40, y: 40, w: 780, h: 430, door: { x: 430, y: 470 } },
    dir: { x: 840, y: 40, w: 400, h: 430, door: { x: 1000, y: 470 } },
    corr: { x: 40, y: 470, w: 1200, h: 90 },
    kit: { x: 40, y: 560, w: 390, h: 200, door: { x: 235, y: 560 } },
    wc: { x: 450, y: 560, w: 200, h: 200, door: { x: 550, y: 560 } },
    meet: { x: 670, y: 560, w: 330, h: 200, door: { x: 835, y: 560 } },
    mail: { x: 1020, y: 560, w: 220, h: 200, door: { x: 1130, y: 560 } }
  };
  var CY = 515;
  var DESKS = [[80, 100], [270, 100], [460, 100], [650, 100], [175, 290], [365, 290], [555, 290]]
    .map(function (p) { return { x: p[0], y: p[1] }; });
  function seat(i) { return { x: DESKS[i].x + 75, y: DESKS[i].y + 84 }; }
  var KITCHEN = [{ x: 120, y: 650 }, { x: 215, y: 628 }, { x: 310, y: 650 }, { x: 120, y: 715 },
    { x: 215, y: 738 }, { x: 310, y: 715 }, { x: 380, y: 690 }];
  var SOFA = [{ x: 80, y: 612 }, { x: 80, y: 652 }, { x: 80, y: 692 }, { x: 80, y: 732 },
    { x: 160, y: 740 }, { x: 260, y: 740 }, { x: 360, y: 740 }];
  var STALLS = [{ x: 500, y: 625 }, { x: 600, y: 625 }];
  var WC_QUEUE = [{ x: 480, y: 720 }, { x: 530, y: 725 }, { x: 580, y: 720 }, { x: 625, y: 725 },
    { x: 505, y: 690 }];
  var EXIT = [{ x: 1200, y: 505 }, { x: 1170, y: 530 }, { x: 1140, y: 500 }, { x: 1110, y: 530 },
    { x: 1080, y: 500 }, { x: 1050, y: 530 }, { x: 1020, y: 500 }];
  var DIRECTOR = { x: 1060, y: 300 }, MAIL_DESK = { x: 1130, y: 650 };
  var STOP_BTN = { x: 1150, y: 156, r: 26 };

  var LOOK = {
    orchestrator: ["#8E7CF0", "#3B2F2F"], discovery: ["#2BB673", "#1E1A16"],
    research_audit: ["#E8673A", "#6B3E1F"], opportunity_scoring: ["#E0559A", "#2A2320"],
    proposal_requirements: ["#3A8FE0", "#4A2E19"], quality_gate: ["#D9A21E", "#5A3A22"],
    conversation: ["#7FB536", "#141414"]
  };

  function roomOf(p) {
    var order = ["corr", "open", "dir", "kit", "wc", "meet", "mail"];
    for (var k = 0; k < order.length; k++) {
      var r = ROOMS[order[k]];
      if (p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h) return order[k];
    }
    return "corr";
  }
  function route(from, to) {
    var a = roomOf(from), b = roomOf(to), pts = [];
    if (a === b) return [to];
    if (a !== "corr") { var d = ROOMS[a].door; pts.push({ x: d.x, y: d.y }, { x: d.x, y: CY }); }
    if (b !== "corr") { var e = ROOMS[b].door; pts.push({ x: e.x, y: CY }, { x: e.x, y: e.y }); }
    pts.push(to);
    return pts;
  }

  // ---- state -----------------------------------------------------------------------
  var agents = [];
  var byKey = {};
  Array.prototype.forEach.call(document.querySelectorAll("[data-agent]"), function (el, i) {
    var key = el.dataset.agent;
    var look = LOOK[key] || ["#888", "#222"];
    var a = {
      key: key, i: i, name: tr("agent." + key), role: tr("office.role." + key),
      color: look[0], hair: look[1], x: seat(i).x, y: seat(i).y, path: [], dest: null,
      face: 1, alpha: 1, carry: null, server: null, errands: [], errand: null
    };
    agents.push(a);
    byKey[key] = a;
    var dot = document.querySelector('[data-dot="' + key + '"]');
    if (dot) dot.style.backgroundColor = a.color;
  });
  var snap = null, seenEvents = {}, firstPoll = true, offline = false, flyers = [], steam = [];

  function spotFor(a) {
    var s = a.server;
    if (!s) return seat(a.i);
    if (a.errand) return a.errand.to;
    switch (s.mode) {
      case "work": case "error": case "queued": return seat(a.i);
      case "wait": {
        var waiting = agents.filter(function (b) { return b.server && b.server.mode === "wait"; });
        var n = waiting.indexOf(a);
        return n < STALLS.length ? STALLS[n] : WC_QUEUE[(n - STALLS.length) % WC_QUEUE.length];
      }
      case "pause": return SOFA[a.i % SOFA.length];
      case "stop": return EXIT[a.i % EXIT.length];
      default: return KITCHEN[a.i % KITCHEN.length]; // idle: coffee
    }
  }
  function goTo(a, p) {
    if (a.dest && a.dest.x === p.x && a.dest.y === p.y) return;
    a.dest = { x: p.x, y: p.y };
    if (reduced) { a.x = p.x; a.y = p.y; a.path = []; return; }
    a.path = route(a, p);
  }
  function arrived(a) { return a.path.length === 0; }

  // ---- server polling ----------------------------------------------------------------
  function poll() {
    if (document.visibilityState !== "visible") return;
    fetch(API, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) {
        var type = r.headers.get("content-type") || "";
        if (r.status === 401 || (r.redirected && type.indexOf("json") < 0)) {
          window.location.reload(); // session expired → login page
          throw new Error("auth");
        }
        if (!r.ok || type.indexOf("json") < 0) throw new Error("http " + r.status);
        return r.json();
      })
      .then(function (data) { offline = false; apply(data); })
      .catch(function () { offline = true; renderStatus(); });
  }

  function apply(data) {
    snap = data;
    (data.agents || []).forEach(function (s) {
      var a = byKey[s.key];
      if (a) a.server = s;
    });
    (data.events || []).forEach(function (ev) {
      if (seenEvents[ev.id]) return;
      seenEvents[ev.id] = true;
      if (!firstPoll) playEvent(ev); // reloading the page never replays old events
    });
    firstPoll = false;
    agents.forEach(function (a) { if (!a.errand) goTo(a, spotFor(a)); });
    renderList();
    renderStatus();
    if (openKey) fillSheet();
  }

  function playEvent(ev) {
    var a = byKey[ev.module];
    if (ev.kind === "handoff") {
      var b = byKey[ev.to];
      if (a && b && !reduced) flyers.push({ from: seat(a.i), to: seat(b.i), t: 0, kind: "paper" });
      return;
    }
    if (!a) return;
    if (ev.kind === "email_sent") {
      a.errands.push({ to: MAIL_DESK, carry: "mail", done: function () {
        if (!reduced) flyers.push({ from: MAIL_DESK, to: { x: 1275, y: CY }, t: 0, kind: "mail" });
      } });
    } else if (ev.kind === "order_confirmed") {
      toast(tr("office.new_order", { t: ev.text || "" }));
      a.errands.push({ to: DIRECTOR, carry: "folder", done: function () {} });
    }
  }

  // ---- DOM: list, status, sheet, toast ---------------------------------------------
  function modeLabel(s) {
    if (!s) return "…";
    if (s.mode === "error" && s.stalled) return tr("office.mode.stalled");
    return tr("office.mode." + s.mode);
  }
  function hhmm(iso) {
    try {
      return new Intl.DateTimeFormat(undefined, {
        hour: "2-digit", minute: "2-digit", hour12: false, timeZone: root.dataset.timezone
      }).format(new Date(iso));
    } catch (e) { return ""; }
  }
  function detailText(s) {
    if (!s) return "";
    if (s.mode === "work") return (s.detail || "…") + (s.progress_pct != null ? " · " + s.progress_pct + "%" : "");
    if (s.mode === "queued") return s.detail + " " + tr("office.queued");
    if (s.mode === "wait") {
      var why = s.wait_kind ? tr("office.wait." + s.wait_kind) : "";
      var parts = [why, s.detail, s.retry_at ? tr("office.retry_at", { t: hhmm(s.retry_at) }) : ""];
      return parts.filter(Boolean).join(" · ");
    }
    if (s.mode === "error") return s.detail || "";
    return "";
  }
  function pillClass(s) {
    var m = s ? s.mode : "";
    return "badge badge-office-" + (m === "error" && s.stalled ? "stalled" : m);
  }
  function renderList() {
    agents.forEach(function (a) {
      var text = document.querySelector('[data-text="' + a.key + '"]');
      var pill = document.querySelector('[data-pill="' + a.key + '"]');
      if (text) text.textContent = detailText(a.server) || a.role;
      if (pill) { pill.textContent = modeLabel(a.server); pill.className = pillClass(a.server); }
    });
  }
  var statusEl = document.getElementById("office-status");
  function renderStatus() {
    if (!statusEl) return;
    var parts = [];
    if (offline) parts.push("⚠ " + tr("office.offline"));
    if (snap) {
      if (snap.cron_health !== "ok") parts.push("⏰ " + tr("office.cron_late"));
      var d = snap.today || {};
      parts.push(snap.local_time + " · " + tr("office.funnel", {
        a: d.found || 0, b: d.researched || 0, c: d.proposals || 0, d: d.emails || 0, e: d.orders || 0
      }));
    }
    statusEl.textContent = parts.join("  ·  ");
    statusEl.classList.toggle("office-status-bad", offline || (snap && snap.cron_health !== "ok"));
  }

  var sheet = document.getElementById("office-sheet");
  var openKey = null;
  function openSheet(key) { openKey = key; sheet.hidden = false; fillSheet(); }
  function fillSheet() {
    var a = byKey[openKey];
    if (!a) return;
    var s = a.server || {};
    document.getElementById("sheet-dot").style.backgroundColor = a.color;
    document.getElementById("sheet-name").textContent = a.name;
    document.getElementById("sheet-role").textContent = a.role;
    var pill = document.getElementById("sheet-pill");
    pill.textContent = modeLabel(a.server);
    pill.className = pillClass(a.server);
    document.getElementById("sheet-detail").textContent = detailText(a.server);
    document.getElementById("sheet-done").textContent = s.done_today || 0;
    document.getElementById("sheet-failed").textContent = s.failed_today || 0;
    document.getElementById("sheet-queued").textContent = s.queued || 0;
    document.getElementById("sheet-cost").textContent = s.cost_today_usd || "0";
    var job = document.getElementById("sheet-job");
    job.hidden = !s.job_id;
    if (s.job_id) job.href = "/jobs/" + encodeURIComponent(s.job_id);
    document.getElementById("sheet-settings").href = "/settings/agents/" + encodeURIComponent(a.key);
    Array.prototype.forEach.call(document.querySelectorAll("[data-sheet-form]"), function (form) {
      form.action = "/control/" + encodeURIComponent(a.key);
      var btn = form.querySelector("button");
      var current = btn.dataset.state === s.control;
      btn.disabled = current;
      btn.classList.toggle("is-current", current);
    });
  }
  document.getElementById("sheet-close").addEventListener("click", function () {
    sheet.hidden = true; openKey = null;
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-agent]"), function (el) {
    el.addEventListener("click", function () { openSheet(el.dataset.agent); });
  });

  var toastEl = document.getElementById("office-toast");
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () { toastEl.hidden = true; }, 6000);
  }

  // ---- canvas sizing and taps --------------------------------------------------------
  var scroller = document.getElementById("office-scroller");
  var scale = 1;
  function resize() {
    var cssW = Math.max(scroller.clientWidth, MIN_CSS_W);
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    scale = cssW / W;
    canvas.style.width = cssW + "px";
    canvas.style.height = H * scale + "px";
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(H * scale * dpr);
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  canvas.addEventListener("click", function (e) {
    var r = canvas.getBoundingClientRect();
    var x = (e.clientX - r.left) / scale, y = (e.clientY - r.top) / scale;
    if (Math.hypot(x - STOP_BTN.x, y - STOP_BTN.y) < STOP_BTN.r) { directorButton(); return; }
    var best = null, bd = 45;
    agents.forEach(function (a) {
      var d = Math.hypot(a.x - x, a.y - 20 - y);
      if (d < bd) { bd = d; best = a; }
    });
    if (best) openSheet(best.key);
  });
  function directorButton() {
    if (!IS_OWNER || !snap) return;
    var stopped = snap.global_state === "STOPPED";
    var form = document.getElementById(stopped ? "office-resume-form" : "office-stop-form");
    if (form && window.confirm(tr(stopped ? "office.resume.confirm" : "control.stop_all.confirm"))) form.submit();
  }

  // ---- drawing -----------------------------------------------------------------------
  function R(x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); }
  function RR(x, y, w, h, r, c) {
    ctx.fillStyle = c;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, r); else ctx.rect(x, y, w, h);
    ctx.fill();
  }
  function T(s, x, y, size, c, align, weight) {
    ctx.font = (weight || 600) + " " + size + "px " + FONT;
    ctx.fillStyle = c; ctx.textAlign = align || "center"; ctx.textBaseline = "middle";
    ctx.fillText(s, x, y);
  }
  function fit(s, max) { return s.length > max ? s.slice(0, max - 1) + "…" : s; }
  function tiles(r, a, b, sz) {
    for (var y = r.y; y < r.y + r.h; y += sz)
      for (var x = r.x; x < r.x + r.w; x += sz)
        R(x, y, Math.min(sz, r.x + r.w - x), Math.min(sz, r.y + r.h - y), ((x / sz + y / sz) | 0) % 2 ? a : b);
  }
  function plant(x, y, s) {
    RR(x - 10 * s, y, 20 * s, 16 * s, 3, "#8A5A3B");
    ctx.fillStyle = "#2F7D4A";
    [[0, -10], [-9, -4], [9, -4], [-5, -16], [6, -15]].forEach(function (d) {
      ctx.beginPath(); ctx.arc(x + d[0] * s, y + d[1] * s, 8 * s, 0, 7); ctx.fill();
    });
  }
  function line(x1, y1, x2, y2) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }

  function drawWorld(now) {
    var night = snap && snap.night, stopped = snap && snap.global_state === "STOPPED";
    R(0, 0, W, H, "#1b2420");
    tiles(ROOMS.open, "#D8DCD3", "#D1D6CC", 40);
    tiles(ROOMS.corr, "#C9C3B6", "#C3BDB0", 30);
    tiles(ROOMS.kit, "#EFE6D2", "#E5DAC2", 28);
    tiles(ROOMS.wc, "#D3E4EE", "#C7DAE6", 24);
    for (var py = ROOMS.dir.y; py < ROOMS.dir.y + ROOMS.dir.h; py += 18)
      for (var px = ROOMS.dir.x + ((py / 18) % 2 ? 0 : 30); px < ROOMS.dir.x + ROOMS.dir.w; px += 60)
        R(px, py, Math.min(58, ROOMS.dir.x + ROOMS.dir.w - px), 16, ((px + py) / 60 | 0) % 2 ? "#B58457" : "#A9784C");
    tiles(ROOMS.meet, "#D6D2E4", "#CECADD", 36);
    tiles(ROOMS.mail, "#E2D8C6", "#D9CEBB", 30);
    var sky = night ? "#1C2C4A" : "#9FD3EE";
    for (var wx = 70; wx < 800; wx += 110) R(wx, 22, 70, 10, sky);
    for (var wx2 = 870; wx2 < 1220; wx2 += 110) R(wx2, 22, 70, 10, sky);
    // walls with door gaps
    ctx.strokeStyle = "#3A4540"; ctx.lineWidth = 10; ctx.lineCap = "square";
    ctx.strokeRect(25, 25, 1230, 750);
    line(40, 470, 395, 470); line(465, 470, 820, 470); line(830, 40, 830, 470);
    line(840, 470, 965, 470); line(1035, 470, 1240, 470);
    line(40, 560, 200, 560); line(270, 560, 430, 560); line(440, 560, 440, 775);
    line(450, 560, 515, 560); line(585, 560, 650, 560); line(660, 560, 660, 775);
    line(670, 560, 800, 560); line(870, 560, 1000, 560); line(1010, 560, 1010, 775);
    line(1020, 560, 1095, 560); line(1165, 560, 1240, 560);
    R(1246, CY - 34, 12, 68, "#2E8B57");
    [["office.room.open", 52, 56], ["office.room.dir", 852, 56], ["office.room.kitchen", 52, 578],
      ["office.room.wc", 462, 578], ["office.room.meet", 682, 578], ["office.room.mail", 1032, 578]]
      .forEach(function (l) {
        ctx.font = "700 14px " + FONT;
        var label = tr(l[0]), lw = ctx.measureText(label).width + 12;
        RR(l[1] - 6, l[2] - 11, lw, 22, 6, "rgba(255,255,255,.75)");
        T(label, l[1], l[2], 14, "#3A4540", "left", 700);
      });
    plant(60, 440, 1); plant(800, 440, 1); plant(800, 80, 0.9);

    DESKS.forEach(function (d, i) { drawDesk(d, agents[i], now); });

    // director's room: desk, "you", the big red STOP
    R(990, 128, 210, 80, "rgba(0,0,0,.12)"); RR(980, 120, 210, 76, 6, "#6E4A2E"); R(980, 188, 210, 8, "#5A3C25");
    RR(1030, 80, 96, 40, 10, "#2E2A28"); T(fit(tr("office.director"), 14), 1078, 100, 13, "#F3E7D3", "center", 700);
    RR(1000, 132, 56, 34, 3, "#2B3330"); R(1003, 135, 50, 28, "#173C30");
    var pulse = reduced || stopped ? 0 : Math.sin(now / 300) * 1.5;
    ctx.fillStyle = "#4A4A4A"; ctx.beginPath(); ctx.arc(STOP_BTN.x, 158, 22, 0, 7); ctx.fill();
    ctx.fillStyle = stopped ? "#7A1E16" : "#E0392B"; ctx.beginPath(); ctx.arc(STOP_BTN.x, 156, 16 + pulse, 0, 7); ctx.fill();
    T("STOP", STOP_BTN.x, 192, 13, "#F3E7D3", "center", 700);
    RR(860, 80, 22, 260, 3, "#7B5A3D");
    for (var k = 0; k < 6; k++) for (var m = 0; m < 3; m++)
      R(864 + m * 6, 90 + k * 40, 5, 28, ["#C0392B", "#2E86C1", "#27AE60", "#F1C40F"][(k + m) % 4]);
    plant(1210, 440, 1.1); RR(900, 380, 120, 60, 8, "#3C5A73");

    // kitchen: table, coffee machine, fridge, sofa (lounge)
    RR(140, 640, 150, 70, 10, "#C9A57A"); R(140, 700, 150, 10, "#A98659");
    RR(345, 575, 80, 40, 4, "#9AA3A0"); RR(365, 580, 34, 34, 4, "#2E3533"); R(375, 600, 14, 10, "#7A4B2A");
    RR(48, 575, 40, 22, 4, "#E6EAEA");
    RR(52, 600, 40, 150, 10, "#7E5B9A");
    steam.forEach(function (p) {
      ctx.fillStyle = "rgba(255,255,255," + p.a + ")"; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill();
    });

    // restroom: two stalls with real occupancy (agents waiting there)
    STALLS.forEach(function (s, n) {
      var x = n ? 560 : 460;
      R(x, 580, 80, 80, "#AFC6D4");
      ctx.strokeStyle = "#6E8796"; ctx.lineWidth = 3; ctx.strokeRect(x, 580, 80, 80);
      var occupied = agents.some(function (a) {
        return a.server && a.server.mode === "wait" && Math.hypot(a.x - s.x, a.y - s.y) < 3;
      });
      RR(x + 28, 664, 24, 12, 3, occupied ? "#D2453A" : "#2E8B57");
    });

    // meeting room: the real funnel of today on the whiteboard
    ctx.fillStyle = "#8C6A4D"; ctx.beginPath(); ctx.ellipse(835, 680, 110, 42, 0, 0, 7); ctx.fill();
    for (var c = 0; c < 6; c++) {
      var ang = c / 6 * Math.PI * 2;
      RR(835 + Math.cos(ang) * 140 - 12, 680 + Math.sin(ang) * 62 - 10, 24, 20, 6, "#4A4E69");
    }
    RR(690, 592, 290, 30, 3, "#F7F7F2");
    var d0 = (snap && snap.today) || {};
    T((d0.found || 0) + " → " + (d0.researched || 0) + " → " + (d0.proposals || 0) + " → " +
      (d0.emails || 0) + " → " + (d0.orders || 0), 835, 607, 14, "#2C3E50", "center", 700);

    // mail desk
    RR(1040, 610, 180, 40, 4, "#8E6E4E"); RR(1150, 595, 50, 18, 3, "#D9C9A8");
    plant(1225, 740, 0.9);

    if (night) R(0, 0, W, H, "rgba(10,18,40,.35)");
    if (stopped) R(0, 0, W, H, "rgba(0,0,0,.45)");
  }

  function drawDesk(d, a, now) {
    var s = a && a.server, mode = s ? s.mode : "";
    var atDesk = a && Math.hypot(a.x - seat(a.i).x, a.y - seat(a.i).y) < 3;
    R(d.x + 4, d.y + 8, 150, 56, "rgba(0,0,0,.12)");
    RR(d.x, d.y, 150, 56, 4, "#B98B5E"); R(d.x, d.y + 50, 150, 6, "#9C7048");
    RR(d.x + 48, d.y + 4, 54, 34, 3, "#2B3330");
    var typing = mode === "work" && atDesk;
    var screen = mode === "error" ? "#E04A3A" : typing ? "#123A2C" : mode === "stop" ? "#0E1110" : "#1E2826";
    R(d.x + 51, d.y + 7, 48, 26, screen);
    if (typing) {
      for (var k = 0; k < 4; k++) {
        var w = reduced ? 20 : 10 + ((k * 13 + (now / 120 | 0) * 7) % 30);
        R(d.x + 54, d.y + 10 + k * 6, w, 3, k % 2 ? "#7FE0B4" : a.color);
      }
    }
    if (mode === "error") T("!", d.x + 75, d.y + 20, 20, "#fff", "center", 800);
    R(d.x + 68, d.y + 38, 14, 6, "#2B3330"); RR(d.x + 50, d.y + 42, 50, 8, 2, "#E9ECE8");
    RR(d.x + 58, d.y + 70, 34, 30, 8, mode === "stop" ? "#2A3036" : "#36414A");
    RR(d.x + 6, d.y + 40, 40, 12, 3, a ? a.color : "#999");
    // the monitor caption: the real current step / error / queue (CLAUDE.md §13A.3)
    var caption = "";
    if (mode === "work") caption = s.detail || "";
    else if (mode === "error") caption = s.stalled ? tr("office.mode.stalled") : (s.detail || "");
    else if (mode === "queued") caption = s.detail + " " + tr("office.queued");
    if (caption) {
      ctx.font = "600 12px " + FONT;
      var text = fit(caption, 26), tw = Math.min(170, ctx.measureText(text).width + 12);
      RR(d.x + 75 - tw / 2, d.y - 30, tw, 18, 6, mode === "error" ? "rgba(192,57,43,.92)" : "rgba(20,26,23,.85)");
      T(text, d.x + 75, d.y - 21, 12, "#fff", "center", 600);
    }
    if (mode === "work" && s.progress_pct != null) {
      R(d.x + 5, d.y - 9, 140, 5, "rgba(0,0,0,.25)");
      R(d.x + 5, d.y - 9, 140 * s.progress_pct / 100, 5, a.color);
    }
  }

  function drawAgent(a, now) {
    var s = a.server || {}, mode = s.mode;
    var stopped = mode === "stop";
    ctx.globalAlpha = stopped ? 0.55 : 1;
    var moving = a.path.length > 0;
    var sit = !moving && (mode === "work" || mode === "error" || mode === "queued" || mode === "pause" || mode === "idle") && !a.errand;
    var bob = moving && !reduced ? Math.abs(Math.sin(now / 110 + a.i)) * 3 : 0;
    var x = a.x, y = a.y - bob;
    ctx.fillStyle = "rgba(0,0,0,.22)"; ctx.beginPath(); ctx.ellipse(a.x, a.y + 14, 15, 6, 0, 0, 7); ctx.fill();
    if (!sit) {
      var step = moving && !reduced ? Math.sin(now / 90 + a.i) * 5 : 0;
      R(x - 8, y + 4 + step, 6, 12, "#2D3436"); R(x + 2, y + 4 - step, 6, 12, "#2D3436");
    }
    RR(x - 13, y - 16, 26, 24, 8, a.color);
    var arm = mode === "work" && !moving && !reduced ? Math.sin(now / 70 + a.i) * 2 : 0;
    RR(x - 17, y - 12 + arm, 6, 14, 3, a.color); RR(x + 11, y - 12 - arm, 6, 14, 3, a.color);
    ctx.fillStyle = "#F2C9A8"; ctx.beginPath(); ctx.arc(x, y - 28, 12, 0, 7); ctx.fill();
    ctx.fillStyle = a.hair; ctx.beginPath(); ctx.arc(x, y - 31, 12.5, Math.PI, 0); ctx.fill(); R(x - 12.5, y - 32, 25, 4, a.hair);
    var ex = a.face * 2;
    R(x - 5 + ex, y - 28, 3, 3, "#1d1d1d"); R(x + 3 + ex, y - 28, 3, 3, "#1d1d1d");
    if (a.carry === "mail") {
      RR(x + 8, y - 10, 20, 14, 2, "#FFFFFF");
      ctx.strokeStyle = "#C0392B"; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(x + 8, y - 10); ctx.lineTo(x + 18, y - 2); ctx.lineTo(x + 28, y - 10); ctx.stroke();
    } else if (a.carry === "folder") {
      RR(x + 8, y - 12, 20, 16, 2, "#F0A04B"); R(x + 8, y - 14, 8, 4, "#F0A04B");
    } else if (mode === "idle" && !moving) {
      RR(x + 13, y - 6, 9, 11, 2, "#FFFFFF"); R(x + 15, y - 4, 5, 3, "#6B3E1F"); // coffee cup
    }
    ctx.font = "700 13px " + FONT;
    var label = fit(a.name, 18), tw = ctx.measureText(label).width + 12;
    RR(x - tw / 2, y - 62, tw, 18, 9, "rgba(20,26,23,.85)");
    T(label, x, y - 53, 13, "#FFFFFF", "center", 700);
    var icon = null, bg = "#FFFFFF";
    if (!moving && !a.errand) {
      if (mode === "wait") { icon = fit(s.wait_kind ? tr("office.wait." + s.wait_kind) : tr("office.mode.wait"), 22); bg = "#F3D27A"; }
      else if (mode === "pause") { icon = tr("office.mode.pause"); bg = "#E6E0F8"; }
      else if (mode === "error" && !s.stalled) { icon = "!"; bg = "#F7A39A"; }
    }
    if (icon) {
      ctx.font = "700 12px " + FONT;
      var bw = ctx.measureText(icon).width + 14;
      RR(x + 10, y - 86, bw, 20, 8, bg);
      T(icon, x + 10 + bw / 2, y - 76, 12, "#2A2A2A", "center", 700);
    }
    ctx.globalAlpha = 1;
  }

  function drawFlyers(dt) {
    for (var k = flyers.length - 1; k >= 0; k--) {
      var f = flyers[k];
      f.t += dt * 1.2;
      var e = Math.min(1, f.t);
      var x = f.from.x + (f.to.x - f.from.x) * e;
      var y = f.from.y - 20 + (f.to.y - f.from.y) * e - Math.sin(e * Math.PI) * 60;
      if (f.kind === "mail") RR(x - 10, y - 7, 20, 14, 2, "#FFFFFF");
      else {
        ctx.save(); ctx.translate(x, y); ctx.rotate(e * 6);
        R(-8, -10, 16, 20, "#FFFFFF"); R(-5, -6, 10, 2, "#99AAAA"); R(-5, -1, 10, 2, "#99AAAA");
        ctx.restore();
      }
      if (e >= 1) flyers.splice(k, 1);
    }
  }

  // ---- animation loop ----------------------------------------------------------------
  function move(a, dt) {
    if (!a.path.length) return;
    var p = a.path[0], dx = p.x - a.x, dy = p.y - a.y, d = Math.hypot(dx, dy), v = 160 * dt;
    if (Math.abs(dx) > 0.5) a.face = dx > 0 ? 1 : -1;
    if (d <= v) { a.x = p.x; a.y = p.y; a.path.shift(); } else { a.x += dx / d * v; a.y += dy / d * v; }
  }
  function runErrands(a, now) {
    if (!a.errand && a.errands.length) {
      var stopped = a.server && a.server.mode === "stop";
      if (stopped) { a.errands = []; return; } // a stopped agent carries nothing
      a.errand = a.errands.shift();
      a.carry = a.errand.carry;
      a.errand.until = 0;
      goTo(a, a.errand.to);
    }
    if (a.errand && arrived(a)) {
      if (!a.errand.until) { a.errand.done(); a.carry = null; a.errand.until = now + 900; }
      else if (now >= a.errand.until) { a.errand = null; goTo(a, spotFor(a)); }
    }
  }

  var last = 0, lastDraw = 0;
  function frame(now) {
    window.requestAnimationFrame(frame);
    if (document.visibilityState !== "visible") { last = now; return; }
    if (now - lastDraw < FRAME_MS) return;
    lastDraw = now;
    var dt = Math.min(0.1, (now - (last || now)) / 1000);
    last = now;
    agents.forEach(function (a) { runErrands(a, now); move(a, dt); });
    if (!reduced) {
      var brewing = agents.some(function (a) { return a.server && a.server.mode === "idle" && !a.path.length; });
      if (brewing && Math.random() < 0.3) steam.push({ x: 382 + Math.random() * 8, y: 590, r: 3, a: 0.5 });
      steam.forEach(function (p) { p.y -= 20 * dt; p.r += 3 * dt; p.a -= 0.35 * dt; });
      while (steam.length && steam[0].a <= 0) steam.shift();
    }
    drawWorld(now);
    agents.slice().sort(function (p, q) { return p.y - q.y; }).forEach(function (a) { drawAgent(a, now); });
    drawFlyers(dt);
    if (snap && snap.global_state === "STOPPED") {
      T(tr("office.stopped_banner"), W / 2, H / 2, 34, "#FFD5CF", "center", 800);
    }
  }

  poll();
  window.setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") poll(); });
  window.requestAnimationFrame(frame);
})();
