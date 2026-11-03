// The explorer's code, kept out of index.html so the page's Content
// Security Policy can allow scripts from this site only.
(() => {
const M = window.CORPUS, D = M.docs;
const MONTHS = []; for (let y = 2019, m = 12; y < 2023 || (y === 2023 && m <= 5); m++) { if (m > 12) { m = 1; y++ } if (y === 2023 && m > 5) break; MONTHS.push(`${y}-${String(m).padStart(2, "0")}`) }
const MN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtM = m => `${MN[+m.slice(5) - 1]} ${m.slice(0, 4)}`;
const fmtN = n => n.toLocaleString("en-US");
const EVENTS = [
  ["2020-01", "PHE declared"], ["2020-03", "National emergency"], ["2020-03", "CARES Act"],
  ["2020-04", "Cloth face coverings"], ["2020-12", "First vaccine EUA"], ["2021-01", "Biden national strategy"],
  ["2021-03", "American Rescue Plan"], ["2021-05", "Masks off if vaccinated"], ["2021-07", "Masks back indoors"],
  ["2021-12", "Isolation shortened"], ["2022-01", "COVIDtests.gov opens"], ["2022-08", "Streamlined guidance"],
  ["2023-04", "National emergency ends"], ["2023-05", "PHE ends"]];
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/* ---- documents ---- */
const st = { agency: new Set(), type: new Set(), translated: false, month: null, q: "", shown: 60 };
const typeOf = d => d.type;
function match(d, skip) {
  if (skip !== "agency" && st.agency.size && !st.agency.has(d.agency)) return false;
  if (skip !== "type" && st.type.size && !st.type.has(typeOf(d))) return false;
  if (skip !== "translated" && st.translated && !d.langs.length) return false;
  if (skip !== "month" && st.month && d.month !== st.month) return false;
  if (st.q) { const t = (d.title + " " + d.langs.join(" ")).toLowerCase(); if (!st.q.split(/\s+/).every(w => t.includes(w))) return false }
  return true;
}
function facet(title, key, values) {
  const counts = {}; D.forEach(d => { if (match(d, key)) counts[values(d)] = (counts[values(d)] || 0) + 1 });
  const all = [...new Set(D.map(values))].sort((a, b) => (counts[b] || 0) - (counts[a] || 0));
  return `<div class="facet"><h2>${title}</h2>${all.map(v => `<label><span><input type="checkbox" id="f-${key}-${esc(v).replace(/\W/g, "")}" data-k="${key}" value="${esc(v)}" ${st[key].has(v) ? "checked" : ""}> ${esc(v)}</span><span>${fmtN(counts[v] || 0)}</span></label>`).join("")}</div>`;
}
function renderFacets() {
  const tr = D.filter(d => match(d, "translated") && d.langs.length).length;
  document.getElementById("facets").innerHTML = facet("Agency", "agency", d => d.agency) + facet("Document type", "type", typeOf) +
    `<div class="facet"><h2>Languages</h2><label><span><input type="checkbox" id="f-tr" data-k="translated" ${st.translated ? "checked" : ""}> Has translations</span><span>${fmtN(tr)}</span></label></div>`;
}
// Rows of event labels above the bars. Five: the events from Dec 2020 to Jul 2021
// are close enough that each label needs its own row to keep the marker lines clear.
const EV_ROWS = 5;
const labelWidth = (() => { const c = document.createElement("canvas").getContext("2d");
  return t => { c.font = `600 10px ${getComputedStyle(document.body).fontFamily}`; return c.measureText(t).width } })();
function renderHist() {
  const counts = MONTHS.map(m => D.filter(d => d.month === m && match(d, "month")).length);
  const max = Math.max(1, ...counts), W = 1000, L = 40, R = 10, T = 14 + EV_ROWS * 13, B = T + 146, bw = (W - L - R) / MONTHS.length;
  const nice = max > 200 ? 100 : max > 50 ? 25 : max > 20 ? 10 : 5, top = Math.ceil(max / nice) * nice, y = v => B - (v / top) * (B - T);
  let s = "";
  for (let v = 0; v <= top; v += nice) s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="axis" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  counts.forEach((c, i) => {
    const m = MONTHS[i], x = L + i * bw + 1;
    s += `<rect class="bar${st.month === m ? " sel" : ""}" data-m="${m}" x="${x}" y="${y(c)}" width="${bw - 2}" height="${B - y(c)}"><title>${fmtM(m)}: ${c}</title></rect>`;
    // Years at each January only. Dec 2019 had a "Dec" label, which read as "Dec 2020" beside the 2020.
    if (m.endsWith("-01")) s += `<text class="axis" x="${x}" y="${B + 16}">${m.slice(0, 4)}</text>`;
  });
  // Each event label takes the first row, and side of its marker, where its text
  // clears the other labels and no event's marker line runs through it. Widths
  // are measured in the label font.
  const placed = [];
  EVENTS.forEach(([m, label]) => {
    const i = MONTHS.indexOf(m); if (i < 0) return;
    const x = L + i * bw + bw / 2, w = labelWidth(label);
    const clashes = (r, a, b) => placed.filter(p => p.r === r ? p.a < b + 6 && a < p.b + 6
      : p.r < r ? p.x > a - 4 && p.x < b + 4 : x > p.a - 4 && x < p.b + 4).length;
    const options = [];
    for (let r = 0; r < EV_ROWS; r++) for (const left of [false, true]) {
      const a = left ? x - 5 - w : x + 5, b = left ? x - 5 : x + 5 + w;
      if (a >= 0 && b <= W) options.push({ r, left, a, b, n: clashes(r, a, b) });
    }
    const o = options.find(o => !o.n) || options.reduce((p, q) => q.n < p.n ? q : p);
    placed.push({ r: o.r, a: o.a, b: o.b, x });
    const ly = 12 + o.r * 13;
    s += `<g class="ev"><line x1="${x}" x2="${x}" y1="${ly + 3}" y2="${B}"/><circle cx="${x}" cy="${ly}" r="3"/><text x="${o.left ? x - 5 : x + 5}" y="${ly + 3.5}"${o.left ? ` text-anchor="end"` : ""}>${esc(label)}</text></g>`;
  });
  const svg = document.getElementById("hist"); svg.innerHTML = s;
  svg.querySelectorAll(".bar").forEach(b => b.onclick = () => { st.month = st.month === b.dataset.m ? null : b.dataset.m; st.shown = 60; render() });
  document.getElementById("h-total").textContent = fmtN(counts.reduce((a, b) => a + b, 0));
  // The same filter as the bars, for the keyboard and as the chart's data in text.
  const pick = document.getElementById("month");
  pick.innerHTML = `<option value="">All months</option>` + MONTHS.map((m, i) => `<option value="${m}">${fmtM(m)} (${fmtN(counts[i])})</option>`).join("");
  pick.value = st.month || "";
}
function renderDocs() {
  const rows = D.filter(d => match(d));
  const filt = st.agency.size || st.type.size || st.translated || st.month || st.q;
  document.getElementById("count").textContent = `${fmtN(rows.length)} of ${fmtN(D.length)} documents${st.month ? ` · ${fmtM(st.month)}` : ""}`;
  document.getElementById("clear").hidden = !filt;
  document.getElementById("docs").innerHTML = rows.slice(0, st.shown).map(d => {
    const when = d.day ? new Date(d.day + "T12:00").toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }) : `by ${fmtM(d.month)}`;
    const langs = d.langs.length ? `<span class="langs" title="${esc(d.langs.join(", "))}">+${d.langs.length} language${d.langs.length > 1 ? "s" : ""}</span>` : "";
    return `<li><span class="when">${when}</span><span class="ttl"><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a></span><span class="ag">${esc(d.agency)}</span><span class="meta"><span>${esc(d.type)}</span>${langs ? "·" + langs : ""}</span></li>`;
  }).join("");
  const more = document.getElementById("more"); more.hidden = rows.length <= st.shown;
  more.textContent = `Show more (${fmtN(rows.length - st.shown)} left)`;
}
function render() { renderFacets(); renderHist(); renderDocs() }
document.getElementById("facets").addEventListener("change", e => {
  const k = e.target.dataset.k; if (!k) return;
  if (k === "translated") st.translated = e.target.checked; else e.target.checked ? st[k].add(e.target.value) : st[k].delete(e.target.value);
  // render() rebuilds the facets, so put focus back on the same checkbox.
  const id = e.target.id; st.shown = 60; render(); document.getElementById(id)?.focus();
});
document.getElementById("month").addEventListener("change", e => { st.month = e.target.value || null; st.shown = 60; render() });
document.getElementById("q").addEventListener("input", e => { st.q = e.target.value.trim().toLowerCase(); st.shown = 60; render() });
document.getElementById("more").onclick = () => { st.shown += 100; renderDocs() };
document.getElementById("clear").onclick = () => { st.agency.clear(); st.type.clear(); st.translated = false; st.month = null; st.q = ""; const q = document.getElementById("q"); q.value = ""; q.focus(); render() };

