/**
 * Cookie consent (RGPD) — Amour Crochet Garden
 * necessary: always on | analytics: optional
 */
(function () {
  var STORAGE_KEY = "acg_cookie_consent";
  var COOKIE_ANALYTICS = "acg_analytics";
  var MAX_AGE_DAYS = 180;

  function readConsent() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setAnalyticsCookie(enabled) {
    var maxAge = MAX_AGE_DAYS * 24 * 60 * 60;
    if (enabled) {
      document.cookie =
        COOKIE_ANALYTICS + "=1; path=/; max-age=" + maxAge + "; SameSite=Lax";
    } else {
      document.cookie =
        COOKIE_ANALYTICS + "=; path=/; max-age=0; SameSite=Lax";
    }
  }

  function saveConsent(analytics) {
    var data = {
      necessary: true,
      analytics: !!analytics,
      ts: Date.now(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    setAnalyticsCookie(data.analytics);
    hideBanner();
    hideModal();
    return data;
  }

  function hideBanner() {
    var el = document.getElementById("cookieBanner");
    if (el) el.hidden = true;
  }

  function showBanner() {
    var el = document.getElementById("cookieBanner");
    if (el) el.hidden = false;
  }

  function hideModal() {
    var el = document.getElementById("cookieModal");
    if (el) el.hidden = true;
  }

  function showModal() {
    var el = document.getElementById("cookieModal");
    var consent = readConsent();
    var check = document.getElementById("cookieAnalyticsToggle");
    if (check) check.checked = !!(consent && consent.analytics);
    if (el) el.hidden = false;
  }

  function init() {
    var consent = readConsent();
    if (!consent) {
      showBanner();
    } else {
      setAnalyticsCookie(!!consent.analytics);
      hideBanner();
    }

    document.getElementById("cookieAcceptAll")?.addEventListener("click", function () {
      saveConsent(true);
    });
    document.getElementById("cookieRejectOptional")?.addEventListener("click", function () {
      saveConsent(false);
    });
    document.getElementById("cookieCustomize")?.addEventListener("click", function () {
      showModal();
    });
    document.getElementById("cookieSavePrefs")?.addEventListener("click", function () {
      var check = document.getElementById("cookieAnalyticsToggle");
      saveConsent(!!(check && check.checked));
    });
    document.getElementById("cookieModalClose")?.addEventListener("click", hideModal);
    document.querySelectorAll("[data-open-cookie-settings]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        showModal();
        showBanner();
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.acgOpenCookieSettings = function () {
    showModal();
    showBanner();
  };
})();
