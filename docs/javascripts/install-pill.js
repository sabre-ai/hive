// Hive install pill — copy handler.
(function () {
  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('[data-hive-copy]');
    if (!btn) return;
    var text = btn.dataset.hiveCopy;
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      // clipboard unavailable; fall through silently
    }
    var original = btn.textContent;
    btn.dataset.copied = 'true';
    btn.textContent = 'COPIED';
    setTimeout(function () {
      btn.dataset.copied = 'false';
      btn.textContent = original;
    }, 1400);
  });
})();
