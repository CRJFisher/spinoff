"""HTML/CSS/JS template for the overview dashboard.

Uses string.Template with $-style placeholders to avoid conflicts
with CSS {} and JS {} braces.
"""

from string import Template

TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="$refresh_interval">
<title>$project_name - Spinoff Overview</title>
<style>
:root {
    --bg: #1a1a2e;
    --bg-surface: #22223a;
    --text: #e0e0e0;
    --text-muted: #888;
    --border: #333;
    --state-working: #4a9eff;
    --state-waiting: #f0a030;
    --state-errored: #e05050;
    --state-done: #50c878;
    --state-idle: #888;
    --state-init: #7ab8ff;
    --btn-bg: #333;
    --btn-hover: #444;
}
*, *::before, *::after { box-sizing: border-box; }
body {
    margin: 0; padding: 12px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    background: var(--bg); color: var(--text);
}
header {
    display: flex; align-items: center; gap: 16px;
    padding: 8px 0; border-bottom: 1px solid var(--border);
    margin-bottom: 12px; flex-wrap: wrap;
}
h1 { margin: 0; font-size: 16px; font-weight: 600; }
.stats { display: flex; gap: 12px; }
.stat { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.stat.working { background: rgba(74,158,255,0.2); color: var(--state-working); }
.stat.waiting { background: rgba(240,160,48,0.2); color: var(--state-waiting); }
.stat.errored { background: rgba(224,80,80,0.2); color: var(--state-errored); }
.stat.done { background: rgba(80,200,120,0.2); color: var(--state-done); }
.timestamp { color: var(--text-muted); font-size: 11px; margin-left: auto; }
table {
    width: 100%; border-collapse: collapse;
    table-layout: fixed;
}
th {
    text-align: left; padding: 6px 10px;
    border-bottom: 2px solid var(--border);
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted);
}
td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
tr:hover { background: rgba(255,255,255,0.03); }
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 3px;
    font-size: 11px; font-weight: 600;
}
.badge-working { background: rgba(74,158,255,0.2); color: var(--state-working); }
.badge-waiting_approval {
    background: rgba(240,160,48,0.2); color: var(--state-waiting);
    animation: pulse 2s ease-in-out infinite;
}
.badge-errored { background: rgba(224,80,80,0.2); color: var(--state-errored); }
.badge-done { background: rgba(80,200,120,0.2); color: var(--state-done); }
.badge-initializing { background: rgba(122,184,255,0.2); color: var(--state-init); }
.badge-shell, .badge-waiting_input, .badge-unknown {
    background: rgba(136,136,136,0.2); color: var(--state-idle);
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
@media (prefers-reduced-motion: reduce) {
    .badge-waiting_approval { animation: none; }
}
.snippet {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 12px; color: var(--text-muted);
    max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.actions { white-space: nowrap; }
.btn {
    background: var(--btn-bg); color: var(--text); border: none;
    padding: 3px 8px; border-radius: 3px; cursor: pointer;
    font-size: 11px; margin-right: 4px;
}
.btn:hover { background: var(--btn-hover); }
.btn:focus-visible { outline: 2px solid var(--state-working); outline-offset: 1px; }
.btn-approve { background: #2d7a3a; }
.btn-approve:hover { background: #358a42; }
.btn-kill { background: #6b2020; }
.btn-kill:hover { background: #7b2828; }
.btn-approve-all { background: #2d7a3a; color: white; }
.empty { color: var(--text-muted); padding: 24px; text-align: center; }
.overlaps {
    margin-top: 16px; padding: 12px;
    background: rgba(240,160,48,0.1); border: 1px solid rgba(240,160,48,0.3);
    border-radius: 6px;
}
.overlaps h2 { font-size: 13px; margin: 0 0 8px; color: var(--state-waiting); }
.overlap-file { font-family: monospace; font-size: 12px; }
.overlap-agents { color: var(--text-muted); font-size: 11px; }
</style>
</head>
<body>
<header>
    <h1>$project_name</h1>
    <div class="stats">
        <span class="stat">${total_count} agents</span>
        $stats_badges
    </div>
    $approve_all_btn
    <div class="timestamp">Updated: $generated_at</div>
</header>
<main>
$table_content
</main>
$overlaps_section
<script>
var ACTIONS_PATH = $actions_file_path;
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.dataset.action;
    var sid = btn.dataset.sid || '';
    if (action === 'kill') {
        var name = btn.dataset.name || sid;
        if (!confirm('Kill agent "' + name + '"?')) return;
    }
    writeAction(action, sid);
    var row = btn.closest('tr');
    if (row) { row.style.opacity = '0.6'; setTimeout(function() { row.style.opacity = '1'; }, 1000); }
});
document.addEventListener('click', function(e) {
    if (e.target.closest('.btn-approve-all')) {
        if (confirm('Approve all waiting agents? Dangerous prompts will be skipped.'))
            writeAction('approve_all', '');
    }
});
function writeAction(action, surfaceId) {
    var payload = JSON.stringify({action: action, surface_id: surfaceId, timestamp: Date.now()/1000});
    if (typeof window.__cmux_write !== 'undefined') {
        window.__cmux_write(ACTIONS_PATH, payload); return;
    }
    try {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/action', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(payload);
    } catch(e) {}
}
</script>
</body>
</html>
""")
