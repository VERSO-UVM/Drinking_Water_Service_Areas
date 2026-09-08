/* Vermont drinking water service areas — map viewer.
 *
 * Layers are declared in the LAYERS registry below. Adding another political
 * boundary layer (fire districts, villages, counties) is one entry here plus a
 * checkbox in index.html with a matching `id`.
 */

'use strict';

var VT_BOUNDS = L.latLngBounds([42.72, -73.44], [45.02, -71.46]);

var COLORS = {
  auth: '#2563eb',
  modeled: '#d97706',
  town: '#475569',
  fd: '#9333ea',           // fire district, confirmed boundary
  fdApprox: '#0d9488',     // extent derived from a statute description
  fdUnconfirmed: '#a1a1aa' // equals its town, not yet confirmed as town-wide
};

/* ---------- basemaps ---------- */

var basemaps = {
  // Standard OpenStreetMap tiles. Busier than a muted basemap, so the overlay
  // fill opacities below stay low to keep street names readable underneath.
  light: L.tileLayer(
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">' +
        'OpenStreetMap</a> contributors'
    }
  ),
  imagery: L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Imagery &copy; Esri' }
  )
};

var map = L.map('map', {
  layers: [basemaps.light],
  zoomControl: true,
  scrollWheelZoom: true
}).fitBounds(VT_BOUNDS);

L.control.scale({ imperial: true, metric: false }).addTo(map);

// Panes fix the draw order regardless of the sequence layers finish loading in.
// Fire districts sit between towns and water: they contain the service areas,
// so the service areas have to stay readable on top of them.
map.createPane('parcels').style.zIndex = 350;
map.createPane('towns').style.zIndex = 400;
map.createPane('fire').style.zIndex = 425;
map.createPane('water').style.zIndex = 450;
map.createPane('sewer').style.zIndex = 460;

/* ---------- ANR live map services ---------- */

/* Vermont ANR publishes these as ArcGIS map services, not as files we can
 * ship. Rendering them server-side into 256px tiles keeps the payload at zero
 * regardless of feature count -- the service line inventory alone is 144,195
 * parcel polygons, which could never be embedded as GeoJSON.
 *
 * The trade-off is that these are images: no popups, no search, no filtering.
 * They are context layers, and both default to off.
 */

var WEB_MERCATOR_ORIGIN = 20037508.342789244;

var ArcGISDynamicLayer = L.TileLayer.extend({
  getTileUrl: function (coords) {
    var size = 256;
    var res = (WEB_MERCATOR_ORIGIN * 2) / (size * Math.pow(2, coords.z));
    var minx = -WEB_MERCATOR_ORIGIN + coords.x * size * res;
    var maxy = WEB_MERCATOR_ORIGIN - coords.y * size * res;
    var bbox = [minx, maxy - size * res, minx + size * res, maxy].join(',');

    return this.options.service + '/export' +
      '?bbox=' + bbox +
      '&bboxSR=3857&imageSR=3857' +
      '&size=' + size + ',' + size +
      '&layers=show:' + this.options.layerId +
      '&format=png32&transparent=true&f=image';
  }
});

var ANR_DWGWP = 'https://anrmaps.vermont.gov/arcgis/rest/services/map_services/' +
                'MAP_ANR_ANRATLASDWGWP_WM_NOCACHE/MapServer';
var ANR_UTILITY = 'https://anrmaps.vermont.gov/arcgis/rest/services/Open_Data/' +
                  'OPENDATA_ANR_UTILITY_SP_NOCACHE_v1/MapServer';

var ANR_LAYERS = {
  parcels: {
    checkbox: 'lyr-parcels',
    service: ANR_DWGWP,
    layerId: 15,
    pane: 'parcels',
    attribution: 'Service line inventory &copy; Vermont ANR'
  },
  sewer: {
    checkbox: 'lyr-sewer',
    service: ANR_UTILITY,
    layerId: 165,
    pane: 'sewer',
    attribution: 'Wastewater infrastructure &copy; Vermont ANR'
  }
};

