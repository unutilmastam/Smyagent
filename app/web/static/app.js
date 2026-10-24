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

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }
})();
