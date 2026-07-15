/* Legacy League — D3 Charts
   All functions receive serialized Python data via Dash dcc.Store.
   Return window.dash_clientside.no_update always (output is the div's data-rendered attr). */

/* Retry helper — waits up to maxMs for a DOM element to appear, then calls fn(el).
   Each new wait for the same id cancels any earlier pending wait (last one wins),
   so repeated store updates while a tab is unmounted can't queue up stacked renders. */
var _waitTokens = {};
function _waitForEl(id, fn, maxMs) {
    var token = (_waitTokens[id] || 0) + 1;
    _waitTokens[id] = token;
    (function poll(remaining) {
        if (_waitTokens[id] !== token) return;   /* superseded by a newer wait */
        var el = document.getElementById(id);
        if (el) { fn(el); return; }
        if (remaining > 0) setTimeout(function() { poll(remaining - 100); }, 100);
    })(maxMs);
}

window.dash_clientside = window.dash_clientside || {};

window.dash_clientside.d3charts = {

/* ── 4A: Snake Graph ─────────────────────────────────────────────────────── */
renderSnakeGraph: function(data, tabValue, mode) {
    if (tabValue !== 'tab-season') return window.dash_clientside.no_update;
    if (!data) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-snake-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderSnakeGraph.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-snake-container', function() { _fn(data, tabValue, mode); }, 3000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';

    var usePoints = (mode === 'points') && data.cumulative_pts;
    var fullSeriesMap = usePoints ? data.cumulative_pts : data.series;
    var yLabel    = usePoints ? 'Points' : 'Wins';

    var margin = {top: 20, right: 140, bottom: 40, left: usePoints ? 70 : 50};
    var width  = container.clientWidth  - margin.left - margin.right;
    var height = container.clientHeight - margin.top  - margin.bottom;
    if (width <= 0) width  = 700;
    if (height <= 0) height = 440;

    var svg = d3.select(container).append('svg')
        .attr('width',  width  + margin.left + margin.right)
        .attr('height', height + margin.top  + margin.bottom)
        .style('background', 'transparent');

    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    // Clip data at current_week
    var allWeeks = data.weeks;
    var currentWeek = data.current_week || allWeeks[allWeeks.length - 1];
    var cutIdx = allWeeks.length - 1;
    for (var ci = 0; ci < allWeeks.length; ci++) {
        if (allWeeks[ci] > currentWeek) { cutIdx = ci - 1; break; }
    }
    var weeks = allWeeks.slice(0, cutIdx + 1);
    var seriesMap = {};
    data.teams.forEach(function(t) {
        seriesMap[t] = (fullSeriesMap[t] || []).slice(0, weeks.length);
    });

    var maxVal = d3.max(data.teams, function(t) { return d3.max(seriesMap[t]); });

    var x = d3.scaleLinear().domain([0, weeks.length - 1]).range([0, width]);
    var y = d3.scaleLinear().domain([0, maxVal * 1.05]).range([height, 0]);

    // Gridlines
    g.append('g').attr('class', 'grid')
        .call(d3.axisLeft(y).tickSize(-width).tickFormat(''))
        .selectAll('line').style('stroke', '#3D5E78').style('stroke-opacity', 0.5);
    g.select('.grid .domain').remove();

    // X Axis
    var xAxisG = g.append('g').attr('transform', 'translate(0,' + height + ')')
        .call(d3.axisBottom(x)
            .tickValues(weeks.filter(function(w) { return w > 0; }))
            .tickFormat(function(d) { return 'Wk ' + d; }));
    xAxisG.selectAll('text')
        .style('fill', '#BDE2FF')
        .style('font-family', 'Courier New')
        .style('font-size', '11px');
    xAxisG.selectAll('line').style('stroke', '#3D5E78');
    xAxisG.select('.domain').style('stroke', '#3D5E78');

    // Y Axis label
    g.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -height / 2)
        .attr('y', -(margin.left - 14))
        .attr('text-anchor', 'middle')
        .style('fill', '#6a9abf')
        .style('font-family', 'Courier New')
        .style('font-size', '11px')
        .text(yLabel);

    // Y Axis ticks
    var yAxisFmt = usePoints ? d3.format('.0f') : d3.format('d');
    var yTicks   = usePoints ? 6 : (maxVal + 1);
    var yAxisG = g.append('g')
        .call(d3.axisLeft(y).ticks(yTicks).tickFormat(yAxisFmt));
    yAxisG.selectAll('text')
        .style('fill', '#BDE2FF')
        .style('font-family', 'Courier New')
        .style('font-size', '11px');
    yAxisG.selectAll('line').style('stroke', '#3D5E78');
    yAxisG.select('.domain').style('stroke', '#3D5E78');

    // Line generator
    var line = d3.line()
        .x(function(d, i) { return x(i); })
        .y(function(d) { return y(d); })
        .curve(d3.curveCatmullRom);

    // Draw lines with animation; collect end-label positions for collision resolution
    var endLabels = [];
    data.teams.forEach(function(team, ti) {
        var color = data.colors[ti];
        var vals  = seriesMap[team];
        if (!vals) return;

        var path = g.append('path')
            .datum(vals)
            .attr('fill', 'none')
            .attr('stroke', color)
            .attr('stroke-width', 2.5)
            .attr('d', line);

        // Animate draw
        var totalLength = path.node().getTotalLength();
        path.attr('stroke-dasharray', totalLength + ' ' + totalLength)
            .attr('stroke-dashoffset', totalLength)
            .transition().duration(2500).ease(d3.easeLinear)
            .attr('stroke-dashoffset', 0);

        var lastVal = vals[vals.length - 1];
        endLabels.push({ team: team, color: color, rawY: y(lastVal), adjY: y(lastVal), x: x(vals.length - 1) + 8 });
    });

    // Resolve vertical collisions: iteratively push overlapping labels apart
    var labelH = 14; // px between label baselines when crowded
    endLabels.sort(function(a, b) { return a.rawY - b.rawY; });
    var maxIter = 50;
    for (var iter = 0; iter < maxIter; iter++) {
        var moved = false;
        for (var i = 1; i < endLabels.length; i++) {
            var gap = endLabels[i].adjY - endLabels[i - 1].adjY;
            if (gap < labelH) {
                var push = (labelH - gap) / 2;
                endLabels[i - 1].adjY -= push;
                endLabels[i].adjY     += push;
                moved = true;
            }
        }
        if (!moved) break;
    }
    // Clamp to chart bounds
    endLabels.forEach(function(lbl) {
        lbl.adjY = Math.max(0, Math.min(height, lbl.adjY));
    });

    // Render end labels at resolved positions
    endLabels.forEach(function(lbl) {
        g.append('text')
            .attr('x', lbl.x)
            .attr('y', lbl.adjY)
            .attr('dy', '0.35em')
            .style('fill', lbl.color)
            .style('font-family', 'Courier New')
            .style('font-size', '11px')
            .style('font-weight', 'bold')
            .text(lbl.team)
            .style('opacity', 0)
            .transition().delay(2400).duration(300)
            .style('opacity', 1);
    });

    // Tooltip div
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute')
        .style('pointer-events', 'none')
        .style('background', '#1a3a52')
        .style('border', '1px solid #2e526e')
        .style('border-radius', '6px')
        .style('padding', '8px 12px')
        .style('font-family', 'Courier New')
        .style('font-size', '12px')
        .style('color', '#BDE2FF')
        .style('opacity', 0)
        .style('z-index', 10);

    // Make container relatively positioned for absolute tooltip
    d3.select(container).style('position', 'relative');

    var crosshair = g.append('line')
        .attr('stroke', '#3D5E78')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '4')
        .attr('y1', 0)
        .attr('y2', height)
        .style('opacity', 0);

    svg.on('mousemove', function(event) {
        var coords = d3.pointer(event, g.node());
        var mx = coords[0];
        var weekIdx = Math.round(x.invert(mx));
        weekIdx = Math.max(0, Math.min(weeks.length - 1, weekIdx));
        var xPos = x(weekIdx);

        crosshair.attr('x1', xPos).attr('x2', xPos).style('opacity', 1);

        var ranked = data.teams.map(function(t, ti) {
            var v = seriesMap[t] ? seriesMap[t][weekIdx] : 0;
            return { team: t, val: v, color: data.colors[ti] };
        }).sort(function(a, b) { return b.val - a.val; });

        var suffix = usePoints ? ' pts' : ' wins';
        var html = '<div style="color:#FFC300;font-weight:bold;margin-bottom:4px">Week ' + weeks[weekIdx] + '</div>';
        ranked.forEach(function(r) {
            var display = usePoints ? r.val.toFixed(1) : r.val;
            html += '<div><span style="color:' + r.color + '">' + r.team + '</span>: ' + display + suffix + '</div>';
        });

        var containerRect = container.getBoundingClientRect();
        var svgRect = svg.node().getBoundingClientRect();
        var leftOffset = (svgRect.left - containerRect.left) + margin.left + xPos + 10;
        tooltip.html(html).style('opacity', 1)
            .style('left', leftOffset + 'px')
            .style('top', '10px');
    }).on('mouseleave', function() {
        crosshair.style('opacity', 0);
        tooltip.style('opacity', 0);
    });

    return window.dash_clientside.no_update;
},