Object.keys(ANR_LAYERS).forEach(function (key) {
  var cfg = ANR_LAYERS[key];
  cfg.layer = new ArcGISDynamicLayer('', {
    service: cfg.service,
    layerId: cfg.layerId,
    pane: cfg.pane,
    opacity: 0.75,
    maxZoom: 19,
    attribution: cfg.attribution
  });

  var box = document.getElementById(cfg.checkbox);
  if (!box) return;
  // Off by default: the boxes are unchecked in the markup, and nothing is
  // requested from ANR until someone ticks one.
  box.addEventListener('change', function () {
    if (box.checked) map.addLayer(cfg.layer);
    else map.removeLayer(cfg.layer);
  });
});

/* ---------- layer registry ---------- */

var LAYERS = {
  water: {
    checkbox: 'lyr-water',
    countEl: 'count-water',
    url: 'data/water_service_areas.geojson',
    layer: null,
    features: [],
    options: function () {
      return {
        pane: 'water',
        style: waterStyle,
        onEachFeature: bindWaterPopup
      };
    }
  },
  fire: {
    checkbox: 'lyr-fire',
    countEl: 'count-fire',
    url: 'data/fire_districts.geojson',
    layer: null,
    features: [],
    options: function () {
      return {
        pane: 'fire',
        style: fireStyle,
        onEachFeature: bindFirePopup
      };
    }
  },
  towns: {
    checkbox: 'lyr-towns',
    countEl: 'count-towns',
    url: 'data/town_boundaries.geojson',
    layer: null,
    features: [],
    options: function () {
      return {
        pane: 'towns',
        // A fully transparent fill (not `fill: false`) keeps the whole town
        // clickable rather than just its 1px outline. Service areas still win
        // the click where they overlap, because the water pane sits above this
        // one and takes the pointer event first.
        style: {
          color: COLORS.town,
          weight: 1,
          opacity: 0.85,
          fillColor: COLORS.town,
          fillOpacity: 0
        },
        onEachFeature: function (feature, layer) {
          var name = feature.properties.TOWNNAMEMC;
          if (!name) return;
          layer.bindTooltip(name, { sticky: true, direction: 'top' });
          // Clicking a town outline surfaces its clerk — the office holding the
          // land records that charter boundary sections cite.
          layer.bindPopup(function () { return townPopupHtml(name); },
                          { maxWidth: 300 });
        }
      };
    }
  }
};

/* ---------- town clerks ---------- */

var clerkData = { municipalities: [], byTown: {} };

// Mirrors split_name()/map_key() in script/build_site_data.py: fold Saint -> St
// and keep the City/Town suffix, so Barre Town keeps its own clerk.
function clerkKey(name) {
  var s = String(name)
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\bsaint\b/g, 'st')
    .replace(/\b(of|the)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  var m = s.match(/\b(city|town|village|gore)$/);
  return m ? s.slice(0, m.index).trim() + '|' + m[1] : s;
}

fetch('data/town_clerks.json')
  .then(function (r) { return r.ok ? r.json() : null; })
  .then(function (data) { if (data) clerkData = data; })
  .catch(function (err) { console.error(err); });

function townPopupHtml(townName) {
  var idx = clerkData.byTown[clerkKey(townName)];
  var c = idx === undefined ? null : clerkData.municipalities[idx];
  var html = '<h3>' + esc(townName) + '</h3>';

  if (!c) {
    return html + '<p class="popup-id">No clerk contact on file.</p>';
  }

  html += '<p class="popup-id">' +
    esc(c.municipality_type || 'Town') +
    (c.county ? ' &middot; ' + esc(c.county) + ' County' : '') + '</p>';

  var rows = [];
  if (c.clerk_name) rows.push(['Town clerk', esc(c.clerk_name)]);
  if (c.clerk_email) {
    rows.push(['Email', '<a href="mailto:' + esc(c.clerk_email) + '">' +
                        esc(c.clerk_email) + '</a>']);
  }
  if (c.clerk_phone) rows.push(['Phone', esc(c.clerk_phone)]);
  if (c.town_website) {
    rows.push(['Website', '<a href="' + esc(c.town_website) +
                          '" target="_blank" rel="noopener">town site &rarr;</a>']);
  }

  if (!rows.length) {
    return html + '<p class="popup-id">No clerk contact on file.</p>';
  }

  html += '<table class="popup-table">';
  rows.forEach(function (row) {
    html += '<tr><th>' + row[0] + '</th><td>' + row[1] + '</td></tr>';
  });
  html += '</table>';
  html += '<p class="popup-foot">Holds the land records cited by district charters.</p>';
  return html;
}

