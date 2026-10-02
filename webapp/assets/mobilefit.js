/* Phone fit for Plotly charts.
 *
 * Figures are built server-side for a desktop card (~1300px wide). On a narrow
 * card (< NARROW px) this pass shrinks what was sized for desktop:
 *   - fixed left/right margins drop to a minimum; automargin (on in the
 *     gridiron_ink template) then regrows each to exactly what its labels need,
 *     instead of a 160-290px gutter that leaves no room for the bars
 *   - tick fonts cap at 11px and axis titles at 12px; numeric axes keep ~5 ticks
 *   - bar/marker text, annotations and legends cap at phone sizes
 *
 * Runs on every Plotly render, once per figure object: a Dash update brings a
 * new layout object and is re-fitted; our own relayout mutates the same object,
 * so it can't loop. No Dash callback, no app.py wiring — same pattern as
 * chartdownload.js.
 */
(function () {
    'use strict';
    var NARROW = 600;

    function cap(v, max) { return (typeof v === 'number' && v > max) ? max : v; }

    function fit(gd) {
        if (!window.Plotly || !gd.layout || !gd._fullLayout) return;
        if (!gd.clientWidth || gd.clientWidth >= NARROW) return;
        if (gd.__phoneFitFor === gd.layout) return;
        gd.__phoneFitFor = gd.layout;

        var L = gd._fullLayout, upd = {};
        var cartesian = Object.keys(L).some(function (k) { return /^[xy]axis\d*$/.test(k); });
        if (cartesian) {
            // automargin regrows these to fit the tick labels. Polar/pie charts
            // have nothing to regrow them, so they keep the server's margins.
            upd['margin.l'] = Math.min(L.margin.l, 8);
            // Value labels drawn past the bar end live in the right margin.
            upd['margin.r'] = Math.min(L.margin.r, 48);
        }

        Object.keys(L).forEach(function (k) {
            if (!/^[xy]axis\d*$/.test(k)) return;
            var ax = L[k];
            upd[k + '.automargin'] = true;
            upd[k + '.tickfont.size'] = cap(ax.tickfont && ax.tickfont.size, 11);
            if (ax.title && ax.title.font) upd[k + '.title.font.size'] = cap(ax.title.font.size, 12);
            // Names along a narrow top x axis: straight up, never tilted — a
            // tilted label there ran off the left edge of the card. (Bottom axes
            // keep Plotly's choice: vertical names there ran into the legend.)
            if (k[0] === 'x' && ax.type === 'category' && ax.side === 'top') upd[k + '.tickangle'] = -90;
            // Thin out automatic ticks only. An axis with its own tickvals
            // (the timeline's kickoff slots) keeps them.
            if ((ax.type === 'linear' || ax.type === 'date') && ax.tickmode !== 'array') {
                upd[k + '.nticks'] = 5;
                upd[k + '.dtick'] = null;     // a desktop dtick would override nticks
                upd[k + '.tickmode'] = 'auto';
            }
        });
        if (L.legend) upd['legend.font.size'] = cap(L.legend.font && L.legend.font.size, 10);
        // A grid of small panels titles each one; at 12px, neighbouring titles
        // ran together, so grids get 10px.
        var annCap = (L.annotations || []).length >= 6 ? 10 : 12;
        (L.annotations || []).forEach(function (a, i) {
            if (a.font) upd['annotations[' + i + '].font.size'] = cap(a.font.size, annCap);
        });

        // Bar text: cap the size, and let Plotly put it inside the bar when it
        // fits ('auto') instead of always past the end, where a narrow card
        // has no room for it.
        var sizeIdx = [], autoIdx = [], cellIdx = [];
        (gd._fullData || []).forEach(function (t, i) {
            var idx = t.index != null ? t.index : i;
            if (t.textfont && typeof t.textfont.size === 'number' && t.textfont.size > 12) sizeIdx.push(idx);
            if (t.type === 'bar' && t.textposition === 'outside') autoIdx.push(idx);
            // Heatmap cells under ~25px can't hold "7-7"; color and hover carry it.
            if (t.type === 'heatmap' && t.x && t.x.length > 6 && t.texttemplate) cellIdx.push(idx);
        });

        window.Plotly.relayout(gd, upd);
        if (sizeIdx.length) window.Plotly.restyle(gd, { 'textfont.size': 12 }, sizeIdx);
        if (autoIdx.length) window.Plotly.restyle(gd, { textposition: 'auto' }, autoIdx);
        if (cellIdx.length) window.Plotly.restyle(gd, { texttemplate: '' }, cellIdx);
    }

    function hook(gd) {
        if (gd.__phoneFitHooked || typeof gd.on !== 'function') return;
        gd.__phoneFitHooked = true;
        gd.on('plotly_afterplot', function () { fit(gd); });
        fit(gd);
    }

    // One scan per frame however many mutations Dash makes. Plotly adds the
    // js-plotly-plot class to an existing div on first render, so scan the
    // document rather than only the added nodes.
    var queued = false;
    function scanSoon() {
        if (queued) return;
        queued = true;
        window.requestAnimationFrame(function () {
            queued = false;
            document.querySelectorAll('.js-plotly-plot').forEach(hook);
        });
    }
    new MutationObserver(scanSoon)
        .observe(document.documentElement, { childList: true, subtree: true });
})();
