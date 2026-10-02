/* District tracker — the working list of every district and where its
 * political boundary stands. Reads docs/data/districts.json (built by
 * script/build_site_data.py) and the field list parsed from the data standard.
 */

'use strict';

var districts = [];
var fields = [];
var ladder = [];

var tbody = document.getElementById('tracker-rows');
var searchEl = document.getElementById('tracker-search');
var statusEl = document.getElementById('status-filter');
var countEl = document.getElementById('result-count');

// How a district's political boundary can be obtained, best lead first.
// Keys match `boundary_path` in data/vt_district_status.csv.
var PATHS = {
  partner_file: 'Partner GIS file',
  whole_town: 'Whole town',
  named_features: 'Named roads / features',
  metes_and_bounds: 'Written description',
  district_map: 'District map',
  plat_reference: 'Plat in land records',
  none_found: 'None found'
};
var PATH_ORDER = Object.keys(PATHS);

Promise.all([
  fetch('data/districts.json').then(okJson),
  fetch('data/standard_fields.json').then(okJson)
])
  .then(function (res) {
    districts = res[0].districts || [];
    fields = res[1].fields || [];
    ladder = res[1].ladder || [];
    populateStatuses();
    renderStatusBar();
    stamp();
    render();
    openFromHash();
  })
  .catch(function (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="7" class="loading">District list unavailable. ' +
      'Run <code>script/build_site_data.py</code>.</td></tr>';
  });

function okJson(r) {
  if (!r.ok) throw new Error(r.url + ': ' + r.status);
  return r.json();
}

function tr(d) { return d.tracker || {}; }

/* ---------- header and controls ---------- */

function stamp() {
  var dates = districts.map(function (d) { return tr(d).checked_on; })
    .filter(Boolean).sort();
  document.getElementById('tracker-stamp').textContent =
    districts.length + ' districts in ' + townCount(districts) + ' towns' +
    (dates.length ? ' · sources last checked ' + dates[dates.length - 1] : '');
}

function populateStatuses() {
  ladder.forEach(function (s) {
    var opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    statusEl.appendChild(opt);
  });
}

function renderStatusBar() {
  var bar = document.getElementById('status-bar');
  bar.innerHTML = ladder.map(function (s, i) {
    var n = districts.filter(function (d) { return tr(d).status === s; }).length;
    return '<div><dt><span class="status-pill st-' + i + '">' + esc(s) + '</span></dt>' +
           '<dd><button type="button" class="status-count" data-status="' + esc(s) +
           '" title="Show only this status">' + n + '</button></dd></div>';
  }).join('');
  bar.addEventListener('click', function (ev) {
    var b = ev.target.closest('.status-count');
    if (!b) return;
    var s = b.getAttribute('data-status');
    statusEl.value = statusEl.value === s ? '' : s;
    render();
  });
}

searchEl.addEventListener('input', render);
statusEl.addEventListener('change', render);

/* ---------- table ---------- */

// Default: least progress first, so the work still to do is on top.
var sortKey = 'status';
var sortAsc = true;

document.querySelectorAll('.sort-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var key = btn.getAttribute('data-sort');
    if (key === sortKey) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
    render();
  });
});

function sortValue(d) {
  if (sortKey === 'status') return tr(d).status_rank;
  if (sortKey === 'path') {
    var i = PATH_ORDER.indexOf(tr(d).boundary_path);
    return i < 0 ? PATH_ORDER.length : i;
  }
  return String(d[sortKey] || '').toLowerCase();
}

