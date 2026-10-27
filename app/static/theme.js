/* Theme: "auto" follows the system, "light" and "dark" are fixed. Loaded in <head> so that the page never flashes
   the wrong colours. The choice is kept in localStorage (when the browser allows it). */
(function () {
  "use strict";
  var KEY = "melomancer.theme";
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

  function stored() {
    try {
      var value = localStorage.getItem(KEY);
      return value === "light" || value === "dark" ? value : "auto";
    } catch (e) { return "auto"; }
  }
  function resolve(mode) { return mode === "auto" ? (media && media.matches ? "light" : "dark") : mode; }
  function apply(mode) { document.documentElement.setAttribute("data-theme", resolve(mode)); }

  window.MelomancerTheme = {
    get: stored,
    set: function (mode) {
      try {
        if (mode === "auto") localStorage.removeItem(KEY); else localStorage.setItem(KEY, mode);
      } catch (e) { /* storage unavailable: the choice lasts until the page is closed */ }
      apply(mode);
    },
  };
  if (media && media.addEventListener) {
    media.addEventListener("change", function () { if (stored() === "auto") apply("auto"); });
  }
  apply(stored());
})();
