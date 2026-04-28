// Hive install pill — copy handler.
(function () {
  document.addEventListener("click", async function (e) {
    var btn = e.target.closest("[data-hive-copy]");
    if (!btn) return;
    var text = btn.dataset.hiveCopy;
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      // clipboard unavailable; fall through silently
    }
    var original = btn.textContent;
    btn.dataset.copied = "true";
    btn.textContent = "\u2713 Copied";
    btn.setAttribute("aria-label", "Copied to clipboard");
    setTimeout(function () {
      btn.dataset.copied = "false";
      btn.textContent = original;
      btn.setAttribute("aria-label", "Copy install command");
    }, 1400);
  });
})();
