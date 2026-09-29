/* Client-side column sort for the Power Rankings table and any table marked
   data-sortable. Survives Dash re-renders via MutationObserver. */
(function () {
  var SELECTOR = '#pr-table, table[data-sortable]';

  function attachSort(table) {
    if (table._sortAttached) return;
    table._sortAttached = true;
    var state = { col: null, dir: 1 };

    table.querySelectorAll('th[data-sortcol]').forEach(function (th) {
      th.addEventListener('click', function () {
        var col = parseInt(th.dataset.sortcol, 10);
        if (state.col === col) {
          state.dir *= -1;
        } else {
          state.col = col;
          state.dir = 1;
        }
        sortRows(table, col, state.dir);
        updateIcons(table, col, state.dir);
      });
    });
  }

  function attachAll() {
    document.querySelectorAll(SELECTOR).forEach(attachSort);
  }

  function sortRows(table, colIdx, dir) {
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort(function (a, b) {
      var aTd = a.querySelectorAll('td')[colIdx];
      var bTd = b.querySelectorAll('td')[colIdx];
      if (!aTd || !bTd) return 0;

      var isStr = aTd.dataset.sortType === 'str';
      if (isStr) {
        var aStr = (aTd.dataset.val || aTd.textContent || '').trim().toLowerCase();
        var bStr = (bTd.dataset.val || bTd.textContent || '').trim().toLowerCase();
        return aStr < bStr ? -dir : aStr > bStr ? dir : 0;
      }

      var aVal = parseFloat(aTd.dataset.val);
      var bVal = parseFloat(bTd.dataset.val);
      if (isNaN(aVal)) aVal = 0;
      if (isNaN(bVal)) bVal = 0;
      return (aVal - bVal) * dir;
    });

    rows.forEach(function (r) { tbody.appendChild(r); });
  }

  function updateIcons(table, activeCol, dir) {
    table.querySelectorAll('th[data-sortcol]').forEach(function (th) {
      th.classList.remove('pr-th-sorted-asc', 'pr-th-sorted-desc');
      if (parseInt(th.dataset.sortcol, 10) === activeCol) {
        th.classList.add(dir === 1 ? 'pr-th-sorted-asc' : 'pr-th-sorted-desc');
      }
    });
  }

  /* Re-attach after each Dash render that swaps the DOM */
  var observer = new MutationObserver(attachAll);
  observer.observe(document.body, { childList: true, subtree: true });

  attachAll();
})();