function render() {
  var q = searchEl.value.trim().toLowerCase();
  var st = statusEl.value;

  var rows = districts.filter(function (d) {
    if (st && tr(d).status !== st) return false;
    if (!q) return true;
    return (d.name + ' ' + d.town + ' ' + (d.pwsid || '')).toLowerCase().indexOf(q) > -1;
  });

  rows.sort(function (a, b) {
    var x = sortValue(a), y = sortValue(b);
    if (x < y) return sortAsc ? -1 : 1;
    if (x > y) return sortAsc ? 1 : -1;
    // Ties fall back to town, then district, so the order is stable.
    return a.town.localeCompare(b.town) || a.name.localeCompare(b.name);
  });

  document.querySelectorAll('.sort-btn').forEach(function (btn) {
    var on = btn.getAttribute('data-sort') === sortKey;
    btn.classList.toggle('sorted', on);
    btn.setAttribute('aria-sort', on ? (sortAsc ? 'ascending' : 'descending') : 'none');
  });

  countEl.textContent = rows.length === districts.length
    ? districts.length + ' districts'
    : rows.length + ' of ' + districts.length + ' districts';

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">No districts match.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(function (d) {
    var t = tr(d);
    return '<tr>' +
      '<td>' + esc(d.town) + '</td>' +
      '<td class="td-name">' + esc(d.name) + tagsHtml(d) + '</td>' +
      '<td>' + statusPill(t) + '</td>' +
      '<td class="td-path">' + esc(PATHS[t.boundary_path] || '—') + '</td>' +
      '<td class="td-summary">' + (t.summary
        ? '<span class="clamp" title="' + esc(t.summary) + '">' + esc(t.summary) + '</span>'
        : '<span class="dd-meta">Nothing recorded yet.</span>') + '</td>' +
      '<td class="td-links">' + quickLinks(d) + '</td>' +
      '<td class="num"><button type="button" class="details-btn" data-name="' +
      esc(d.name) + '">More</button></td>' +
      '</tr>';
  }).join('');
}

function statusPill(t) {
  return '<span class="status-pill st-' + (t.status_rank || 0) + '">' +
         esc(t.status || 'Not started') + '</span>';
}

function tagsHtml(d) {
  var tags = '';
  if (d.pilot) tags += ' <span class="tag tag-pilot">pilot</span>';
  if (d.unconfirmed) tags += ' <span class="tag tag-extra">VRWA unsure</span>';
  else if (!d.in_roster) tags += ' <span class="tag tag-extra">not in VRWA list</span>';
  return tags;
}

// The few links most worth a click, inline. Everything else is under More.
function quickLinks(d) {
  var x = d.details || {};
  var out = [];
  if (d.fd_id) {
    out.push('<a href="index.html#fd=' + encodeURIComponent(d.fd_id) + '">On the map</a>');
  }
  if (d.website) out.push(extLink(d.website, 'Website'));
  if (x.charter) out.push(extLink(x.charter.url, 'Charter ch. ' + x.charter.chapter));
  if (x.epa && x.epa.echo) out.push(extLink(x.epa.echo, 'EPA'));
  var broken = (tr(d).links || []).filter(isBroken).length;
  if (broken) {
    out.push('<span class="link-broken">' + broken + ' broken</span>');
  }
  return out.length ? out.join('<br>') : '<span class="dd-meta">—</span>';
}

function isBroken(l) {
  return /^(broken|blocked)/.test(l.status || '');
}

tbody.addEventListener('click', function (ev) {
  var b = ev.target.closest('.details-btn');
  if (b) openDetails(b.getAttribute('data-name'));
});

/* ---------- More dialog ---------- */

/* Every section renders even when it is empty, showing "In progress" instead
 * of disappearing. A missing charter or permit is a research gap worth seeing,
 * not an absence of anything to find.
 */

var dialog = document.getElementById('district-dialog');
var dialogBody = document.getElementById('dd-body');

function openDetails(name) {
  var d = null;
  districts.forEach(function (x) { if (x.name === name) d = x; });
  if (!d) return;

  dialogBody.innerHTML = detailsHtml(d);
  history.replaceState(null, '', '#' + encodeURIComponent(d.name));
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');       // very old browsers
}

// A district name in the hash opens its More view, so a row can be linked to.
function openFromHash() {
  var h = decodeURIComponent(location.hash.slice(1));
  if (h) openDetails(h);
}

dialog.addEventListener('close', function () {
  history.replaceState(null, '', location.pathname);
});