/* ── 4B: Score Race ──────────────────────────────────────────────────────── */
renderScoreRace: function(data, tabValue) {
    if (tabValue !== 'tab-season') return window.dash_clientside.no_update;
    if (!data) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-race-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderScoreRace.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-race-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    try {
    /* Tear down the previous render's autoplay timer and hover listeners —
       the container element survives re-renders, so they'd accumulate otherwise */
    if (container._raceCleanup) container._raceCleanup();
    container.innerHTML = '';

    d3.select(container).style('position', 'relative');

    var margin = {top: 20, right: 160, bottom: 50, left: 50};
    var width  = container.clientWidth  - margin.left - margin.right;
    var height = container.clientHeight - margin.top  - margin.bottom;
    if (width <= 0) width  = 700;
    if (height <= 0) height = 430;

    var svg = d3.select(container).append('svg')
        .attr('width',  width  + margin.left + margin.right)
        .attr('height', height + margin.top  + margin.bottom)
        .style('background', 'transparent');
    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    var colorMap = {};
    data.teams.forEach(function(t, i) { colorMap[t] = data.colors[i]; });

    var totalWeeks = data.weeks.length;
    var currentFrame = [0];
    var playing = [true];

    function getFrameData(weekIdx) {
        return data.teams.map(function(t) {
            return { team: t, value: data.cumulative[t][weekIdx] || 0, color: colorMap[t] };
        }).sort(function(a, b) { return b.value - a.value; });
    }

    var maxVal = d3.max(data.teams, function(t) { return d3.max(data.cumulative[t]); });
    var x = d3.scaleLinear().domain([0, maxVal]).range([0, width]);
    var y = d3.scaleBand().domain(d3.range(data.teams.length)).range([0, height]).padding(0.2);

    // X Axis
    var xAxisG = g.append('g').attr('transform', 'translate(0,' + height + ')')
        .call(d3.axisBottom(x).ticks(5).tickFormat(function(d) { return d.toFixed(0); }));
    xAxisG.selectAll('text').style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '11px');
    xAxisG.selectAll('line').style('stroke', '#3D5E78');
    xAxisG.select('.domain').style('stroke', '#3D5E78');

    // Week counter label
    var weekLabel = g.append('text')
        .attr('x', width)
        .attr('y', height - 10)
        .attr('text-anchor', 'end')
        .style('fill', '#FFC300')
        .style('font-family', 'Courier New')
        .style('font-size', '28px')
        .style('font-weight', 'bold')
        .style('opacity', 0.3)
        .text('Wk 1');

    function update(weekIdx, animate) {
        var frameData = getFrameData(weekIdx);
        var dur = animate ? 600 : 0;

        weekLabel.text('Wk ' + data.weeks[weekIdx]);

        var bars = g.selectAll('.race-bar').data(frameData, function(d) { return d.team; });
        bars.enter().append('rect').attr('class', 'race-bar')
            .attr('x', 0).attr('height', y.bandwidth()).attr('rx', 4)
            .merge(bars)
            .transition().duration(dur).ease(d3.easeCubicInOut)
            .attr('y', function(d, i) { return y(i); })
            .attr('width', function(d) { return x(d.value); })
            .attr('fill', function(d) { return d.color; })
            .attr('fill-opacity', 0.85);

        var labels = g.selectAll('.race-label').data(frameData, function(d) { return d.team; });
        labels.enter().append('text').attr('class', 'race-label')
            .style('font-family', 'Courier New')
            .style('font-size', '12px')
            .style('font-weight', 'bold')
            .merge(labels)
            .transition().duration(dur).ease(d3.easeCubicInOut)
            .attr('x', function(d) { return x(d.value) + 4; })
            .attr('y', function(d, i) { return y(i) + y.bandwidth() / 2; })
            .attr('dy', '0.35em')
            .style('fill', function(d) { return d.color; })
            .text(function(d) { return d.team + '  ' + d.value.toFixed(1); });
    }

    update(Math.min(currentFrame[0], totalWeeks - 1), false);

    // Autoplay
    var timer = d3.interval(function() {
        if (!playing[0]) return;
        currentFrame[0]++;
        if (currentFrame[0] >= totalWeeks) {
            timer.stop();
            playing[0] = false;
            return;
        }
        update(currentFrame[0], true);
    }, 800);

    // Pause on hover
    var onEnter = function() { playing[0] = false; };
    var onLeave = function() {
        if (currentFrame[0] < totalWeeks - 1) playing[0] = true;
    };
    container.addEventListener('mouseenter', onEnter);
    container.addEventListener('mouseleave', onLeave);

    container._raceCleanup = function() {
        timer.stop();
        playing[0] = false;
        container.removeEventListener('mouseenter', onEnter);
        container.removeEventListener('mouseleave', onLeave);
        container._raceCleanup = null;
    };

    } catch(e) { console.error('[ScoreRace]', e); }
    return window.dash_clientside.no_update;
},

