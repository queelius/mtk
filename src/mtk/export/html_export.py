"""HTML Single File Application export for mtk.

Generates a self-contained HTML file with an embedded SQLite database
that can be viewed in a browser using sql.js.
"""

from __future__ import annotations

import base64
import sqlite3
from pathlib import Path

from mtk.export.base import ExportResult


class HtmlExporter:
    """Export the mtk database as a self-contained HTML application.

    Unlike other exporters, this reads the raw SQLite database file,
    base64-encodes it, and embeds it into a single HTML page that uses
    sql.js to provide an interactive email client in the browser.
    """

    def __init__(self, output_path: Path, db_path: Path | str) -> None:
        self.output_path = Path(output_path)
        self.db_path = Path(db_path) if not isinstance(db_path, Path) else db_path

    def export_from_db(self) -> ExportResult:
        """Export the database as a self-contained HTML application."""
        # Read the database file and base64-encode it
        db_bytes = self.db_path.read_bytes()
        db_base64 = base64.b64encode(db_bytes).decode("ascii")

        # Count emails in the database
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM emails")
            email_count = cursor.fetchone()[0]
        finally:
            conn.close()

        # Generate the HTML
        html = _build_html(db_base64)

        # Write output
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")

        return ExportResult(
            format="html",
            output_path=str(self.output_path),
            emails_exported=email_count,
        )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>mtk - Mail Archive</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #f5f5f5; color: #222; display: flex; flex-direction: column; height: 100vh;
}
header {
  background: #1a1a2e; color: #e0e0e0; padding: 10px 20px;
  display: flex; align-items: center; gap: 16px; flex-shrink: 0;
}
header h1 { font-size: 18px; font-weight: 600; white-space: nowrap; }
#stats { font-size: 13px; color: #aaa; white-space: nowrap; }
#search-box {
  flex: 1; max-width: 400px; padding: 6px 12px;
  border: 1px solid #444; border-radius: 4px;
  background: #16213e; color: #eee; font-size: 14px; outline: none;
}
#search-box::placeholder { color: #777; }
#search-box:focus { border-color: #5c7cfa; }
.container { display: flex; flex: 1; overflow: hidden; }
#list-pane {
  width: 45%%; min-width: 320px; border-right: 1px solid #ddd;
  overflow-y: auto; background: #fff;
}
#detail-pane {
  flex: 1; overflow-y: auto; padding: 24px; background: #fafafa;
}
table { width: 100%%; border-collapse: collapse; font-size: 13px; }
thead th {
  position: sticky; top: 0; background: #f0f0f0; text-align: left;
  padding: 8px 10px; border-bottom: 2px solid #ddd; font-weight: 600;
  color: #555; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
}
tbody tr { cursor: pointer; border-bottom: 1px solid #eee; }
tbody tr:hover { background: #e8f0fe; }
tbody tr.selected { background: #d2e3fc; }
td { padding: 8px 10px; vertical-align: top; }
td.date { white-space: nowrap; color: #666; width: 130px; }
td.from { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
td.subject { font-weight: 500; }
td.tags { font-size: 11px; color: #888; white-space: nowrap; }
.tag {
  display: inline-block; background: #e0e7ff; color: #3b5bdb; padding: 1px 6px;
  border-radius: 3px; margin-right: 3px; font-size: 11px;
}
#detail-pane .email-header { margin-bottom: 16px; }
#detail-pane .email-header h2 { font-size: 20px; margin-bottom: 8px; color: #1a1a2e; }
#detail-pane .meta { font-size: 13px; color: #666; line-height: 1.6; }
#detail-pane .meta strong { color: #333; }
#detail-pane .body {
  white-space: pre-wrap; font-size: 14px; line-height: 1.7;
  background: #fff; padding: 16px; border-radius: 6px;
  border: 1px solid #e0e0e0; margin-top: 12px;
}
.thread-link {
  color: #5c7cfa; cursor: pointer; text-decoration: underline;
  font-size: 12px;
}
.back-link {
  color: #5c7cfa; cursor: pointer; text-decoration: underline;
  font-size: 13px; margin-bottom: 12px; display: inline-block;
}
#loading {
  display: flex; align-items: center; justify-content: center;
  height: 100vh; font-size: 16px; color: #666;
}
</style>
</head>
<body>
<div id="loading">Loading database...</div>
<header style="display:none" id="app-header">
  <h1>mtk</h1>
  <input type="text" id="search-box" placeholder="Search emails...">
  <div id="stats"></div>
</header>
<div class="container" style="display:none" id="app-body">
  <div id="list-pane"></div>
  <div id="detail-pane"><p style="color:#999;padding:40px;">Select an email to view.</p></div>
</div>

<script>
const DB_BASE64 = "%s";
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/sql-wasm.js"></script>
<script>
(async function() {
  var SQL = await initSqlJs({
    locateFile: function(file) {
      return "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/" + file;
    }
  });
  var raw = Uint8Array.from(atob(DB_BASE64), function(c) { return c.charCodeAt(0); });
  var db = new SQL.Database(raw);

  document.getElementById("loading").style.display = "none";
  document.getElementById("app-header").style.display = "flex";
  document.getElementById("app-body").style.display = "flex";

  // Stats
  var countRow = db.exec("SELECT COUNT(*), MIN(date), MAX(date) FROM emails");
  if (countRow.length) {
    var vals = countRow[0].values[0];
    var total = vals[0], minDate = vals[1], maxDate = vals[2];
    var fmt = function(d) { return d ? d.substring(0, 10) : "?"; };
    document.getElementById("stats").textContent =
      total + " emails (" + fmt(minDate) + " to " + fmt(maxDate) + ")";
  }

  var currentView = "inbox";

  function escapeHtml(s) {
    if (!s) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function renderList(rows, columns) {
    var colIdx = {};
    columns.forEach(function(c, i) { colIdx[c] = i; });
    var html = "<table><thead><tr>"
      + "<th>Date</th><th>From</th><th>Subject</th><th>Tags</th>"
      + "</tr></thead><tbody>";
    rows.forEach(function(r) {
      var id = r[colIdx["id"]];
      var date = r[colIdx["date"]] || "";
      var from = r[colIdx["from_name"]] || r[colIdx["from_addr"]] || "";
      var subject = r[colIdx["subject"]] || "(no subject)";
      var tags = r[colIdx["tags"]] || "";
      html += '<tr data-id="' + id + '">'
        + '<td class="date">' + escapeHtml(date.substring(0, 16).replace("T", " ")) + "</td>"
        + '<td class="from">' + escapeHtml(from) + "</td>"
        + '<td class="subject">' + escapeHtml(subject) + "</td>"
        + '<td class="tags">' + (tags ? tags.split(",").map(function(t) { return '<span class="tag">' + escapeHtml(t.trim()) + "</span>"; }).join("") : "") + "</td>"
        + "</tr>";
    });
    html += "</tbody></table>";
    document.getElementById("list-pane").innerHTML = html;

    document.querySelectorAll("#list-pane tbody tr").forEach(function(tr) {
      tr.addEventListener("click", function() { showEmail(parseInt(tr.dataset.id)); });
    });
  }

  function loadInbox(query) {
    currentView = "inbox";
    var sql;
    if (query) {
      var escaped = query.replace(/'/g, "''");
      sql = "SELECT e.id, e.date, e.from_addr, e.from_name, e.subject, "
        + "GROUP_CONCAT(t.name) as tags "
        + "FROM emails e LEFT JOIN email_tags et ON e.id = et.email_id "
        + "LEFT JOIN tags t ON et.tag_id = t.id "
        + "WHERE e.subject LIKE '%%" + escaped + "%%' "
        + "OR e.body_text LIKE '%%" + escaped + "%%' "
        + "OR e.from_addr LIKE '%%" + escaped + "%%' "
        + "GROUP BY e.id ORDER BY e.date DESC";
    } else {
      sql = "SELECT e.id, e.date, e.from_addr, e.from_name, e.subject, "
        + "GROUP_CONCAT(t.name) as tags "
        + "FROM emails e LEFT JOIN email_tags et ON e.id = et.email_id "
        + "LEFT JOIN tags t ON et.tag_id = t.id "
        + "GROUP BY e.id ORDER BY e.date DESC";
    }
    var result = db.exec(sql);
    if (result.length) {
      renderList(result[0].values, result[0].columns);
    } else {
      document.getElementById("list-pane").innerHTML =
        '<p style="padding:20px;color:#999;">No emails found.</p>';
    }
  }

  function showEmail(id) {
    document.querySelectorAll("#list-pane tbody tr").forEach(function(tr) {
      tr.classList.toggle("selected", parseInt(tr.dataset.id) === id);
    });

    var result = db.exec(
      "SELECT e.*, GROUP_CONCAT(t.name) as tags FROM emails e "
      + "LEFT JOIN email_tags et ON e.id = et.email_id "
      + "LEFT JOIN tags t ON et.tag_id = t.id "
      + "WHERE e.id = " + id + " GROUP BY e.id"
    );
    if (!result.length) return;
    var cols = result[0].columns;
    var row = result[0].values[0];
    var get = function(name) { return row[cols.indexOf(name)]; };

    var html = '<div class="email-header">'
      + "<h2>" + escapeHtml(get("subject")) + "</h2>"
      + '<div class="meta">'
      + "<strong>From:</strong> " + escapeHtml(get("from_name") || "") + " &lt;" + escapeHtml(get("from_addr")) + "&gt;<br>"
      + "<strong>Date:</strong> " + escapeHtml(get("date") || "") + "<br>";

    var tags = get("tags");
    if (tags) {
      html += "<strong>Tags:</strong> " + tags.split(",").map(function(t) { return '<span class="tag">' + escapeHtml(t.trim()) + "</span>"; }).join(" ") + "<br>";
    }

    var threadId = get("thread_id");
    if (threadId) {
      html += '<strong>Thread:</strong> <span class="thread-link" data-thread="'
        + escapeHtml(threadId) + '">' + escapeHtml(threadId) + "</span><br>";
    }

    html += "</div></div>"
      + '<div class="body">' + escapeHtml(get("body_text") || "(no body)") + "</div>";

    document.getElementById("detail-pane").innerHTML = html;

    document.querySelectorAll(".thread-link").forEach(function(el) {
      el.addEventListener("click", function() { showThread(el.dataset.thread); });
    });
  }

  function showThread(threadId) {
    currentView = "thread";
    var escaped = threadId.replace(/'/g, "''");
    var result = db.exec(
      "SELECT e.id, e.date, e.from_addr, e.from_name, e.subject, "
      + "GROUP_CONCAT(t.name) as tags "
      + "FROM emails e LEFT JOIN email_tags et ON e.id = et.email_id "
      + "LEFT JOIN tags t ON et.tag_id = t.id "
      + "WHERE e.thread_id = '" + escaped + "' "
      + "GROUP BY e.id ORDER BY e.date ASC"
    );

    document.getElementById("detail-pane").innerHTML =
      '<span class="back-link" id="back-to-inbox">Back to inbox</span>';
    document.getElementById("back-to-inbox").addEventListener("click", function() {
      loadInbox(document.getElementById("search-box").value.trim());
      document.getElementById("detail-pane").innerHTML =
        '<p style="color:#999;padding:40px;">Select an email to view.</p>';
    });

    if (result.length) {
      renderList(result[0].values, result[0].columns);
    }
  }

  // Search
  var searchTimeout;
  document.getElementById("search-box").addEventListener("input", function() {
    clearTimeout(searchTimeout);
    var q = this.value.trim();
    searchTimeout = setTimeout(function() { loadInbox(q); }, 200);
  });

  // Initial load
  loadInbox("");
})();
</script>
</body>
</html>"""


def _build_html(db_base64: str) -> str:
    """Build the complete HTML page with embedded database."""
    return _HTML_TEMPLATE % db_base64
