/* Power rankings table — client-side column sort.
   Survives Dash re-renders via MutationObserver. */
(function () {
  var sortState = { col: null, dir: 1 };

  function attachSort() {
    var table = document.getElementById('pr-table');
    if (!table || table._sortAttached) return;
    table._sortAttached = true;

    table.querySelectorAll('th[data-sortcol]').forEach(function (th) {
      th.addEventListener('click', function () {
        var col = parseInt(th.dataset.sortcol, 10);
        if (sortState.col === col) {
          sortState.dir *= -1;
        } else {
          sortState.col = col;
          sortState.dir = 1;
        }
        sortRows(table, col, sortState.dir);
        updateIcons(table, col, sortState.dir);
      });
    });
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
  var observer = new MutationObserver(function () {
    var table = document.getElementById('pr-table');
    if (table && !table._sortAttached) {
      sortState = { col: null, dir: 1 };
      attachSort();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  attachSort();
})();