/* ── 4D: Score Heatmap ───────────────────────────────────────────────────── */
renderHeatmap: function(data, tabValue) {
    if (tabValue !== 'tab-season') return window.dash_clientside.no_update;
    if (!data) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-heatmap-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderHeatmap.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-heatmap-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    try {
    container.innerHTML = '';

    d3.select(container).style('position', 'relative');

    var nTeams = data.teams.length;
    var nWeeks = data.weeks.length;
    var margin = {top: 30, right: 20, bottom: 20, left: 100};
    var width  = container.clientWidth  - margin.left - margin.right;
    var height = container.clientHeight - margin.top  - margin.bottom;
    if (width <= 0) width  = 700;
    if (height <= 0) height = 360;

    var cellW = width  / nWeeks;
    var cellH = height / nTeams;

    var svg = d3.select(container).append('svg')
        .attr('width',  width  + margin.left + margin.right)
        .attr('height', height + margin.top  + margin.bottom)
        .style('background', 'transparent');
    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    // Color scale: diverging red→neutral→green centered on 0 deviation
    var color = d3.scaleDiverging(d3.interpolateRdYlGn).domain([-0.25, 0, 0.25]);

    // Week labels (top)
    g.selectAll('.wk-label').data(data.weeks).enter().append('text').attr('class', 'wk-label')
        .attr('x', function(d, i) { return i * cellW + cellW / 2; })
        .attr('y', -8)
        .attr('text-anchor', 'middle')
        .style('fill', '#BDE2FF')
        .style('font-family', 'Courier New')
        .style('font-size', '10px')
        .text(function(d) { return 'W' + d; });

    // Team labels (left)
    g.selectAll('.team-label').data(data.teams).enter().append('text').attr('class', 'team-label')
        .attr('x', -6)
        .attr('y', function(d, i) { return i * cellH + cellH / 2; })
        .attr('dy', '0.35em')
        .attr('text-anchor', 'end')
        .style('fill', function(d) { return (data.teamcolors && data.teamcolors[d]) ? data.teamcolors[d] : '#BDE2FF'; })
        .style('font-family', 'Courier New')
        .style('font-size', '11px')
        .style('font-weight', 'bold')
        .text(function(d) { return d; });

    // Tooltip
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute')
        .style('pointer-events', 'none')
        .style('background', '#1a3a52')
        .style('border', '1px solid #2e526e')
        .style('border-radius', '6px')
        .style('padding', '8px 12px')
        .style('font-family', 'Courier New')
        .style('font-size', '12px')
        .style('color', '#BDE2FF')
        .style('opacity', 0)
        .style('z-index', 10);

    // Cells — animate column by column
    data.teams.forEach(function(team, ti) {
        data.weeks.forEach(function(wk, wi) {
            var scoresForTeam = data.scores[team] || {};
            var cell = scoresForTeam[wk] || scoresForTeam[String(wk)];
            if (!cell) return;
            var dev = (cell.score - cell.avg) / (cell.avg || 1);

            g.append('rect')
                .attr('x', wi * cellW + 1)
                .attr('y', ti * cellH + 1)
                .attr('width', cellW - 2)
                .attr('height', cellH - 2)
                .attr('rx', 3)
                .attr('fill', color(dev))
                .attr('opacity', 0)
                .on('mouseover', function(event) {
                    var result = cell.won ? 'W' : 'L';
                    var devStr = (dev >= 0 ? '+' : '') + (dev * 100).toFixed(1) + '%';
                    tooltip.html(
                        '<b>' + team + '</b> · Week ' + wk + '<br>' +
                        result + ' · ' + cell.score.toFixed(1) + ' pts<br>' +
                        'vs ' + cell.opp + ' (' + cell.opp_score.toFixed(1) + ')<br>' +
                        'vs avg: ' + devStr
                    ).style('opacity', 1)
                     .style('left', (event.offsetX + 10) + 'px')
                     .style('top',  (event.offsetY + 10) + 'px');
                })
                .on('mouseleave', function() { tooltip.style('opacity', 0); })
                .transition().delay(wi * 60).duration(300)
                .attr('opacity', 0.85);

            // Win/loss indicator dot
            g.append('circle')
                .attr('cx', wi * cellW + cellW - 6)
                .attr('cy', ti * cellH + 6)
                .attr('r', 3)
                .attr('fill', cell.won ? '#90BE6D' : '#F94144')
                .attr('opacity', 0)
                .transition().delay(wi * 60 + 200).duration(200)
                .attr('opacity', 1);
        });
    });

    } catch(e) { console.error('[Heatmap]', e); }
    return window.dash_clientside.no_update;
},

/* ── 4C: NFL Contribution Bubble Map ─────────────────────────────────────── */
renderBubbleMap: function(data, tabValue) {
    if (tabValue !== 'tab-week') return window.dash_clientside.no_update;
    if (!data || !data.teams || !data.teams.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-bubble-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderBubbleMap.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-bubble-container', function() { _fn(data, tabValue); }, 8000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';

    d3.select(container).style('position', 'relative');

    var width  = container.clientWidth  || 800;
    var height = container.clientHeight || 460;

    var svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height)
        .style('background', 'transparent');

    // Albers USA projection
    var projection = d3.geoAlbersUsa()
        .scale(Math.min(width / 960, height / 600) * 1070 * 0.85)
        .translate([width / 2, height / 2]);

    var path = d3.geoPath().projection(projection);

    // Scales
    var maxPts = d3.max(data.teams, function(d) { return d.fantasy_pts; }) || 1;
    var r = d3.scaleSqrt().domain([0, maxPts]).range([4, 36]);
    var deviation = function(d) { return (d.fantasy_pts - d.season_avg) / (d.season_avg || 1); };
    var colorScale = d3.scaleDiverging(d3.interpolateRdYlGn).domain([-0.4, 0, 0.4]);

    // Load US map then draw bubbles
    var usUrl = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json';
    d3.json(usUrl).then(function(us) {
        // Draw states
        svg.append('g')
            .selectAll('path')
            .data(topojson.feature(us, us.objects.states).features)
            .enter().append('path')
            .attr('d', path)
            .attr('fill', '#163146')
            .attr('stroke', '#2e526e')
            .attr('stroke-width', 0.5);

        // Draw bubbles
        var tooltip = d3.select(container).append('div')
            .style('position', 'absolute').style('pointer-events', 'none')
            .style('background', '#1a3a52').style('border', '1px solid #2e526e')
            .style('border-radius', '6px').style('padding', '8px 12px')
            .style('font-family', 'Courier New').style('font-size', '12px')
            .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10);

        data.teams.forEach(function(d) {
            var coords = projection([d.lon, d.lat]);
            if (!coords) return;

            svg.append('circle')
                .attr('cx', coords[0]).attr('cy', coords[1])
                .attr('r', 0)
                .attr('fill', colorScale(deviation(d)))
                .attr('fill-opacity', 0.75)
                .attr('stroke', '#BDE2FF').attr('stroke-width', 0.5)
                .on('mouseover', function(event) {
                    var dev = deviation(d);
                    tooltip.html(
                        '<b>' + d.nfl_team + '</b><br>' +
                        'Fantasy pts: <b>' + d.fantasy_pts.toFixed(1) + '</b><br>' +
                        'Season avg: ' + d.season_avg.toFixed(1) + '<br>' +
                        'Top: ' + d.top_player + ' (' + d.top_player_pts.toFixed(1) + ')<br>' +
                        (dev >= 0 ? '+' : '') + (dev * 100).toFixed(1) + '% vs avg'
                    ).style('opacity', 1)
                     .style('left', (event.offsetX + 12) + 'px')
                     .style('top',  (event.offsetY + 12) + 'px');
                })
                .on('mouseleave', function() { tooltip.style('opacity', 0); })
                .transition().duration(600).ease(d3.easeBackOut)
                .attr('r', r(d.fantasy_pts));

            // Label
            svg.append('text')
                .attr('x', coords[0]).attr('y', coords[1])
                .attr('dy', '0.35em').attr('text-anchor', 'middle')
                .style('fill', '#0d1e2e').style('font-family', 'Courier New')
                .style('font-size', Math.min(10, r(d.fantasy_pts) * 0.55) + 'px')
                .style('font-weight', 'bold').style('pointer-events', 'none')
                .style('opacity', 0)
                .text(d.nfl_team)
                .transition().delay(500).duration(300)
                .style('opacity', r(d.fantasy_pts) > 12 ? 1 : 0);
        });
    }).catch(function(err) {
        svg.append('text').attr('x', width/2).attr('y', height/2)
            .attr('text-anchor', 'middle')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '14px')
            .text('Map unavailable — check network connection');
    });

    return window.dash_clientside.no_update;
},