// Backdrop click closes; clicks inside the panel must not.
dialog.addEventListener('click', function (ev) {
  if (ev.target === dialog) dialog.close();
});

function pending(label) {
  return '<p class="dd-pending">In progress &mdash; ' + esc(label) + '</p>';
}

function detailsHtml(d) {
  var x = d.details || {};
  var t = tr(d);
  var h = '';

  h += '<h2 id="dd-title">' + esc(d.name) + tagsHtml(d) + '</h2>';
  h += '<p class="dd-sub">' + esc(d.town) + (d.pwsid ? ' &middot; ' + esc(d.pwsid) : '') + '</p>';

  /* --- where it stands --- */
  h += '<h3>Where it stands</h3>';
  h += ddTable([
    ['Status', statusPill(t)],
    ['Boundary source', esc(PATHS[t.boundary_path] || 'Not yet assessed')]
  ]);
  h += t.summary ? '<p>' + esc(t.summary) + '</p>' : pending('no summary yet');
  if (t.open_questions && t.open_questions.length) {
    h += '<h4>Open questions</h4><ul class="dd-notes">' +
         t.open_questions.map(function (q) { return '<li>' + esc(q) + '</li>'; }).join('') +
         '</ul>';
  }
  if (t.checked_on) h += '<p class="dd-meta">Sources last checked ' + esc(t.checked_on) + '.</p>';
  if (d.fd_id) {
    h += '<p><a href="index.html#fd=' + encodeURIComponent(d.fd_id) +
         '">Show this boundary on the map &rarr;</a></p>';
  }

  /* --- every field in the data standard --- */
  h += '<h3>Data standard fields</h3>';
  h += '<p class="dd-meta">Sections 3&ndash;6 of the <a href="standard.html">data ' +
       'standard</a>, filled with what we hold. <em>Not yet known</em> is a gap ' +
       'still to fill; <em>Unknown</em> means someone looked and the answer ' +
       'isn\'t known.</p>';
  h += fieldsHtml(d);

  /* --- links checked --- */
  h += '<h3>Links checked</h3>';
  var links = t.links || [];
  if (links.length) {
    h += '<table class="dd-table dd-links-table"><tbody>';
    links.forEach(function (l) {
      h += '<tr><th>' + extLink(l.url, l.label || l.url) + '</th><td>' +
           '<span class="link-status ' + (isBroken(l) ? 'bad' : 'ok') + '">' +
           esc(l.status || 'unchecked') + '</span> ' + esc(l.finding || '') +
           '</td></tr>';
    });
    h += '</tbody></table>';
  } else {
    h += pending('no links checked yet');
  }

  h += legacySections(d, x);
  return h;
}

function fieldsHtml(d) {
  var std = d.standard || {};
  var h = '';
  var section = '';
  fields.forEach(function (f) {
    if (f.section !== section) {
      if (section) h += '</tbody></table>';
      section = f.section;
      h += '<h4>&sect;' + esc(f.section) + ' ' + esc(f.section_title) + '</h4>' +
           '<table class="dd-table std-table"><tbody>';
    }
    var cell = std[f.field];
    var val;
    if (!cell || cell.v === '') {
      val = '<span class="std-gap">Not yet known</span>';
    } else if (/^unknown$/i.test(cell.v)) {
      val = '<span class="std-unknown">Unknown</span>';
    } else {
      val = /^https?:\/\//.test(cell.v) ? extLink(cell.v, cell.v) : esc(cell.v);
    }
    // pwsid is "Required for service areas; Recommended for districts".
    var m = /(\w+) for districts/.exec(f.level);
    var level = m ? m[1] : String(f.level).split(' ')[0];
    h += '<tr><th title="' + esc(f.description) + '"><code>' + esc(f.field) + '</code>' +
         '<span class="std-level lvl-' + esc(level.toLowerCase()) + '">' + esc(level) +
         '</span></th><td>' + val +
         (cell && cell.v !== '' ? ' <span class="std-src">' + esc(cell.src) + '</span>' : '') +
         '</td></tr>';
  });
  if (section) h += '</tbody></table>';
  return h;
}

