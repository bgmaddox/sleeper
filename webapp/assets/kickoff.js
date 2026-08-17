/* Preseason kickoff countdown.
   Follows the same shape as counter.js: read a data attribute, then re-attach
   on Dash DOM swaps via MutationObserver (Dash replaces nodes without a page
   reload, which would otherwise leave the clock frozen at "--").

   The target timestamp is rendered server-side into data-kickoff as epoch ms
   (UTC), derived from the published NFL schedule — never hardcoded here. */
window.addEventListener('DOMContentLoaded', function () {
    var timer = null;

    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function render(root) {
        var target = parseInt(root.dataset.kickoff, 10);
        if (!target) return false;

        var diff = target - Date.now();
        var counting = diff > 0;   // still before kickoff
        if (!counting) diff = 0;

        var secs = Math.floor(diff / 1000);
        var parts = {
            d: Math.floor(secs / 86400),
            h: Math.floor((secs % 86400) / 3600),
            m: Math.floor((secs % 3600) / 60),
            s: secs % 60
        };

        Object.keys(parts).forEach(function (key) {
            var el = root.querySelector('[data-kickoff-unit="' + key + '"]');
            if (!el) return;
            var next = key === 'd' ? String(parts[key]) : pad(parts[key]);
            // Only write when the value actually changed. Assigning textContent
            // replaces a text node, which is a childList mutation the observer
            // below would otherwise pick up.
            if (el.textContent !== next) el.textContent = next;
        });

        // Once the clock hits zero the hero is about to be replaced by real
        // data anyway; mark it so the CSS can swap in a "kickoff!" treatment.
        root.classList.toggle('is-live', !counting);
        return counting;
    }

    function tick() {
        var roots = document.querySelectorAll('[data-kickoff]');
        if (!roots.length) {
            if (timer) { clearInterval(timer); timer = null; }
            return;
        }
        roots.forEach(render);
    }

    function start() {
        tick();
        if (!timer && document.querySelector('[data-kickoff]')) {
            timer = setInterval(tick, 1000);
        }
    }

    start();

    // Restart only when a countdown actually enters the DOM.
    //
    // Reacting to any addedNodes deadlocks the page: render() writes
    // textContent, which is itself a childList mutation, so the observer would
    // re-enter start() -> tick() -> render() forever. Observer callbacks are
    // microtasks, so that loop never yields and the tab hangs. Element nodes
    // only (nodeType 1) — the text nodes our own writes create are skipped,
    // which is the same guard counter.js relies on.
    var observer = new MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
            var added = mutations[i].addedNodes;
            for (var j = 0; j < added.length; j++) {
                var node = added[j];
                if (node.nodeType !== 1) continue;
                if ((node.matches && node.matches('[data-kickoff]')) ||
                    (node.querySelector && node.querySelector('[data-kickoff]'))) {
                    start();
                    return;
                }
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