/* ── 4E: Draft Board Replay ───────────────────────────────────────────────── */
renderDraftBoard: function(data, tabValue) {
    if (tabValue !== 'tab-season') return window.dash_clientside.no_update;
    if (!data || !data.picks || !data.picks.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-draft-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderDraftBoard.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-draft-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';

    d3.select(container).style('position', 'relative');

    var picks = data.picks;
    var rounds = d3.max(picks, function(d) { return d.round; });
    // Figure out picks per round
    var picksPerRound = Math.ceil(picks.length / rounds);

    var margin = {top: 40, right: 20, bottom: 20, left: 20};
    var width  = container.clientWidth  - margin.left - margin.right || 760;
    var height = container.clientHeight - margin.top  - margin.bottom || 500;

    var cellW = Math.floor(width  / picksPerRound);
    var cellH = Math.floor(height / rounds);

    var svg = d3.select(container).append('svg')
        .attr('width',  width  + margin.left + margin.right)
        .attr('height', height + margin.top  + margin.bottom)
        .style('background', 'transparent');
    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    // Column headers (pick slots)
    for (var slot = 1; slot <= picksPerRound; slot++) {
        g.append('text')
            .attr('x', (slot - 1) * cellW + cellW / 2).attr('y', -12)
            .attr('text-anchor', 'middle')
            .style('fill', '#6a9abf').style('font-family', 'Courier New').style('font-size', '10px')
            .text(slot);
    }

    // Row headers (rounds)
    for (var rnd = 1; rnd <= rounds; rnd++) {
        g.append('text')
            .attr('x', -4).attr('y', (rnd - 1) * cellH + cellH / 2)
            .attr('dy', '0.35em').attr('text-anchor', 'end')
            .style('fill', '#6a9abf').style('font-family', 'Courier New').style('font-size', '10px')
            .text('R' + rnd);
    }

    var tierColors = { elite: '#FFC300', solid: '#90BE6D', average: '#BDE2FF', bust: '#F94144' };

    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute').style('pointer-events', 'none')
        .style('background', '#1a3a52').style('border', '1px solid #2e526e')
        .style('border-radius', '6px').style('padding', '8px 12px')
        .style('font-family', 'Courier New').style('font-size', '12px')
        .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10);

    // Animate picks in snake order
    picks.forEach(function(pick, i) {
        var rnd  = pick.round;
        var slot = ((pick.pick - 1) % picksPerRound) + 1;
        // Snake order: odd rounds go left-to-right, even go right-to-left
        var col  = (rnd % 2 === 1) ? (slot - 1) : (picksPerRound - slot);
        var cx   = col  * cellW;
        var cy   = (rnd - 1) * cellH;

        var cell = g.append('g')
            .attr('transform', 'translate(' + cx + ',' + cy + ')')
            .style('opacity', 0)
            .style('cursor', 'pointer');

        cell.append('rect')
            .attr('width', cellW - 2).attr('height', cellH - 2)
            .attr('rx', 3)
            .attr('fill', pick.color)
            .attr('fill-opacity', 0.25)
            .attr('stroke', pick.color)
            .attr('stroke-width', 1)
            .attr('stroke-opacity', 0.5);

        // Player name (truncated)
        var nameParts = pick.player.split(' ');
        var shortName = nameParts.length > 1 ? nameParts[0][0] + '. ' + nameParts[nameParts.length - 1] : pick.player;
        cell.append('text')
            .attr('x', (cellW - 2) / 2).attr('y', (cellH - 2) / 2 - 4)
            .attr('dy', '0.35em').attr('text-anchor', 'middle')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New')
            .style('font-size', Math.min(10, cellW / 7) + 'px')
            .text(shortName);

        cell.append('text')
            .attr('x', (cellW - 2) / 2).attr('y', (cellH - 2) / 2 + 8)
            .attr('text-anchor', 'middle')
            .style('fill', pick.color).style('font-family', 'Courier New')
            .style('font-size', Math.min(8, cellW / 9) + 'px')
            .text(pick.position);

        cell.on('mouseover', function(event) {
            tooltip.html(
                '<b>' + pick.player + '</b> (' + pick.position + ')<br>' +
                'Team: ' + pick.team + '<br>' +
                'Pick: Rd ' + pick.round + '<br>' +
                'Season pts: <b>' + pick.total_pts + '</b><br>' +
                'Tier: <span style="color:' + tierColors[pick.tier] + '">' + pick.tier.toUpperCase() + '</span>'
            ).style('opacity', 1)
             .style('left', (event.offsetX + 10) + 'px')
             .style('top',  (event.offsetY + 10) + 'px');
        }).on('mouseleave', function() { tooltip.style('opacity', 0); });

        cell.transition().delay(i * 100).duration(250)
            .style('opacity', 1);

        // Phase 2: after all picks revealed, recolor by value tier
        if (i === picks.length - 1) {
            setTimeout(function() {
                g.selectAll('g').each(function(_, idx) {
                    var p = picks[idx];
                    if (!p) return;
                    var tColor = tierColors[p.tier] || '#BDE2FF';
                    d3.select(this).select('rect')
                        .transition().duration(600).delay(idx * 30)
                        .attr('fill', tColor)
                        .attr('fill-opacity', 0.4)
                        .attr('stroke', tColor);
                });
            }, (picks.length * 100) + 800);
        }
    });

    // Legend
    var legendData = [
        {label: 'Elite (200+ pts)', color: '#FFC300'},
        {label: 'Solid (120–199)', color: '#90BE6D'},
        {label: 'Average (60–119)', color: '#BDE2FF'},
        {label: 'Bust (<60)',  color: '#F94144'},
    ];
    var legend = svg.append('g').attr('transform', 'translate(' + (margin.left + width - 200) + ', 8)');
    legendData.forEach(function(d, i) {
        legend.append('rect').attr('x', 0).attr('y', i * 14).attr('width', 10).attr('height', 10).attr('fill', d.color).attr('rx', 2);
        legend.append('text').attr('x', 14).attr('y', i * 14 + 5).attr('dy', '0.35em')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '10px')
            .text(d.label);
    });

    return window.dash_clientside.no_update;
},

