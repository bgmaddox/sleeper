/* Temporary diagnostic — catches JS errors and sends them to /debug-error */
window.onerror = function(msg, src, line, col, err) {
    var info = JSON.stringify({msg: msg, src: src, line: line, col: col, stack: err ? err.stack : ''});
    fetch('/debug-error', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: info,
        credentials: 'include',
    }).catch(function(){});
    return false;
};
window.addEventListener('unhandledrejection', function(e) {
    var info = JSON.stringify({msg: 'UnhandledRejection', reason: String(e.reason)});
    fetch('/debug-error', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: info,
        credentials: 'include',
    }).catch(function(){});
});