/* ---- pages over time ---- */
const NAMES = { cdc_home: "CDC COVID-19 home", cdc_masks: "Cloth face coverings", cdc_masks2: "About face coverings", cdc_spread: "How COVID spreads",
  cdc_quarantine: "Quarantine", cdc_quarantine2: "Quarantine and isolation", cdc_symptoms: "Symptoms", cdc_cases: "Cases in the U.S.",
  cdc_uptodate: "Stay up to date with vaccines", cdc_schools0: "Schools: operational strategy", cdc_schools: "K-12 guidance", cdc_travel: "Travelers",
  cdc_risk: "People at increased risk", coronavirus_gov: "coronavirus.gov", covid_gov: "covid.gov", covidtests_gov: "covidtests.gov",
  vaccines_gov: "vaccines.gov", phe_decl: "PHE declaration", cisa_covid: "CISA coronavirus", fema_covid: "FEMA coronavirus" };
function spark(p) {
  const W = 260, H = 44, bw = W / MONTHS.length, byM = Object.fromEntries(p.months.map(x => [x.m, x]));
  const vmax = Math.max(...p.months.map(x => x.v)), kmax = p.peak || 1; let s = "", pts = [];
  MONTHS.forEach((m, i) => { const x = byM[m]; if (!x) return;
    if (x.ph) s += `<rect class="ph" x="${i * bw}" y="0" width="${bw}" height="${H}"/>`;
    const h = Math.max(1, (x.v / vmax) * (H - 6)); s += `<rect class="v" x="${i * bw + .5}" y="${H - h}" width="${Math.max(1, bw - 1)}" height="${h}"/>`;
    if (x.kb != null) pts.push(`${(i + .5) * bw},${H - 2 - (x.kb / kmax) * (H - 8)}`) });
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${s}<polyline class="kb" points="${pts.join(" ")}"/></svg>`;
}
document.getElementById("pages").innerHTML = M.pages.map(p => {
  const ph = p.months.filter(x => x.ph); const name = NAMES[p.key] || p.url.split("/").filter(Boolean).pop().replace(/\.html?$/, "").replace(/-/g, " ");
  const flag = ph.length ? `<span class="flag">placeholder from ${fmtM(ph[0].m)}</span>` : "";
  const url = esc("https://" + p.url);
  const rows = p.months.map((x, i) => { const prev = p.months[i - 1];
    const diff = prev ? ` · <a href="https://web.archive.org/web/diff/${esc(prev.ts)}/${esc(x.ts)}/${url}" target="_blank" rel="noopener">diff</a>` : "";
    return `<div class="${x.ph ? "isph" : ""}"><a href="https://web.archive.org/web/${esc(x.ts)}/${url}" target="_blank" rel="noopener">${fmtM(x.m)}</a><span>${x.v} v · ${x.kb ?? "–"} KB${x.ph ? " · placeholder" : ""}${diff}</span></div>` }).join("");
  return `<details class="prow"><summary><span style="min-width:0"><div class="pname">${esc(name)} ${flag}</div><div class="purl">${esc(p.url)}</div></span>${spark(p)}<span class="pstat">${fmtN(p.versions)} versions<br>peak ${p.peak} KB</span></summary><div class="months">${rows}</div></details>`;
}).join("");

/* ---- archive.org ---- */
const CARDS = [
  ["Coronavirus (COVID-19)", "ArchiveIt-Collection-13721", "Archive-It, from the Federal Depository Library Program Web Archive (partner 593)."],
  ["COVID.gov", "ArchiveIt-Collection-19129", "Archive-It, FDLP Web Archive."],
  ["COVIDtests.gov", "ArchiveIt-Collection-18608", "Archive-It."],
  ["David J. Sencer CDC Museum COVID-19 Collection Web Archive", "ArchiveIt-Collection-16018", "The CDC museum's own web archive."],
  ["David J. Sencer CDC Museum COVID-19 Timeline Links", "ArchiveIt-Collection-20471", "The museum's timeline. A candidate backbone for the events track."],
  ["White House Coronavirus Task Force briefings", "TV-CSPAN", "C-SPAN recordings in the TV News Archive, titled “Coronavirus Task Force”.", 145],
  ["CDC YouTube channel", "cdc-youtube-channel", "All of CDC's videos, not only the COVID ones. A topic filter is still to do.", 6664],
  ["COVID-19 Apps", "COVID-19_Apps", "Archived apps, including CDC's own.", 257],
  ["U.S. Government Documents matching coronavirus or covid", "USGovernmentDocuments", "Keyword match inside the collection. Not yet read item by item.", 98],
  ["State Executive Actions Related to the COVID-19 Pandemic", "ArchiveIt-Collection-15784", "States rather than federal. A companion collection, linked but not in the corpus."]];
document.getElementById("cards").innerHTML = CARDS.map(([t, id, note, n]) => `<div class="card">${n ? `<div class="big">${fmtN(n)}<span class="num"> items</span></div>` : ""}<h2><a href="https://archive.org/details/${id}" target="_blank" rel="noopener">${esc(t)}</a></h2><div class="id">${id}</div><p>${note}</p></div>`).join("");
document.getElementById("ab-cdc").textContent = `${fmtN(M.stats.cdc_files)} CDC files fold into ${fmtN(M.stats.cdc_docs)} documents.`;
document.getElementById("stamp").textContent = `${fmtN(D.length)} documents · Wayback index read ${M.stats.harvested}`;

/* ---- views ---- */
const VIEWS = ["documents", "pages", "archive", "about"];
function show(v) { if (!VIEWS.includes(v)) v = "documents";
  VIEWS.forEach(x => document.getElementById("v-" + x).hidden = x !== v);
  document.querySelectorAll("nav.tabs a").forEach(a => a.dataset.v === v ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")) }
document.querySelectorAll("nav.tabs a").forEach(a => a.onclick = e => { e.preventDefault(); show(a.dataset.v); try { history.replaceState(null, "", "#" + a.dataset.v) } catch (_) {} });
render(); show(location.hash.slice(1));
document.fonts?.ready.then(renderHist);  // label widths change once Public Sans loads
})();