// The sections the Map page's old Details dialog showed: charters, EPA and
// permit connections, ordinances, the mapped boundary, and research notes.
function legacySections(d, x) {
  var h = '';

  /* --- websites and charters --- */
  h += '<h3>Websites &amp; charters</h3>';
  var links = [];
  if (d.website) {
    links.push('<li>' + extLink(d.website, 'District website') + '</li>');
  }
  if (x.charter) {
    links.push('<li>' + extLink(x.charter.url, 'Charter: ' + x.charter.title) + ' ' +
               '<span class="dd-meta">24 V.S.A. App. ch. ' + esc(x.charter.chapter) +
               '</span></li>');
  }
  if (x.town_charter) {
    links.push('<li>' + extLink(x.town_charter.url, x.town_charter.title) + ' ' +
               '<span class="dd-meta">town charter, context only</span></li>');
  }
  h += links.length ? '<ul class="dd-links">' + links.join('') + '</ul>'
                    : pending('no website or charter found yet');

  if (x.charter && x.charter.sections && x.charter.sections.length) {
    h += '<h4>Charter sections describing boundaries or powers</h4>';
    x.charter.sections.forEach(function (sec) {
      h += '<details class="dd-section"><summary>&sect; ' + esc(sec.number) + ' &mdash; ' +
           esc(sec.heading) + '</summary>' +
           '<p class="dd-meta">Matched because: ' + esc(sec.why) + ' &middot; ' +
           extLink(sec.url, 'read on legislature.vermont.gov') + '</p>' +
           '<blockquote>' + esc(sec.excerpt) +
           (sec.truncated ? '…' : '') + '</blockquote></details>';
    });
  }

  /* --- EPA and permits --- */
  h += '<h3>EPA &amp; permit connections</h3>';
  var rows = [];
  if (x.epa && x.epa.pwsid) {
    rows.push(['PWSID', esc(x.epa.pwsid)]);
    rows.push(['Drinking water', extLink(x.epa.echo, 'ECHO facility report') +
               ' &middot; ' + extLink(x.epa.sdwis, 'SDWIS record')]);
  }
  var w = x.ww || {};
  if (w.permit) rows.push(['Wastewater permit', esc(w.permit)]);
  if (w.npdes) rows.push(['NPDES', esc(w.npdes)]);
  if (w.permit_type) rows.push(['Discharge', esc(w.permit_type)]);
  if (w.treatment) rows.push(['Treatment', esc(w.treatment)]);
  if (w.capacity_mgd) rows.push(['Capacity', esc(w.capacity_mgd) + ' MGD']);
  h += rows.length ? ddTable(rows) : pending('no PWSID or permit on file');

  /* --- ordinances and policy --- */
  h += '<h3>Ordinances &amp; policy</h3>';
  var docs = (x.documents || []).slice();

  // Governance documents first, routine meeting records last: a reader looking
  // for the ordinance should not have to scroll past 260 sets of minutes.
  var RANK = {
    ordinance: 0, bylaws: 1, charter: 2, policy: 3, rates: 4, plan: 5,
    annual_report: 6, budget: 7, audit: 8, permit: 9, ccr: 10,
    warning: 11, agenda: 12, packet: 13, minutes: 14, other: 15
  };
  docs.sort(function (a, b) {
    var ra = RANK[a.type] === undefined ? 15 : RANK[a.type];
    var rb = RANK[b.type] === undefined ? 15 : RANK[b.type];
    if (ra !== rb) return ra - rb;
    // Newest first within a type.
    return String(b.adopted || '').localeCompare(String(a.adopted || '')) ||
           String(a.title).localeCompare(String(b.title));
  });

  var DOC_LIMIT = 12;
  var shown = docs.slice(0, DOC_LIMIT);
  var hidden = docs.length - shown.length;

  if (docs.length) {
    h += '<p class="dd-meta">' + docs.length + ' document' +
         (docs.length === 1 ? '' : 's') + ' on file.</p>';
    h += '<ul class="dd-docs">';
    shown.forEach(function (doc) {
      var bits = [];
      if (doc.type) bits.push(esc(doc.type.replace(/_/g, ' ')));
      if (doc.adopted) bits.push(esc(doc.adopted));
      if (doc.pages) bits.push(doc.pages + ' pp');
      // Say so plainly when a PDF is a scan we could not read.
      if (doc.needs_ocr) bits.push('scanned, text not extracted');
      h += '<li>' + extLink(doc.url, doc.title) + ' <span class="dd-meta">' +
           bits.join(' &middot; ') + '</span>';
      if (doc.refs && doc.refs.length) {
        h += '<br><span class="dd-meta">Cites ' + doc.refs.map(esc).join('; ') + '</span>';
      }
      h += '</li>';
    });
    h += '</ul>';

    if (hidden > 0) {
      var src = '';
      docs.forEach(function (dc) { if (!src && dc.source_page) src = dc.source_page; });
      h += '<p class="dd-meta">' + hidden + ' more not listed here' +
           (src ? ' &mdash; ' + extLink(src, 'browse the source') : '') + '.</p>';
    }
  } else {
    h += pending('no ordinances or policies collected yet');
  }

  /* --- boundary --- */
  h += '<h3>Boundary</h3>';
  var b = x.boundary || {};
  var brows = [];
  if (b.extent) brows.push(['Extent', esc(b.extent)]);
  if (b.method) brows.push(['Drawn', esc(methodText(b))]);
  if (b.derivation) brows.push(['How it was derived', esc(b.derivation)]);
  if (b.citation) {
    var cite = legalText(b.legal_authority_type, b.citation);
    brows.push(['Legal authority', b.url ? extLink(b.url, cite) : esc(cite)]);
  }
  if (b.verification_status) brows.push(['Verification', esc(verificationText(b))]);
  if (b.submitted_by) {
    brows.push(['Submitted by', esc(b.submitted_by) +
                (b.submission_date ? ' on ' + esc(b.submission_date) : '')]);
  }
  h += brows.length ? ddTable(brows) : pending('no boundary mapped yet');
  if (b.text) h += '<blockquote>' + esc(b.text) + '</blockquote>';

  /* --- notes --- */
  h += '<h3>Notes</h3>';
  if (x.notes && x.notes.length) {
    h += '<ul class="dd-notes">';
    x.notes.forEach(function (n) { h += '<li>' + esc(n) + '</li>'; });
    h += '</ul>';
  } else {
    h += pending('nothing recorded yet');
  }
  if (x.checked_on) {
    h += '<p class="dd-meta">Website search last run ' + esc(x.checked_on) + '.</p>';
  }
  return h;
}