/* ---------- styling & popups ---------- */

function isAuthoritative(props) {
  return props.boundary_source === 'Authoritative (VT/local)';
}

function waterStyle(feature) {
  var auth = isAuthoritative(feature.properties);
  return {
    color: auth ? COLORS.auth : COLORS.modeled,
    weight: 1.4,
    opacity: 0.95,
    dashArray: auth ? null : '4 3',
    fillColor: auth ? COLORS.auth : COLORS.modeled,
    fillOpacity: 0.18
  };
}

function isRealDistrict(props) {
  return props.geometry_status === 'district';
}

function isTownwide(props) {
  return props.extent === 'coextensive_with_town';
}

function isApproximate(props) {
  return props.geometry_status === 'approximate';
}

function fireStyle(feature) {
  var p = feature.properties;
  var real = isRealDistrict(p);
  var approx = isApproximate(p);
  return {
    color: real ? COLORS.fd : approx ? COLORS.fdApprox : COLORS.fdUnconfirmed,
    weight: real ? 2.4 : 1.8,
    opacity: 0.95,
    // Town-wide districts get a dashed edge so they read as "same line as the
    // town" rather than looking like a missing boundary; both are filled,
    // because both are real district extents. Approximate extents are dotted.
    dashArray: real ? (isTownwide(p) ? '7 4' : null) : approx ? '3 5' : '2 4',
    fillColor: real ? COLORS.fd : approx ? COLORS.fdApprox : COLORS.fdUnconfirmed,
    fillOpacity: real ? 0.16 : 0.09
  };
}

function bindFirePopup(feature, layer) {
  layer.bindPopup(firePopupHtml(feature.properties), { maxWidth: 340 });
  layer.on({
    mouseover: function () {
      layer.setStyle({ weight: 4, fillOpacity: 0.22 });
      layer.bringToFront();
    },
    mouseout: function () { LAYERS.fire.layer.resetStyle(layer); }
  });
}

function firePopupHtml(p) {
  var real = isRealDistrict(p);
  var townwide = isTownwide(p);

  var approx = isApproximate(p);

  var tag = approx ? 'Approximate extent'
          : !real ? 'Unconfirmed'
          : townwide ? 'Town-wide district'
          : 'Sub-town district';

  var tagClass = approx ? 'approx' : real ? 'district' : 'placeholder';

  var html =
    '<h3>' + esc(p.district_name) + '</h3>' +
    '<p class="popup-id">' + esc(p.town) +
    (p.county ? ', ' + esc(p.county) + ' County' : '') + ' &middot; ' +
    '<span class="popup-tag ' + tagClass + '">' + tag + '</span></p>';

  if (approx) {
    html +=
      '<p class="popup-warn">Derived from the roads named in statute, not a ' +
      'surveyed boundary. Use as a starting estimate only.</p>';
  } else if (!real) {
    html +=
      '<p class="popup-warn">This boundary equals the town outline at ' +
      pct(p.town_iou) + '. It may be a town-wide district or a town outline ' +
      'filed under a district name — confirm before use.</p>';
  } else if (townwide) {
    html +=
      '<p class="popup-note">This district is coextensive with its town, so ' +
      'its area difference against the town is zero by definition. Compare it ' +
      'against the water service area instead.</p>';
  }

  var rows = [
    ['Population', num(p.population)],
    ['Boundary area', p.area_sqkm != null ? fixed(p.area_sqkm, 1) + ' km²' : null],
    ['Extent', townwide ? 'Coextensive with town' : 'Part of town (' + pct(p.town_iou) + ')'],
    ['PWSID', p.pwsid],
    ['Water system', p.pws_name ? titleCase(p.pws_name) : null],
    ['Confirmed by', p.confirmed_by],
    ['Source CRS', p.source_crs + (p.crs_inferred === 'Y' ? ' (inferred)' : '')]
  ];

  html += '<table class="popup-table">';
  rows.forEach(function (row) {
    if (row[1] === null || row[1] === undefined || row[1] === '') return;
    html += '<tr><th>' + row[0] + '</th><td>' + esc(String(row[1])) + '</td></tr>';
  });
  html += '</table>';

  // Provenance: what authorizes this polygon, quoted and linked.
  if (p.source_citation) {
    html += '<div class="popup-source"><h4>Source</h4>';
    html += p.source_url
      ? '<p><a href="' + esc(p.source_url) + '" target="_blank" ' +
        'rel="noopener">' + esc(p.source_citation) + ' &rarr;</a></p>'
      : '<p>' + esc(p.source_citation) + '</p>';
    if (p.source_text) {
      html += '<blockquote>' + esc(p.source_text) + '</blockquote>';
    }
    if (p.derivation) {
      html += '<p class="derivation">' + esc(p.derivation) + '</p>';
    }
    html += '</div>';
  }

  var foot = [];
  if (p.clerk_email) {
    foot.push('Town clerk: ' + esc(p.clerk_name || '') +
              ' &middot; <a href="mailto:' + esc(p.clerk_email) + '">' +
              esc(p.clerk_email) + '</a>');
  }
  if (p.district_website) {
    foot.push('<a href="' + esc(p.district_website) + '" target="_blank" ' +
              'rel="noopener">District website &rarr;</a>');
  }
  if (foot.length) {
    html += '<p class="popup-foot">' + foot.join('<br>') + '</p>';
  }
  return html;
}