/* ── 4F: State Choropleth — Fantasy Points by State ─────────────────────── */
renderChoropleth: function(data, tabValue) {
    if (tabValue !== 'tab-alltime') return window.dash_clientside.no_update;
    if (!data || !data.states || !data.states.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-choropleth-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderChoropleth.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-choropleth-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';
    d3.select(container).style('position', 'relative');

    var width  = container.clientWidth  || 820;
    var height = container.clientHeight || 480;

    // FIPS → state data lookup (TopoJSON uses numeric IDs matching FIPS)
    var stateMap = {};
    data.states.forEach(function(s) { stateMap[parseInt(s.fips, 10)] = s; });

    // sqrt scale so mid-range states aren't washed out by CA/FL/TX
    var colorScale = d3.scaleSequentialSqrt()
        .domain([0, data.max_pts])
        .interpolator(d3.interpolateRgb('#1a3a52', '#FFC300'));

    var svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height)
        .style('background', 'transparent');

    var projection = d3.geoAlbersUsa()
        .scale(Math.min(width / 960, height / 600) * 1070 * 0.85)
        .translate([width / 2, height / 2]);
    var path = d3.geoPath().projection(projection);

    // Tooltip
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute').style('pointer-events', 'none')
        .style('background', '#1a3a52').style('border', '1px solid #2e526e')
        .style('border-radius', '6px').style('padding', '9px 13px')
        .style('font-family', 'Courier New').style('font-size', '12px')
        .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10)
        .style('max-width', '200px').style('line-height', '1.6');

    d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json').then(function(us) {
        var features = topojson.feature(us, us.objects.states).features;

        // ── Filled states ─────────────────────────────────────────────────
        svg.append('g').selectAll('path')
            .data(features)
            .enter().append('path')
            .attr('d', path)
            .attr('fill', function(d) {
                var s = stateMap[d.id];
                return s ? colorScale(s.total_pts) : '#163146';
            })
            .attr('stroke', '#0d1e2e')
            .attr('stroke-width', 0.5)
            .style('cursor', function(d) { return stateMap[d.id] ? 'pointer' : 'default'; })
            .on('mouseover', function(event, d) {
                var s = stateMap[d.id];
                if (!s) return;
                // Teams sorted by pts descending
                var teamLines = Object.entries(s.teams)
                    .sort(function(a, b) { return b[1] - a[1]; })
                    .map(function(e) { return e[0] + ': ' + e[1].toFixed(1); })
                    .join('<br>');
                tooltip.html(
                    '<b>' + s.name + '</b><br>' +
                    'Total: <b>' + s.total_pts.toFixed(1) + ' pts</b><br>' +
                    '<span style="color:#6a9abf">' + teamLines + '</span>'
                ).style('opacity', 1)
                 .style('left', (event.offsetX + 14) + 'px')
                 .style('top',  (event.offsetY - 10) + 'px');
                d3.select(this)
                    .raise()
                    .attr('stroke', '#FFC300')
                    .attr('stroke-width', 1.8);
            })
            .on('mousemove', function(event) {
                tooltip.style('left', (event.offsetX + 14) + 'px')
                       .style('top',  (event.offsetY - 10) + 'px');
            })
            .on('mouseleave', function(event, d) {
                tooltip.style('opacity', 0);
                d3.select(this).attr('stroke', '#0d1e2e').attr('stroke-width', 0.5);
            });

        // ── State mesh (crisp interior borders) ───────────────────────────
        svg.append('path')
            .datum(topojson.mesh(us, us.objects.states, function(a, b) { return a !== b; }))
            .attr('d', path)
            .attr('fill', 'none')
            .attr('stroke', '#0d1e2e')
            .attr('stroke-width', 0.4);

        // ── Gradient legend bar (bottom-right) ────────────────────────────
        var legW = 180;
        var legH = 12;
        var legX = width - legW - 20;
        var legY = height - 54;

        var defs = svg.append('defs');
        var grad = defs.append('linearGradient')
            .attr('id', 'choro-gradient')
            .attr('x1', '0%').attr('x2', '100%');
        grad.append('stop').attr('offset', '0%')
            .attr('stop-color', '#1a3a52');
        grad.append('stop').attr('offset', '100%')
            .attr('stop-color', '#FFC300');

        var legG = svg.append('g').attr('transform', 'translate(' + legX + ',' + legY + ')');

        // Panel background
        legG.append('rect')
            .attr('x', -10).attr('y', -20)
            .attr('width', legW + 20).attr('height', legH + 44)
            .attr('rx', 6)
            .attr('fill', 'rgba(13,30,46,0.88)')
            .attr('stroke', '#2e526e').attr('stroke-width', 1);

        legG.append('text')
            .attr('x', 0).attr('y', -8)
            .style('fill', '#6a9abf')
            .style('font-family', 'Courier New')
            .style('font-size', '9px')
            .style('letter-spacing', '1.2px')
            .text('ALL-TIME FANTASY PTS');

        legG.append('rect')
            .attr('width', legW).attr('height', legH).attr('rx', 2)
            .attr('fill', 'url(#choro-gradient)')
            .attr('stroke', '#2e526e').attr('stroke-width', 0.5);

        legG.append('text')
            .attr('x', 0).attr('y', legH + 14)
            .style('fill', '#6a9abf')
            .style('font-family', 'Courier New')
            .style('font-size', '9px')
            .text('0');

        legG.append('text')
            .attr('x', legW).attr('y', legH + 14)
            .attr('text-anchor', 'end')
            .style('fill', '#6a9abf')
            .style('font-family', 'Courier New')
            .style('font-size', '9px')
            .text(data.max_pts.toFixed(0) + ' pts');

        // Midpoint tick
        var midPts = Math.sqrt(data.max_pts) * Math.sqrt(data.max_pts) / 2;
        var midX   = legW * Math.sqrt(midPts / data.max_pts);
        legG.append('line')
            .attr('x1', midX).attr('x2', midX)
            .attr('y1', legH).attr('y2', legH + 5)
            .attr('stroke', '#6a9abf').attr('stroke-width', 1);
        legG.append('text')
            .attr('x', midX).attr('y', legH + 14)
            .attr('text-anchor', 'middle')
            .style('fill', '#6a9abf')
            .style('font-family', 'Courier New')
            .style('font-size', '9px')
            .text(midPts.toFixed(0));

    }).catch(function() {
        svg.append('text').attr('x', width / 2).attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '14px')
            .text('Map unavailable — check network connection');
    });

    return window.dash_clientside.no_update;
},

