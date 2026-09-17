/* chartdownload.js — "Download PNG" button on every chart card.
 *
 * Injects a button into each .chart-card that holds a Plotly graph or a D3
 * SVG, and renders a share-ready PNG: the chart composited onto the card
 * background (both Plotly and D3 render transparent, which shares badly),
 * with the card title and the current season/week drawn in as a header.
 *
 * Pure DOM — no Dash callbacks, no app.py changes. A MutationObserver
 * re-scans after Dash swaps a tab, so new and future charts are covered.
 */
(function () {
    'use strict';

    var SCALE   = 2;      // export at 2x for crisp sharing
    var PAD     = 24;     // CSS-px padding around the composited chart
    var HEADER  = 54;     // CSS-px reserved for title + context line
    var FOOTER  = 22;     // CSS-px for the attribution line

    function cssVar(name, fallback) {
        var v = getComputedStyle(document.documentElement).getPropertyValue(name);
        return (v && v.trim()) || fallback;
    }

    function theme() {
        return {
            bg:      cssVar('--bg-card',      '#1a3a52'),
            accent:  cssVar('--accent',       '#FFC300'),
            text:    cssVar('--text-main',    '#BDE2FF'),
            muted:   cssVar('--text-muted',   '#6a9abf'),
            border:  cssVar('--border',       '#2e526e'),
            display: cssVar('--font-display', 'Rockwell, Georgia, serif'),
            main:    cssVar('--font-main',    "'Courier New', Courier, monospace"),
        };
    }

    /* ── Context (season / week) from the controls bar ──────────────────── */

    function context() {
        var bits = [];
        var yr = document.getElementById('year-display');
        if (yr && yr.textContent.trim()) bits.push(yr.textContent.trim());
        var wk = document.querySelector('.week-scrubber-row .week-btn--active');
        if (wk && wk.textContent.trim()) bits.push('Week ' + wk.textContent.trim());
        return bits.join('  ·  ');
    }

    function slug(s) {
        return (s || 'chart').toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 60) || 'chart';
    }

    /* ── Finding the exportable element inside a card ───────────────────── */

    function plotlyIn(card) {
        var p = card.querySelector('.js-plotly-plot');
        return (p && p.offsetWidth > 0) ? p : null;
    }

    function svgIn(card) {
        // Largest standalone SVG that is not part of a Plotly plot or a button
        var best = null, bestArea = 0;
        card.querySelectorAll('svg').forEach(function (s) {
            if (s.closest('.js-plotly-plot')) return;
            if (s.closest('.chart-dl')) return;
            var w = s.clientWidth || +s.getAttribute('width') || 0;
            var h = s.clientHeight || +s.getAttribute('height') || 0;
            if (w * h > bestArea && w > 120 && h > 80) { best = s; bestArea = w * h; }
        });
        return best;
    }

    function exportable(card) { return plotlyIn(card) || svgIn(card); }

    /* ── Source image: Plotly ───────────────────────────────────────────── */

    function plotlyImage(gd) {
        var w = gd.offsetWidth  || 900;
        var h = gd.offsetHeight || 560;
        return window.Plotly.toImage(gd, {
            format: 'png', width: w, height: h, scale: SCALE,
        }).then(function (url) {
            return loadImage(url).then(function (img) {
                return { img: img, w: w, h: h };
            });
        });
    }

    /* ── Source image: D3 SVG ───────────────────────────────────────────── */

    function svgImage(svg) {
        var w = svg.clientWidth  || +svg.getAttribute('width')  || 900;
        var h = svg.clientHeight || +svg.getAttribute('height') || 560;

        var clone = svg.cloneNode(true);
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
        clone.setAttribute('width', w);
        clone.setAttribute('height', h);
        if (!clone.getAttribute('viewBox')) {
            clone.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
        }

        // Serialized SVG has no access to style.css, so give text a default
        // family/fill for anything the renderers left to the stylesheet.
        var T = theme();
        var def = document.createElementNS('http://www.w3.org/2000/svg', 'style');
        def.textContent =
            'text { font-family: ' + T.main + '; }' +
            'text:not([fill]):not([style*="fill"]) { fill: ' + T.text + '; }';
        clone.insertBefore(def, clone.firstChild);

        var xml = new XMLSerializer().serializeToString(clone);
        var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
        return loadImage(url).then(function (img) {
            return { img: img, w: w, h: h };
        });
    }

    function loadImage(src) {
        return new Promise(function (resolve, reject) {
            var img = new Image();
            img.onload  = function () { resolve(img); };
            img.onerror = function () { reject(new Error('image decode failed')); };
            img.src = src;
        });
    }

    /* ── Compositing ────────────────────────────────────────────────────── */

    function compose(src, title, ctx0) {
        var T = theme();
        var head = title ? HEADER : PAD;
        var cw = src.w + PAD * 2;
        var ch = src.h + head + PAD + FOOTER;

        var canvas = document.createElement('canvas');
        canvas.width  = cw * SCALE;
        canvas.height = ch * SCALE;
        var c = canvas.getContext('2d');
        c.scale(SCALE, SCALE);

        c.fillStyle = T.bg;
        c.fillRect(0, 0, cw, ch);

        if (title) {
            c.fillStyle = T.accent;
            c.font = 'bold 19px ' + T.display;
            c.textBaseline = 'alphabetic';
            c.fillText(title.toUpperCase(), PAD, 26);

            if (ctx0) {
                c.fillStyle = T.muted;
                c.font = '12px ' + T.main;
                c.fillText(ctx0, PAD, 43);
            }
            c.strokeStyle = T.border;
            c.lineWidth = 1;
            c.beginPath();
            c.moveTo(PAD, head - 8.5);
            c.lineTo(cw - PAD, head - 8.5);
            c.stroke();
        }

        c.drawImage(src.img, PAD, head, src.w, src.h);

        c.fillStyle = T.muted;
        c.font = '10px ' + T.main;
        c.fillText('Legacy League', PAD, ch - 8);

        return canvas;
    }

    function save(canvas, name) {
        canvas.toBlob(function (blob) {
            if (!blob) throw new Error('canvas encode failed');
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
        }, 'image/png');
    }

    /* ── Click handler ──────────────────────────────────────────────────── */

    function download(card, btn) {
        var titleEl = card.querySelector('.chart-title');
        var title   = titleEl ? titleEl.textContent.trim() : '';
        var gd      = plotlyIn(card);
        var svg     = gd ? null : svgIn(card);

        if (!gd && !svg) { flash(btn, 'No chart'); return; }

        btn.classList.add('is-busy');
        var job = gd ? plotlyImage(gd) : svgImage(svg);

        job.then(function (src) {
            var canvas = compose(src, title, context());
            var yr = (document.getElementById('year-display') || {}).textContent || '';
            save(canvas, ['legacy-league', slug(yr), slug(title)]
                            .filter(Boolean).join('-') + '.png');
            btn.classList.remove('is-busy');
        }).catch(function (e) {
            btn.classList.remove('is-busy');
            flash(btn, 'Failed');
            console.error('[chartdownload]', e);
        });
    }

    function flash(btn, msg) {
        var prev = btn.getAttribute('aria-label');
        btn.setAttribute('aria-label', msg);
        btn.classList.add('is-error');
        setTimeout(function () {
            btn.setAttribute('aria-label', prev);
            btn.classList.remove('is-error');
        }, 1800);
    }

    /* ── Injection ──────────────────────────────────────────────────────── */

    var ICON =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
        'width="15" height="15" aria-hidden="true">' +
        '<path d="M12 3v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/>' +
        '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>';

    function inject() {
        document.querySelectorAll('.chart-card').forEach(function (card) {
            var has = card.querySelector(':scope > .chart-dl');
            if (!exportable(card)) {
                if (has) has.remove();
                return;
            }
            if (has) return;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'chart-dl';
            btn.setAttribute('aria-label', 'Download chart as PNG');
            btn.innerHTML = ICON + '<span>PNG</span>';
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                download(card, btn);
            });
            card.appendChild(btn);
        });
    }

    var pending = null;
    function scheduleInject() {
        if (pending) clearTimeout(pending);
        pending = setTimeout(function () { pending = null; inject(); }, 250);
    }

    function start() {
        inject();
        new MutationObserver(scheduleInject).observe(document.body, {
            childList: true, subtree: true,
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