function bindWaterPopup(feature, layer) {
  layer.bindPopup(popupHtml(feature.properties), { maxWidth: 320 });
  layer.on({
    mouseover: function () {
      layer.setStyle({ weight: 3, fillOpacity: 0.38 });
      layer.bringToFront();
    },
    mouseout: function () {
      LAYERS.water.layer.resetStyle(layer);
    }
  });
}

function popupHtml(p) {
  var auth = isAuthoritative(p);
  var rows = [
    ['Population served', num(p.Population_Served_Count)],
    ['Service connections', num(p.Service_Connections_Count)],
    ['Size category', p.Pop_Cat_5],
    ['Area type', p.Service_Area_Type],
    ['System type', p.is_community ? 'Community' : 'Non-community'],
    ['Area', p.Area_SqKM != null ? p.Area_SqKM.toFixed(2) + ' km²' : null]
  ];
  if (!auth && p.Model_Method) {
    rows.push(['Model method', p.Model_Method]);
  }

  var html =
    '<h3>' + esc(titleCase(p.PWS_Name)) + '</h3>' +
    '<p class="popup-id">' + esc(p.PWSID) + ' &middot; ' +
    '<span class="popup-tag ' + (auth ? 'auth' : 'modeled') + '">' +
    (auth ? 'Authoritative' : 'EPA-modeled') + '</span></p>' +
    '<table class="popup-table">';

  rows.forEach(function (row) {
    if (row[1] === null || row[1] === undefined || row[1] === '') return;
    html += '<tr><th>' + row[0] + '</th><td>' + esc(String(row[1])) + '</td></tr>';
  });

  html += '</table>';

  if (p.Detailed_Facility_Report) {
    html +=
      '<p style="margin:9px 0 0"><a href="' + esc(p.Detailed_Facility_Report) +
      '" target="_blank" rel="noopener">EPA facility report &rarr;</a></p>';
  }
  return html;
}

/* ---------- loading ---------- */

Object.keys(LAYERS).forEach(function (key) {
  var cfg = LAYERS[key];

  cfg.layer = L.geoJSON(null, cfg.options()).addTo(map);

  fetch(cfg.url)
    .then(function (r) {
      if (!r.ok) throw new Error(cfg.url + ': ' + r.status);
      return r.json();
    })
    .then(function (geojson) {
      cfg.features = geojson.features;
      cfg.layer.addData(geojson);
      setCount(cfg.countEl, geojson.features.length);
      syncVisibility(key);
    })
    .catch(function (err) {
      console.error(err);
      setCount(cfg.countEl, 'unavailable');
    });
});

fetch('data/meta.json')
  .then(function (r) { return r.json(); })
  .then(function (meta) {
    document.querySelectorAll('#stats [data-stat]').forEach(function (el) {
      var v = meta[el.dataset.stat];
      if (v != null) el.textContent = num(v);
    });
  })
  .catch(function (err) { console.error(err); });

/* ---------- controls ---------- */

Object.keys(LAYERS).forEach(function (key) {
  document.getElementById(LAYERS[key].checkbox)
    .addEventListener('change', function () { syncVisibility(key); });
});