/* ── 4G: Owner Territory Map ─────────────────────────────────────────────── */
renderTerritoryMap: function(data, tabValue) {
    if (tabValue !== 'tab-alltime') return window.dash_clientside.no_update;
    if (!data || !data.nfl_teams || !data.nfl_teams.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-territory-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderTerritoryMap.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-territory-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';
    d3.select(container).style('position', 'relative');

    var width    = container.clientWidth  || 820;
    var height   = container.clientHeight || 580;
    var nflTeams = data.nfl_teams;
    var owners   = data.fantasy_owners;
    var colors   = data.colors;
    var matrix   = data.matrix;   // [nfl_team_idx][owner_idx] = all-time pts
    var stadiums = data.stadium_coords || {};

    // ── Per-team stats: top owner, runner-up, total ───────────────────────
    var teamInfo = {};
    var maxTopPts = 0;
    nflTeams.forEach(function(team, ti) {
        var row = matrix[ti] || [];
        var ranked = owners.map(function(o, oi) { return { owner: o, pts: row[oi] || 0 }; })
                           .sort(function(a, b) { return b.pts - a.pts; });
        var total = ranked.reduce(function(s, x) { return s + x.pts; }, 0);
        teamInfo[team] = { top: ranked[0], runner: ranked[1], total: total };
        if (ranked[0] && ranked[0].pts > maxTopPts) maxTopPts = ranked[0].pts;
    });

    var rScale = d3.scaleSqrt().domain([0, maxTopPts]).range([9, 30]);

    // ── Slight position offsets for shared stadiums ───────────────────────
    var offsets = { NYG: [-10, -8], NYJ: [10, 8], LA: [-10, 0], LAC: [10, 0] };

    // ── SVG setup ─────────────────────────────────────────────────────────
    var svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height)
        .style('background', 'transparent');

    var projection = d3.geoAlbersUsa()
        .scale(Math.min(width / 960, height / 600) * 1070 * 0.85)
        .translate([width / 2, height / 2]);
    var path = d3.geoPath().projection(projection);

    // ── Tooltip ───────────────────────────────────────────────────────────
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute').style('pointer-events', 'none')
        .style('background', '#1a3a52').style('border', '1px solid #2e526e')
        .style('border-radius', '6px').style('padding', '9px 13px')
        .style('font-family', 'Courier New').style('font-size', '12px')
        .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10)
        .style('max-width', '220px').style('line-height', '1.5');

    // ── Load TopoJSON then render ─────────────────────────────────────────
    d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json').then(function(us) {

        // States base layer
        svg.append('g').selectAll('path')
            .data(topojson.feature(us, us.objects.states).features)
            .enter().append('path')
            .attr('d', path)
            .attr('fill', '#163146')
            .attr('stroke', '#2e526e')
            .attr('stroke-width', 0.6);

        // State borders (inner borders between states)
        svg.append('path')
            .datum(topojson.mesh(us, us.objects.states, function(a, b) { return a !== b; }))
            .attr('d', path)
            .attr('fill', 'none')
            .attr('stroke', '#2e526e')
            .attr('stroke-width', 0.4);

        // ── Draw one circle per NFL team ──────────────────────────────────
        var circleG = svg.append('g');

        nflTeams.forEach(function(team) {
            var sc = stadiums[team];
            if (!sc) return;
            var info = teamInfo[team];
            if (!info || !info.top || info.top.pts === 0) return;

            var proj = projection([sc.lon, sc.lat]);
            if (!proj) return;

            var off = offsets[team] || [0, 0];
            var cx = proj[0] + off[0];
            var cy = proj[1] + off[1];
            var r  = rScale(info.top.pts);
            var ownerColor = colors[info.top.owner] || '#BDE2FF';

            // Contested: top margin < 12% of total → dashed stroke
            var margin = info.runner ? info.top.pts - info.runner.pts : info.top.pts;
            var isContested = info.total > 0 && (margin / info.total) < 0.08;

            circleG.append('circle')
                .attr('cx', cx).attr('cy', cy).attr('r', 0)
                .attr('fill', ownerColor)
                .attr('fill-opacity', 0.82)
                .attr('stroke', isContested ? '#FFC300' : '#0d1e2e')
                .attr('stroke-width', isContested ? 2.5 : 1.5)
                .attr('stroke-dasharray', isContested ? '4,2' : null)
                .style('cursor', 'pointer')
                .on('mouseover', function(event) {
                    var runnerLine = info.runner && info.runner.pts > 0
                        ? '<br><span style="color:#6a9abf">2nd: ' + info.runner.owner
                            + ' · ' + info.runner.pts.toFixed(1) + ' pts</span>'
                        : '';
                    var contestedBadge = isContested
                        ? '<br><span style="color:#FFC300">⚡ Contested territory</span>'
                        : '';
                    tooltip.html(
                        '<b style="color:' + ownerColor + '">' + team + '</b><br>' +
                        '🏆 <b>' + info.top.owner + '</b> · ' + info.top.pts.toFixed(1) + ' pts' +
                        runnerLine + contestedBadge +
                        '<br><span style="color:#3D5E78">Total from ' + team + ': ' + info.total.toFixed(1) + '</span>'
                    ).style('opacity', 1)
                     .style('left', (event.offsetX + 14) + 'px')
                     .style('top',  (event.offsetY - 10) + 'px');
                })
                .on('mousemove', function(event) {
                    tooltip.style('left', (event.offsetX + 14) + 'px')
                           .style('top',  (event.offsetY - 10) + 'px');
                })
                .on('mouseleave', function() { tooltip.style('opacity', 0); })
                .transition().duration(700).delay(Math.random() * 300).ease(d3.easeBackOut)
                .attr('r', r);

            // Team abbreviation label (only if circle is big enough)
            circleG.append('text')
                .attr('x', cx).attr('y', cy).attr('dy', '0.35em')
                .attr('text-anchor', 'middle')
                .style('fill', '#0d1e2e')
                .style('font-family', 'Courier New')
                .style('font-size', Math.min(9, r * 0.55) + 'px')
                .style('font-weight', 'bold')
                .style('pointer-events', 'none')
                .style('opacity', 0)
                .text(team)
                .transition().delay(800).duration(300)
                .style('opacity', r > 13 ? 1 : 0);
        });

        // ── Legend (bottom-left panel) ────────────────────────────────────
        var legPad  = 10;
        var legRowH = 18;
        var legW    = 158;
        var legH    = owners.length * legRowH + legPad * 2 + 14;
        var legX    = 10;
        var legY    = height - legH - 8;

        var legG = svg.append('g').attr('transform', 'translate(' + legX + ',' + legY + ')');
        legG.append('rect')
            .attr('width', legW).attr('height', legH)
            .attr('rx', 6).attr('ry', 6)
            .attr('fill', 'rgba(13,30,46,0.88)')
            .attr('stroke', '#2e526e').attr('stroke-width', 1);

        legG.append('text')
            .attr('x', legPad).attr('y', legPad + 6)
            .style('fill', '#6a9abf')
            .style('font-family', 'Courier New')
            .style('font-size', '9px')
            .style('letter-spacing', '1.5px')
            .style('text-transform', 'uppercase')
            .text('Fantasy Owner');

        owners.forEach(function(owner, i) {
            var oc = colors[owner] || '#BDE2FF';
            var gy = legPad + 16 + i * legRowH;
            legG.append('circle').attr('cx', legPad + 5).attr('cy', gy + 4)
                .attr('r', 5).attr('fill', oc);
            legG.append('text').attr('x', legPad + 15).attr('y', gy + 4).attr('dy', '0.35em')
                .style('fill', '#BDE2FF')
                .style('font-family', 'Courier New')
                .style('font-size', '11px')
                .text(owner);
        });

        // ── Subtitle ─────────────────────────────────────────────────────
        svg.append('text')
            .attr('x', width / 2).attr('y', height - 8)
            .attr('text-anchor', 'middle')
            .style('fill', '#3D5E78')
            .style('font-family', 'Courier New')
            .style('font-size', '10px')
            .text('Circle size = pts from that franchise · Dashed gold border = contested (<8% margin)');

    }).catch(function() {
        svg.append('text').attr('x', width / 2).attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '14px')
            .text('Map unavailable — check network connection');
    });

    return window.dash_clientside.no_update;
},

