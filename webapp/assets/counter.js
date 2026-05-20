window.addEventListener('DOMContentLoaded', function() {
    function animateCounter(el, target, decimals, duration) {
        var start = performance.now();
        function update(now) {
            var elapsed = Math.min((now - start) / duration, 1);
            el.textContent = (elapsed * target).toFixed(decimals);
            if (elapsed < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }
    function runCounters() {
        document.querySelectorAll('[data-count]').forEach(function(el) {
            animateCounter(el, +el.dataset.count, +(el.dataset.decimals || 0), 800);
        });
    }
    runCounters();
    // Re-run on Dash updates (Dash replaces DOM without full page reload)
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            m.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {
                    node.querySelectorAll && node.querySelectorAll('[data-count]').forEach(function(el) {
                        animateCounter(el, +el.dataset.count, +(el.dataset.decimals || 0), 800);
                    });
                }
            });
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