function syncVisibility(key) {
  var cfg = LAYERS[key];
  var on = document.getElementById(cfg.checkbox).checked;
  if (on && !map.hasLayer(cfg.layer)) map.addLayer(cfg.layer);
  if (!on && map.hasLayer(cfg.layer)) map.removeLayer(cfg.layer);
  if (key === 'water') {
    document.getElementById('water-options').classList.toggle('disabled', !on);
  }
}

document.querySelectorAll('input[name="water-filter"]').forEach(function (input) {
  input.addEventListener('change', function () { applyWaterFilter(input.value); });
});

function applyWaterFilter(mode) {
  var cfg = LAYERS.water;
  var kept = cfg.features.filter(function (f) {
    if (mode === 'community') return f.properties.is_community === true;
    if (mode === 'authoritative') return isAuthoritative(f.properties);
    return true;
  });
  cfg.layer.clearLayers();
  cfg.layer.addData({ type: 'FeatureCollection', features: kept });
  setCount(cfg.countEl, kept.length);
}

document.querySelectorAll('input[name="basemap"]').forEach(function (input) {
  input.addEventListener('change', function () {
    Object.keys(basemaps).forEach(function (name) {
      map.removeLayer(basemaps[name]);
    });
    basemaps[input.value].addTo(map);
  });
});

var panelToggle = document.getElementById('panel-toggle');
panelToggle.addEventListener('click', function () {
  var body = document.getElementById('panel-body');
  var collapsed = !body.hidden;
  body.hidden = collapsed;
  panelToggle.textContent = collapsed ? '+' : '−';
  panelToggle.setAttribute('aria-expanded', String(!collapsed));
});

// Keep map interactions from firing when using the overlaid panels.
['layer-panel', 'search-results', 'search'].forEach(function (id) {
  var el = document.getElementById(id);
  if (el) {
    L.DomEvent.disableClickPropagation(el);
    L.DomEvent.disableScrollPropagation(el);
  }
});

/* ---------- search ---------- */

var searchInput = document.getElementById('search');
var searchResults = document.getElementById('search-results');

searchInput.addEventListener('input', function () {
  var q = searchInput.value.trim().toLowerCase();
  if (q.length < 2) {
    searchResults.hidden = true;
    return;
  }

  var hits = LAYERS.water.features.filter(function (f) {
    var p = f.properties;
    return (p.PWS_Name || '').toLowerCase().indexOf(q) > -1 ||
           (p.PWSID || '').toLowerCase().indexOf(q) > -1;
  }).slice(0, 12);

  renderResults(hits);
});

searchInput.addEventListener('blur', function () {
  // Delay so a click on a result registers before the list is hidden.
  setTimeout(function () { searchResults.hidden = true; }, 150);
});

function renderResults(hits) {
  searchResults.innerHTML = '';

  if (!hits.length) {
    var none = document.createElement('li');
    none.className = 'empty';
    none.textContent = 'No matching water system';
    searchResults.appendChild(none);
    searchResults.hidden = false;
    return;
  }

  hits.forEach(function (feature) {
    var li = document.createElement('li');
    li.innerHTML =
      esc(titleCase(feature.properties.PWS_Name)) +
      '<span class="pwsid">' + esc(feature.properties.PWSID) + '</span>';
    li.addEventListener('mousedown', function () { zoomToFeature(feature); });
    searchResults.appendChild(li);
  });

  searchResults.hidden = false;
}

function zoomToFeature(feature) {
  // The filter may have removed this feature from the map — reset to All first.
  var allRadio = document.querySelector('input[name="water-filter"][value="all"]');
  if (!allRadio.checked) {
    allRadio.checked = true;
    applyWaterFilter('all');
  }
  var box = document.getElementById(LAYERS.water.checkbox);
  if (!box.checked) {
    box.checked = true;
    syncVisibility('water');
  }

  var target = null;
  LAYERS.water.layer.eachLayer(function (l) {
    if (l.feature && l.feature.properties.PWSID === feature.properties.PWSID) target = l;
  });
  if (!target) return;

  map.fitBounds(target.getBounds(), { maxZoom: 14, padding: [40, 40] });
  target.openPopup();
  searchResults.hidden = true;
  searchInput.blur();
}

/* ---------- district roster below the map ---------- */

var districtData = [];
var districtRows = document.getElementById('district-rows');