/* ---------- helpers ---------- */

// The boundary layer follows docs/METADATA_STANDARD.md, where "Unknown" is a
// value in its own right (not a blank), so these say so in words.
function methodText(p) {
  if (!p.method || (p.method === 'Unknown' && p.method_basis === 'Unknown')) {
    return 'Method not recorded';
  }
  return p.method + (p.method_basis && p.method_basis !== 'Unknown'
    ? ' (' + p.method_basis + ')' : '');
}

function verificationText(p) {
  if (!p.verification_status) return null;
  return p.verification_status +
    (p.verifier_name ? ' (' + p.verifier_name + ')' : '') +
    (p.verification_date ? ', ' + p.verification_date : '');
}

function legalText(type, citation) {
  if (!citation || citation === 'unknown') {
    return 'Not yet identified — no charter, vote or recorded plat on file';
  }
  return (type && type !== 'Unknown' ? type + ': ' : '') + citation;
}

function ddTable(rows) {
  var h = '<table class="dd-table">';
  rows.forEach(function (r) {
    h += '<tr><th>' + r[0] + '</th><td>' + r[1] + '</td></tr>';
  });
  return h + '</table>';
}

function extLink(url, label) {
  return '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(label) + '</a>';
}

function townCount(list) {
  var seen = {};
  list.forEach(function (d) { seen[d.town] = true; });
  return Object.keys(seen).length;
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
