// SMY Agent dashboard script. No inline scripts (CSP script-src 'self').
(function () {
  "use strict";

  function showToast(message) {
    var toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () { toast.hidden = true; }, 5000);
  }

  // Explicit error state for HTMX requests (network down, 5xx).
  document.addEventListener("htmx:sendError", function () {
    showToast(document.body.dataset.networkError || "Network error");
  });
  document.addEventListener("htmx:responseError", function (evt) {
    if (evt.detail.xhr && evt.detail.xhr.status === 401) return; // HX-Redirect handles it
    showToast(document.body.dataset.networkError || "Error");
  });

  // Confirmation for dangerous forms (e.g. STOP ALL): <form data-confirm="...">.
  document.addEventListener("submit", function (evt) {
    var form = evt.target;
    if (form && form.dataset && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      evt.preventDefault();
    }
  }, true);

  // Control Center polling (CLAUDE.md §13A.1): every 4 s, only while the tab is visible.
  // Done here because htmx trigger filters need eval, which the CSP forbids.
  var POLL_MS = 4000;
  function startPolling() {
    var target = document.querySelector("[data-poll]");
    if (!target || !window.htmx) return;
    window.setInterval(function () {
      if (document.visibilityState !== "visible") return;
      window.htmx.ajax("GET", target.dataset.poll, { target: target, swap: "innerHTML" });
    }, POLL_MS);
  }
  document.addEventListener("DOMContentLoaded", startPolling);

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }
})();