fetch('data/districts.json')
  .then(function (r) {
    if (!r.ok) throw new Error('districts.json ' + r.status);
    return r.json();
  })
  .then(function (data) {
    districtData = data.districts || [];
    renderDistricts();
  })
  .catch(function (err) {
    console.error(err);
    districtRows.innerHTML =
      '<tr><td colspan="4" class="loading">District list unavailable.</td></tr>';
  });

['district-search', 'district-pilot-only', 'district-web-only'].forEach(function (id) {
  var el = document.getElementById(id);
  if (el) el.addEventListener('input', renderDistricts);
});

function renderDistricts() {
  var q = (document.getElementById('district-search').value || '')
    .trim().toLowerCase();
  var pilotOnly = document.getElementById('district-pilot-only').checked;
  var webOnly = document.getElementById('district-web-only').checked;

  var rows = districtData.filter(function (d) {
    if (pilotOnly && !d.pilot) return false;
    if (webOnly && !d.website) return false;
    if (!q) return true;
    return (d.name + ' ' + d.town).toLowerCase().indexOf(q) !== -1;
  });

  document.getElementById('district-count').textContent =
    rows.length === districtData.length
      ? districtData.length + ' districts in ' + townCount(districtData) + ' towns'
      : 'Showing ' + rows.length + ' of ' + districtData.length + ' districts';

  if (!rows.length) {
    districtRows.innerHTML =
      '<tr><td colspan="4" class="loading">No districts match that filter.</td></tr>';
    return;
  }

  var html = rows.map(function (d) {
    var name = d.website
      ? '<a href="' + esc(d.website) + '" target="_blank" rel="noopener">' +
        esc(d.name) + '</a>'
      : esc(d.name);

    var tags = '';
    if (d.pilot) tags += ' <span class="tag tag-pilot">pilot</span>';
    // Only districts with a real polygon get the jump-to-map badge; the
    // approximate extents are on the map too but are not a boundary.
    if (d.geometry_status === 'district') {
      tags += ' <button type="button" class="tag tag-mapped" data-fd="' +
        esc(d.fd_id) + '" title="Show this district on the map">mapped</button>';
    }
    if (!d.in_roster) tags += ' <span class="tag tag-extra">not in VRWA list</span>';

    return '<tr>' +
      '<td>' + esc(d.town) + '</td>' +
      '<td>' + name + tags + '</td>' +
      '<td>' + esc(d.services || '') + '</td>' +
      '<td class="num">' + (d.population == null ? '&mdash;' : num(d.population)) +
      '</td>' +
      '</tr>';
  }).join('');

  districtRows.innerHTML = html;
}

function townCount(list) {
  var seen = {};
  list.forEach(function (d) { seen[d.town] = true; });
  return Object.keys(seen).length;
}

// Delegated so the badges survive every re-render.
districtRows.addEventListener('click', function (ev) {
  var btn = ev.target.closest('.tag-mapped');
  if (btn) zoomToDistrict(btn.getAttribute('data-fd'));
});

function zoomToDistrict(fdId) {
  // districts.json can arrive before fire_districts.geojson does.
  if (!LAYERS.fire.layer) return;
  var box = document.getElementById(LAYERS.fire.checkbox);
  if (!box.checked) {
    box.checked = true;
    syncVisibility('fire');
  }
  var target = null;
  LAYERS.fire.layer.eachLayer(function (l) {
    if (l.feature && l.feature.properties.fd_id === fdId) target = l;
  });
  if (!target) return;

  document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'center' });
  map.fitBounds(target.getBounds(), { maxZoom: 13, padding: [40, 40] });
  target.openPopup();
}

/* ---------- helpers ---------- */

function setCount(id, value) {
  var el = document.getElementById(id);
  if (el) el.textContent = typeof value === 'number' ? '(' + num(value) + ')' : '(' + value + ')';
}

function num(v) {
  return v == null ? '' : Number(v).toLocaleString('en-US');
}

function fixed(v, digits) {
  return v == null || isNaN(Number(v)) ? '' : Number(v).toFixed(digits);
}

function pct(v) {
  return v == null || isNaN(Number(v)) ? '' : (Number(v) * 100).toFixed(1) + '%';
}

function titleCase(s) {
  if (!s) return '';
  return s.toLowerCase().replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); });
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