/* ── 4G: NFL City → Fantasy Owner Arc Map ───────────────────────────────── */
renderArcMap: function(data, tabValue, mode) {
    if (tabValue !== 'tab-alltime') return window.dash_clientside.no_update;
    if (!data || !data.nfl_teams || !data.nfl_teams.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-arc-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderArcMap.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-arc-container', function() { _fn(data, tabValue, mode); }, 20000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';
    d3.select(container).style('position', 'relative');

    mode = mode || 'top';

    var width    = container.clientWidth  || 860;
    var height   = container.clientHeight || 580;
    var nflTeams = data.nfl_teams;
    var owners   = data.fantasy_owners;
    var colors   = data.colors;
    var matrix   = data.matrix;
    var stadiums = data.stadium_coords || {};

    // ── Layout split: map left, owner labels right ────────────────────────
    var mapW   = Math.floor(width * 0.67);
    var labelX = mapW + 28;   // left edge of label column
    var divX   = mapW + 14;   // divider line x

    // ── Build arc objects ─────────────────────────────────────────────────
    var allArcs = [];
    nflTeams.forEach(function(team, ti) {
        var row = matrix[ti] || [];
        owners.forEach(function(owner, oi) {
            var pts = row[oi] || 0;
            if (pts > 0) allArcs.push({ team: team, owner: owner, oi: oi, pts: pts });
        });
    });

    // Filter by mode
    var arcs;
    if (mode === 'top') {
        var best = {};
        allArcs.forEach(function(a) {
            if (!best[a.team] || a.pts > best[a.team].pts) best[a.team] = a;
        });
        arcs = Object.values(best);
    } else if (mode === 'significant') {
        arcs = allArcs.filter(function(a) { return a.pts >= 100; });
    } else {
        arcs = allArcs.filter(function(a) { return a.pts >= 15; });
    }

    // Sort ascending so thick arcs paint on top
    arcs.sort(function(a, b) { return a.pts - b.pts; });

    var maxPts     = d3.max(arcs, function(a) { return a.pts; }) || 1;
    var strokeW    = d3.scaleSqrt().domain([0, maxPts]).range([0.8, 5.5]);
    var baseOpacity = mode === 'all' ? 0.32 : 0.55;

    // ── Owner label y-positions (evenly spaced) ───────────────────────────
    var padTop = 55, padBot = 30;
    var span   = height - padTop - padBot;
    var ownerY = {};
    owners.forEach(function(o, i) {
        ownerY[o] = padTop + (i / Math.max(owners.length - 1, 1)) * span;
    });

    // ── SVG ───────────────────────────────────────────────────────────────
    var svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height)
        .style('background', 'transparent');

    // Clip map content to left panel so fills don't bleed into label area
    var defs = svg.append('defs');
    defs.append('clipPath').attr('id', 'arc-map-clip')
        .append('rect').attr('width', mapW).attr('height', height);

    var projection = d3.geoAlbersUsa()
        .scale(mapW * 1.28)
        .translate([mapW / 2, height / 2]);
    var geoPath = d3.geoPath().projection(projection);

    // ── Tooltip ───────────────────────────────────────────────────────────
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute').style('pointer-events', 'none')
        .style('background', '#1a3a52').style('border', '1px solid #2e526e')
        .style('border-radius', '6px').style('padding', '9px 13px')
        .style('font-family', 'Courier New').style('font-size', '12px')
        .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10)
        .style('max-width', '210px').style('line-height', '1.6');

    d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json').then(function(us) {
        var features = topojson.feature(us, us.objects.states).features;

        // ── Base map (clipped to left panel) ─────────────────────────────
        svg.append('g').attr('clip-path', 'url(#arc-map-clip)')
            .selectAll('path')
            .data(features)
            .enter().append('path')
            .attr('d', geoPath)
            .attr('fill', '#163146')
            .attr('stroke', '#2e526e')
            .attr('stroke-width', 0.5);

        svg.append('path')
            .attr('clip-path', 'url(#arc-map-clip)')
            .datum(topojson.mesh(us, us.objects.states, function(a, b) { return a !== b; }))
            .attr('d', geoPath)
            .attr('fill', 'none')
            .attr('stroke', '#0d1e2e')
            .attr('stroke-width', 0.35);

        // ── Divider ───────────────────────────────────────────────────────
        svg.append('line')
            .attr('x1', divX).attr('x2', divX)
            .attr('y1', 16).attr('y2', height - 16)
            .attr('stroke', '#2e526e').attr('stroke-width', 0.6);

        // ── Owner labels (right panel) ────────────────────────────────────
        owners.forEach(function(owner) {
            var oc = colors[owner] || '#BDE2FF';
            var y  = ownerY[owner];
            svg.append('circle')
                .attr('cx', labelX + 5).attr('cy', y).attr('r', 5)
                .attr('fill', oc).attr('stroke', '#0d1e2e').attr('stroke-width', 1);
            svg.append('text')
                .attr('x', labelX + 14).attr('y', y).attr('dy', '0.35em')
                .style('fill', '#BDE2FF')
                .style('font-family', 'Courier New')
                .style('font-size', '11px')
                .text(owner);
        });

        // ── Pre-compute stadium positions ─────────────────────────────────
        var offsets    = { NYG: [-10, -8], NYJ: [10, 8], LA: [-10, 0], LAC: [10, 0] };
        var stadiumPos = {};
        nflTeams.forEach(function(team) {
            var sc  = stadiums[team];
            if (!sc) return;
            var proj = projection([sc.lon, sc.lat]);
            if (!proj) return;
            var off = offsets[team] || [0, 0];
            stadiumPos[team] = [proj[0] + off[0], proj[1] + off[1]];
        });

        // ── Arcs ──────────────────────────────────────────────────────────
        // Sort west→east so animation reveals like a sweep across the country
        var arcsSorted = arcs.slice().sort(function(a, b) {
            var pa = stadiumPos[a.team], pb = stadiumPos[b.team];
            return (pa ? pa[0] : 0) - (pb ? pb[0] : 0);
        });

        arcsSorted.forEach(function(arc, idx) {
            var pos = stadiumPos[arc.team];
            if (!pos) return;
            var oc = colors[arc.owner] || '#BDE2FF';
            var x1 = pos[0], y1 = pos[1];
            var x2 = labelX, y2 = ownerY[arc.owner];
            var dx = x2 - x1;

            // Cubic bezier: exits horizontally from stadium, arrives from left at label
            var d = 'M' + x1 + ',' + y1 +
                    ' C' + (x1 + dx * 0.52) + ',' + y1 +
                    ' ' + (x2 - 48)          + ',' + y2 +
                    ' ' + x2                 + ',' + y2;

            var pathEl = svg.append('path')
                .attr('d', d)
                .attr('fill', 'none')
                .attr('stroke', oc)
                .attr('stroke-width', strokeW(arc.pts))
                .attr('stroke-linecap', 'round')
                .style('cursor', 'pointer')
                .on('mouseover', function(event) {
                    d3.select(this)
                        .raise()
                        .attr('stroke-opacity', 1)
                        .attr('stroke-width', strokeW(arc.pts) + 1.5);
                    tooltip.html(
                        '<b style="color:' + oc + '">' + arc.owner + '</b><br>' +
                        'NFL: <b>' + arc.team + '</b><br>' +
                        'All-time pts: <b>' + arc.pts.toFixed(1) + '</b>'
                    ).style('opacity', 1)
                     .style('left', (event.offsetX + 14) + 'px')
                     .style('top',  (event.offsetY - 12) + 'px');
                })
                .on('mousemove', function(event) {
                    tooltip.style('left', (event.offsetX + 14) + 'px')
                           .style('top',  (event.offsetY - 12) + 'px');
                })
                .on('mouseleave', function() {
                    d3.select(this)
                        .attr('stroke-opacity', baseOpacity)
                        .attr('stroke-width', strokeW(arc.pts));
                    tooltip.style('opacity', 0);
                });

            // Draw-on animation using stroke-dashoffset
            var len = pathEl.node().getTotalLength();
            pathEl
                .attr('stroke-dasharray', len + ' ' + len)
                .attr('stroke-dashoffset', len)
                .attr('stroke-opacity', baseOpacity)
                .transition()
                .duration(600)
                .delay(idx * (mode === 'all' ? 4 : 18))
                .ease(d3.easeLinear)
                .attr('stroke-dashoffset', 0);
        });

        // ── Stadium dots (on top of arcs) ─────────────────────────────────
        nflTeams.forEach(function(team) {
            var pos = stadiumPos[team];
            if (!pos) return;
            var ti     = nflTeams.indexOf(team);
            var row    = matrix[ti] || [];
            var maxOi  = row.reduce(function(best, v, i) { return v > (row[best] || 0) ? i : best; }, 0);
            var dotCol = colors[owners[maxOi]] || '#BDE2FF';

            svg.append('circle')
                .attr('cx', pos[0]).attr('cy', pos[1]).attr('r', 3.5)
                .attr('fill', dotCol)
                .attr('stroke', '#0d1e2e').attr('stroke-width', 1)
                .style('pointer-events', 'none');
        });

        // ── Subtitle ─────────────────────────────────────────────────────
        svg.append('text')
            .attr('x', mapW / 2).attr('y', height - 8)
            .attr('text-anchor', 'middle')
            .style('fill', '#3D5E78')
            .style('font-family', 'Courier New')
            .style('font-size', '10px')
            .text('Arc width = all-time fantasy pts · Dot color = dominant owner · Hover arc for details');

    }).catch(function() {
        svg.append('text').attr('x', width / 2).attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .style('fill', '#BDE2FF').style('font-family', 'Courier New').style('font-size', '14px')
            .text('Map unavailable — check network connection');
    });

    return window.dash_clientside.no_update;
},

