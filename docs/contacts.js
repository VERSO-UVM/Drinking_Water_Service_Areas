/* Town clerk directory — filters docs/data/town_clerks.json. */

'use strict';

var rows = [];
var tbody = document.getElementById('clerk-body');
var searchEl = document.getElementById('clerk-search');
var countyEl = document.getElementById('county-filter');
var emailOnlyEl = document.getElementById('email-only');
var countEl = document.getElementById('result-count');

fetch('data/town_clerks.json')
  .then(function (r) {
    if (!r.ok) throw new Error('town_clerks.json: ' + r.status);
    return r.json();
  })
  .then(function (data) {
    rows = (data.municipalities || []).slice();
    rows.sort(function (a, b) {
      return String(a.town).localeCompare(String(b.town));
    });

    populateCounties();
    stampSource();
    render();
  })
  .catch(function (err) {
    console.error(err);
    tbody.innerHTML =
      '<tr><td colspan="5" class="empty">Could not load clerk contacts. ' +
      'Run <code>script/build_site_data.py</code> to generate ' +
      '<code>docs/data/town_clerks.json</code>.</td></tr>';
    document.getElementById('source-stamp').textContent = '';
  });

function populateCounties() {
  var counties = {};
  rows.forEach(function (r) { if (r.county) counties[r.county] = true; });
  Object.keys(counties).sort().forEach(function (c) {
    var opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c + ' County';
    countyEl.appendChild(opt);
  });
}

function stampSource() {
  // Every filled row carries the same source label, e.g.
  // "VT SoS clerk file (June 12, 2026)". Show it once.
  var withSource = rows.filter(function (r) { return r.source; });
  var el = document.getElementById('source-stamp');
  el.textContent = withSource.length
    ? 'Source: ' + withSource[0].source
    : 'Contacts not yet populated — run script/merge_clerk_contacts.py';

  var withEmail = rows.filter(function (r) { return r.clerk_email; }).length;
  document.getElementById('coverage-note').textContent =
    withEmail + ' of ' + rows.length + ' municipalities have a clerk contact on file. ' +
    'The remainder are villages, gores, and unincorporated places with no separate town clerk.';
}

[searchEl, countyEl, emailOnlyEl].forEach(function (el) {
  el.addEventListener('input', render);
  el.addEventListener('change', render);
});

function render() {
  var q = searchEl.value.trim().toLowerCase();
  var county = countyEl.value;
  var emailOnly = emailOnlyEl.checked;

  var shown = rows.filter(function (r) {
    if (county && r.county !== county) return false;
    if (emailOnly && !r.clerk_email) return false;
    if (!q) return true;
    return [r.town, r.county, r.clerk_name, r.clerk_email]
      .some(function (v) { return v && String(v).toLowerCase().indexOf(q) > -1; });
  });

  countEl.textContent = shown.length + (shown.length === 1 ? ' municipality' : ' municipalities');

  if (!shown.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">No match.</td></tr>';
    return;
  }

  tbody.innerHTML = shown.map(rowHtml).join('');
}

function rowHtml(r) {
  var type = r.municipality_type && r.municipality_type !== 'Town'
    ? ' <span class="pill">' + esc(r.municipality_type) + '</span>'
    : '';

  var townCell = esc(r.town) + type;
  if (r.town_website) {
    townCell = '<a href="' + esc(r.town_website) + '" target="_blank" rel="noopener">' +
               esc(r.town) + '</a>' + type;
  }

  var contact = [];
  if (r.clerk_email) {
    contact.push('<a href="mailto:' + esc(r.clerk_email) + '">' + esc(r.clerk_email) + '</a>');
  }
  if (r.clerk_phone) {
    contact.push('<span class="dim">' + esc(r.clerk_phone) + '</span>');
  }

  var missing = '<span class="dim">' + esc(r.notes || 'no clerk on file') + '</span>';

  return '<tr>' +
    '<th scope="row">' + townCell + '</th>' +
    '<td>' + esc(r.county || '') + '</td>' +
    '<td>' + (r.clerk_name ? esc(r.clerk_name) : '<span class="dim">&mdash;</span>') + '</td>' +
    '<td>' + (contact.length ? contact.join('<br>') : missing) + '</td>' +
    '<td class="addr">' + esc(r.clerk_mailing_address || '') + '</td>' +
    '</tr>';
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