/* ── 4H: NFL Franchise → Fantasy Owner Chord Diagram ────────────────────── */
renderChordDiagram: function(data, tabValue) {
    if (tabValue !== 'tab-alltime') return window.dash_clientside.no_update;
    if (!data || !data.nfl_teams || !data.nfl_teams.length) return window.dash_clientside.no_update;
    var container = document.getElementById('d3-chord-container');
    if (!container) {
        var _fn = window.dash_clientside.d3charts.renderChordDiagram.bind(window.dash_clientside.d3charts);
        _waitForEl('d3-chord-container', function() { _fn(data, tabValue); }, 20000);
        return window.dash_clientside.no_update;
    }
    container.innerHTML = '';

    d3.select(container).style('position', 'relative');

    var width  = container.clientWidth  || 760;
    var height = container.clientHeight || 600;
    var outerR = Math.min(width, height) / 2 - 90;
    var innerR = outerR - 24;

    var nflTeams = data.nfl_teams;
    var owners   = data.fantasy_owners;
    var colors   = data.colors;
    var matrix   = data.matrix; // [nfl_team_idx][owner_idx] = pts

    // Build square matrix for d3.chord (size = nfl_teams + owners)
    var n = nflTeams.length + owners.length;
    var sq = Array.from({length: n}, function() { return new Array(n).fill(0); });

    // Fill: nfl_teams are indices 0..nfl-1, owners are indices nfl..n-1
    var nfl = nflTeams.length;
    matrix.forEach(function(row, ti) {
        row.forEach(function(val, oi) {
            sq[ti][nfl + oi] = val;
            sq[nfl + oi][ti] = val;
        });
    });

    // Color scheme
    var nflColor  = '#3D5E78';  // steel blue for all NFL teams
    var ownerColor = function(idx) { return colors[owners[idx]] || '#BDE2FF'; };

    var chord = d3.chord().padAngle(0.04).sortSubgroups(d3.descending)(sq);
    var arc   = d3.arc().innerRadius(innerR).outerRadius(outerR);
    var ribbon = d3.ribbon().radius(innerR);

    var svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height)
        .style('background', 'transparent');

    var g = svg.append('g')
        .attr('transform', 'translate(' + width/2 + ',' + height/2 + ')');

    // Tooltip
    var tooltip = d3.select(container).append('div')
        .style('position', 'absolute').style('pointer-events', 'none')
        .style('background', '#1a3a52').style('border', '1px solid #2e526e')
        .style('border-radius', '6px').style('padding', '8px 12px')
        .style('font-family', 'Courier New').style('font-size', '12px')
        .style('color', '#BDE2FF').style('opacity', 0).style('z-index', 10)
        .style('max-width', '220px');

    // Outer arcs (group segments)
    var group = g.append('g').selectAll('g')
        .data(chord.groups)
        .enter().append('g');

    group.append('path')
        .attr('d', arc)
        .attr('fill', function(d) {
            return d.index < nfl ? nflColor : ownerColor(d.index - nfl);
        })
        .attr('stroke', '#0d1e2e')
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.85)
        .on('mouseover', function(event, d) {
            var name  = d.index < nfl ? nflTeams[d.index] : owners[d.index - nfl];
            var total = d3.sum(sq[d.index]);
            tooltip.html('<b>' + name + '</b><br>Total fantasy pts: <b>' + total.toFixed(1) + '</b>')
                .style('opacity', 1)
                .style('left', (event.offsetX + 12) + 'px')
                .style('top',  (event.offsetY + 12) + 'px');
            // Dim unconnected ribbons
            g.selectAll('.ribbon-path')
                .attr('opacity', function(r) {
                    return r.source.index === d.index || r.target.index === d.index ? 0.8 : 0.05;
                });
        })
        .on('mouseleave', function() {
            tooltip.style('opacity', 0);
            g.selectAll('.ribbon-path').attr('opacity', 0.5);
        });

    // Labels
    group.append('text')
        .each(function(d) { d.angle = (d.startAngle + d.endAngle) / 2; })
        .attr('dy', '0.35em')
        .attr('transform', function(d) {
            return 'rotate(' + (d.angle * 180 / Math.PI - 90) + ')' +
                   'translate(' + (outerR + 8) + ')' +
                   (d.angle > Math.PI ? 'rotate(180)' : '');
        })
        .attr('text-anchor', function(d) { return d.angle > Math.PI ? 'end' : 'start'; })
        .style('fill', function(d) {
            return d.index < nfl ? '#6a9abf' : (colors[owners[d.index - nfl]] || '#BDE2FF');
        })
        .style('font-family', 'Courier New')
        .style('font-size', function(d) { return d.index < nfl ? '9px' : '11px'; })
        .style('font-weight', function(d) { return d.index < nfl ? 'normal' : 'bold'; })
        .text(function(d) { return d.index < nfl ? nflTeams[d.index] : owners[d.index - nfl]; });

    // Ribbons (chords) — animate in from 0 opacity
    g.append('g').attr('fill-opacity', 0.5).selectAll('path')
        .data(chord)
        .enter().append('path')
        .attr('class', 'ribbon-path')
        .attr('d', ribbon)
        .attr('fill', function(d) {
            // Color by owner (the non-nfl side)
            var ownerIdx = d.source.index >= nfl ? d.source.index - nfl : d.target.index - nfl;
            return ownerColor(ownerIdx);
        })
        .attr('stroke', '#0d1e2e')
        .attr('stroke-width', 0.3)
        .attr('opacity', 0)
        .on('mouseover', function(event, d) {
            var nflIdx   = d.source.index < nfl ? d.source.index : d.target.index;
            var ownerIdx = d.source.index >= nfl ? d.source.index - nfl : d.target.index - nfl;
            var pts = matrix[nflIdx] ? (matrix[nflIdx][ownerIdx] || 0) : 0;
            tooltip.html(
                '<b>' + nflTeams[nflIdx] + '</b> → <b style="color:' + ownerColor(ownerIdx) + '">' + owners[ownerIdx] + '</b><br>' +
                'Fantasy pts contributed: <b>' + pts.toFixed(1) + '</b>'
            ).style('opacity', 1)
             .style('left', (event.offsetX + 12) + 'px')
             .style('top',  (event.offsetY + 12) + 'px');
            d3.select(this).attr('opacity', 0.9);
        })
        .on('mouseleave', function() {
            tooltip.style('opacity', 0);
            d3.select(this).attr('opacity', 0.5);
        })
        .transition().duration(1000).delay(function(d, i) { return i * 20; })
        .attr('opacity', 0.5);

    return window.dash_clientside.no_update;
},

}; // end window.dash_clientside.d3charts
