"use strict";
/* Everything below only displays data that build_explorer.py measured and checked. It computes no irrigation number. */
const DATA = JSON.parse(document.getElementById("data").textContent);
const L = DATA.learning;
const $ = (id) => document.getElementById(id);
const FILES = {};
Object.keys(DATA.sources).forEach((p) => { FILES[p] = DATA.sources[p].replace(/\n$/, "").split("\n"); });

/* ---------- small helpers ---------- */
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function load(key, fallback) { try { const v = localStorage.getItem("p2x:" + key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; } }
function save(key, value) { try { localStorage.setItem("p2x:" + key, JSON.stringify(value)); } catch (e) { /* storage is optional */ } }
function short(path) { return path.replace(/^services\//, ""); }
function term(key, label) { return '<span class="term" data-term="' + key + '" tabindex="0" role="button">' + (label || L.glossary[key].term) + "</span>"; }
function badge(kind, ref) {
  return '<button type="button" class="badge b-' + kind + '" data-kind="' + kind + '" data-ref="' + esc(ref || "") + '">' +
    esc(L.sources[kind].label) + (ref ? ' <bdi dir="ltr">' + esc(ref) + "</bdi>" : "") + "</button>";
}
function vtag(kind) { return '<span class="vtag v-' + kind + '" data-value="' + kind + '" tabindex="0" role="button">' + esc(L.values[kind].label) + "</span>"; }

/* ---------- syntax highlighting (P1's Python rules, plus TypeScript and Markdown) ---------- */
const PY_RE = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(@[A-Za-z_][\w.]*)|\b(def|class|return|if|elif|else|try|except|finally|raise|from|import|as|with|for|while|in|not|and|or|is|None|True|False|pass|yield|async|await|lambda)\b|\b(\d+(?:\.\d+)?)\b/g;
const TS_RE = /(\/\/.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)|\b(import|from|export|default|async|await|function|return|const|let|if|else|try|catch|new|type|interface|typeof|null|true|false)\b|\b(\d+(?:\.\d+)?)\b/g;
function hlRe(line, re, classes) {
  let out = "", last = 0, m;
  re.lastIndex = 0;
  while ((m = re.exec(line)) !== null) {
    out += esc(line.slice(last, m.index));
    let cls = "";
    for (let g = 1; g < m.length; g++) if (m[g] !== undefined) { cls = classes[g - 1]; break; }
    out += '<span class="' + cls + '">' + esc(m[0]) + "</span>";
    last = re.lastIndex;
    if (m[0].length === 0) re.lastIndex++;
  }
  return out + esc(line.slice(last));
}
function hl(path, line) {
  if (/\.py$/.test(path)) return hlRe(line, PY_RE, ["c1", "s1", "d1", "k1", "n1"]);
  if (/\.tsx?$/.test(path)) return hlRe(line, TS_RE, ["c1", "s1", "k1", "n1"]);
  if (/\.md$/.test(path) && /^#/.test(line)) return '<span class="h1s">' + esc(line) + "</span>";
  return esc(line);
}
function codeLines(path, from, to, cur, curClass) {
  const lines = FILES[path] || [];
  let html = "";
  for (let n = Math.max(1, from); n <= Math.min(lines.length, to); n++) {
    const c = n === cur ? " cur" + (curClass ? " " + curClass : "") : "";
    html += '<div class="ln' + c + '" data-l="' + n + '"><span class="gut">' + n + '</span><span class="mk"></span><span class="src">' + (hl(path, lines[n - 1]) || " ") + "</span></div>";
  }
  return html;
}
function scrollToLine(box, line) {
  const el = box.querySelector('.ln[data-l="' + line + '"]');
  if (el) box.scrollTop = Math.max(0, el.offsetTop - box.clientHeight / 2 + el.offsetHeight / 2);
}

/* ---------- popover: glossary terms, value tags, source badges ---------- */
const pop = $("pop");
let popFor = null;
let seenTerms = new Set(load("seenTerms", []));
// A term the reader has not opened yet gets a "מושג חדש" chip, on its first visible appearance only.
function markNewTerms() {
  const marked = new Set();
  document.querySelectorAll(".term").forEach((el) => {
    const key = el.dataset.term, show = !seenTerms.has(key) && !marked.has(key) && el.offsetParent !== null;
    el.classList.toggle("new", show);
    if (show) marked.add(key);
  });
}
function showPop(target, html) {
  pop.innerHTML = html;
  pop.hidden = false;
  popFor = target;
  const r = target.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  let left = Math.min(Math.max(16, r.right - w), window.innerWidth - w - 16);
  let top = r.bottom + 8;
  if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 8);
  pop.style.left = left + "px"; pop.style.top = top + "px";
  markNewTerms();
}
function hidePop() { pop.hidden = true; popFor = null; }
function openTerm(el) {
  const key = el.dataset.term, t = L.glossary[key];
  seenTerms.add(key); save("seenTerms", Array.from(seenTerms));
  markNewTerms();
  showPop(el, "<h4>" + t.term + "</h4><p>" + t.text + "</p>");
}
function openValue(el) {
  const v = L.values[el.dataset.value];
  showPop(el, "<h4>" + esc(v.label) + "</h4><p>" + v.text + "</p>");
}
function findLine(path, needle) {
  const lines = FILES[path] || [];
  for (let i = 0; i < lines.length; i++) if (lines[i].indexOf(needle) !== -1) return i + 1;
  return 1;
}
function openBadge(el) {
  const kind = el.dataset.kind, ref = el.dataset.ref, s = L.sources[kind];
  let action = "";
  if (kind === "p2") action = '<a href="' + esc(L.spec_url) + '" target="_blank" rel="noopener">פתיחת המפרט (tasks/p2.md)</a>';
  if (kind === "project" && L.jl_lines[ref]) action = '<button type="button" data-open="docs/judgment-log.md" data-line="' + L.jl_lines[ref] + '">פתיחת ' + esc(ref) + " ביומן ההחלטות</button>";
  if (kind === "fao") {
    const path = "services/planner-service/docs/research/fao56.md";
    // Prefer the line where the equation itself is written ("ETc = Kc × ETo  (Ch. 5, Eq. 56)") over a passing mention.
    const lines = FILES[path] || [];
    const formula = ref ? lines.findIndex((l) => l.indexOf(ref) !== -1 && l.indexOf(" = ") !== -1 && !/^\s*[-*]/.test(l)) : -1;
    const line = formula !== -1 ? formula + 1 : findLine(path, ref || "#");
    action = '<button type="button" data-open="' + path + '" data-line="' + line + '">פתיחה ב-fao56.md</button>';
  }
  showPop(el, "<h4>" + esc(s.label) + (ref ? ' · <bdi dir="ltr">' + esc(ref) + "</bdi>" : "") + "</h4><p>" + s.text + "</p>" + (action ? '<div class="acts">' + action + "</div>" : ""));
}

/* ---------- source dialog ---------- */
function openSource(path, line) {
  hidePop();
  $("srcPath").textContent = path + (line ? ":" + line : "");
  const box = $("srcCode");
  box.innerHTML = codeLines(path, 1, (FILES[path] || []).length, line, "");
  $("srcDlg").showModal();
  scrollToLine(box, line);
}

document.addEventListener("click", (e) => {
  const t = e.target.closest(".term"), v = e.target.closest(".vtag"), b = e.target.closest(".badge"), o = e.target.closest("[data-open]");
  if (o) { openSource(o.dataset.open, Number(o.dataset.line)); return; }
  if (t) { if (popFor === t) hidePop(); else openTerm(t); return; }
  if (v) { if (popFor === v) hidePop(); else openValue(v); return; }
  if (b) { if (popFor === b) hidePop(); else openBadge(b); return; }
  if (!pop.hidden && !pop.contains(e.target)) hidePop();
});
document.addEventListener("keydown", (e) => {
  const t = e.target.closest && e.target.closest(".term, .vtag");
  if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.click(); }
  if (e.key === "Escape") hidePop();
});
$("srcClose").addEventListener("click", () => $("srcDlg").close());
window.addEventListener("resize", hidePop);

/* ---------- views ---------- */
let view = "flow";
function showView(v, quiet) {
  view = v;
  document.querySelectorAll("[data-view]").forEach((s) => { s.hidden = s.dataset.view !== v; });
  document.querySelectorAll("#views button").forEach((b) => b.setAttribute("aria-selected", b.dataset.v === v ? "true" : "false"));
  hidePop();
  // A hidden view has no layout, so the editor can only scroll to the current line once it is visible.
  if (v === "flow" && T && document.body.classList.contains("explorer")) paintEditor(false);
  if (v === "map" && panel === "system") drawWires();
  markNewTerms();
  if (!quiet) writeHash();
}
function buildViews() {
  const nav = $("views");
  Object.keys(L.views).forEach((k) => {
    const v = L.views[k], b = document.createElement("button");
    b.type = "button"; b.dataset.v = k; b.setAttribute("role", "tab");
    b.innerHTML = esc(v.label) + (v.stage > L.current_stage ? '<span class="soon">שלב ' + v.stage + "</span>" : "");
    b.addEventListener("click", () => { showView(k); });
    nav.appendChild(b);
  });
  // Views that a later increment builds say so plainly, instead of showing invented content.
  $("wIntro").innerHTML = "<p>" + L.intro + "</p>";
  $("flowNotice").innerHTML = "<p><b>" + term("trace", "מעקב") + " גולמי.</b> כאן אפשר לעבור על כל שורה של הקוד שלנו שרצה בתרחיש, עם המשתנים האמיתיים. " +
    "כאן אין הסבר כתוב לכל שורה: הטקסט בכרטיס נוצר אוטומטית מהמעקב ומתאר רק את מה שנמדד. ההסבר המודרך, צעד אחר צעד, נמצא בתצוגה הרגילה (כבו את מצב חוקר).</p>";
}

/* ---------- architecture: the system map ---------- */
const MAP_ORDER = ["browser", "next", "planner", "registry", "db", "weather", "openmeteo"];
const GROUP = { browser: "client", next: "client", planner: "planner", engine: "planner", registry: "registry", db: "registry", weather: "weather", openmeteo: "weather" };
let panel = "system", selected = null, litScenario = null;
function codeBtn(ref, small, label) {
  return '<button type="button" class="codebtn' + (small ? " small" : "") + '" data-open="' + esc(ref.file) + '" data-line="' + ref.line + '">' +
    "<span>" + (label || esc(ref.label)) + '</span><span class="loc">' + esc(short(ref.file)) + ":" + ref.line + "</span></button>";
}
function testBtn(ref) { return codeBtn(ref, true, "הבדיקה: <code>" + esc(ref.label.replace(/^def /, "").replace(/\($/, "")) + "</code>"); }
function buildMap() {
  const map = $("map");
  MAP_ORDER.forEach((key) => {
    const s = L.services[key], el = document.createElement("div");
    el.className = "box" + (key === "openmeteo" ? " ext" : "");
    el.dataset.svc = key; el.dataset.group = GROUP[key]; el.style.gridArea = key;
    el.tabIndex = 0; el.setAttribute("role", "button"); el.setAttribute("aria-label", s.name + ": " + s.title);
    el.innerHTML = '<span class="nm">' + esc(s.name) + '</span><span class="ttl">' + esc(s.title) + (s.port ? ' · <span class="port">' + esc(s.port) + "</span>" : "") + "</span>" +
      '<span class="ds">' + esc(s.short) + "</span>" +
      (key === "planner" ? '<button type="button" class="eng" data-svc="engine"><b>engine.py</b><span>' + esc(L.services.engine.title) + ": " + esc(L.services.engine.short) + "</span></button>" : "");
    map.appendChild(el);
  });
  map.addEventListener("click", (e) => {
    const target = e.target.closest(".eng") || e.target.closest(".box");
    if (target) selectService(target.dataset.svc);
  });
  map.addEventListener("keydown", (e) => {
    const box = e.target.closest && e.target.closest(".box");
    if (box && e.target === box && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); selectService(box.dataset.svc); }
  });
  if (window.ResizeObserver) new ResizeObserver(() => drawWires()).observe(map);
  renderService(null);
}
// Arrows: from the edge of one box toward the center of the other, recomputed whenever the layout changes.
function edgePoint(from, to, rect, pad) {
  const dx = to.x - from.x, dy = to.y - from.y, hw = rect.width / 2 + pad, hh = rect.height / 2 + pad;
  const t = Math.min(dx ? hw / Math.abs(dx) : Infinity, dy ? hh / Math.abs(dy) : Infinity);
  return { x: from.x + dx * t, y: from.y + dy * t };
}
function drawWires() {
  const map = $("map"), svg = $("wires");
  if (!map || map.offsetParent === null) return;
  const base = map.getBoundingClientRect();
  map.querySelectorAll(".wlabel").forEach((el) => el.remove());
  svg.setAttribute("viewBox", "0 0 " + base.width + " " + base.height);
  const head = (id) => '<marker id="' + id + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z"/></marker>';
  let html = "<defs>" + head("ah") + head("ahHot") + "</defs>";
  const hotKey = selected === "engine" ? "planner" : selected;
  const boxes = Array.from(map.querySelectorAll(".box")).map((el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left - base.left, top: r.top - base.top, right: r.right - base.left, bottom: r.bottom - base.top };
  });
  L.map_edges.forEach((edge) => {
    const a = map.querySelector('.box[data-svc="' + edge[0] + '"]').getBoundingClientRect();
    const b = map.querySelector('.box[data-svc="' + edge[1] + '"]').getBoundingClientRect();
    const ca = { x: a.left - base.left + a.width / 2, y: a.top - base.top + a.height / 2 };
    const cb = { x: b.left - base.left + b.width / 2, y: b.top - base.top + b.height / 2 };
    const p1 = edgePoint(ca, cb, a, 4), p2 = edgePoint(cb, ca, b, 7);
    const hot = hotKey && (edge[0] === hotKey || edge[1] === hotKey);
    html += '<line x1="' + p1.x + '" y1="' + p1.y + '" x2="' + p2.x + '" y2="' + p2.y + '" class="' + (hot ? "hot" : "") + '" marker-end="url(#' + (hot ? "ahHot" : "ah") + ')"/>';
    const label = document.createElement("span");
    label.className = "wlabel" + (hot ? " hot" : "");
    label.textContent = edge[2];
    map.appendChild(label);
    placeLabel(label, p1, p2, boxes);
  });
  svg.innerHTML = html;
}
// A label sits on its arrow. Where the boxes are close (narrow screens), the middle can be covered by a box,
// so try points along the arrow and just beside it, and keep the first one that covers no box.
function placeLabel(label, p1, p2, boxes) {
  const w = label.offsetWidth, h = label.offsetHeight;
  // Beside: 0 = on the arrow, then further and further to either side (into the empty space between rows).
  const along = [0.5, 0.35, 0.65, 0.2, 0.8], beside = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6];
  const horizontal = Math.abs(p2.x - p1.x) > Math.abs(p2.y - p1.y);
  let best = null, bestOverlap = Infinity;
  for (const side of beside) {
    for (const f of along) {
      const x = p1.x + (p2.x - p1.x) * f + (horizontal ? 0 : side * (w / 2 + 6));
      const y = p1.y + (p2.y - p1.y) * f + (horizontal ? side * (h / 2 + 6) : 0);
      const r = { left: x - w / 2, right: x + w / 2, top: y - h / 2, bottom: y + h / 2 };
      const overlap = boxes.reduce((sum, b) => sum + Math.max(0, Math.min(r.right, b.right) - Math.max(r.left, b.left)) *
        Math.max(0, Math.min(r.bottom, b.bottom) - Math.max(r.top, b.top)), 0);
      if (overlap < bestOverlap) { best = { x: x, y: y }; bestOverlap = overlap; }
      if (overlap === 0) break;
    }
    if (bestOverlap === 0) break;
  }
  label.style.left = best.x + "px"; label.style.top = best.y + "px";
}
function selectService(key, quiet) {
  selected = key || null;
  document.querySelectorAll("#map .box, #map .eng").forEach((el) => el.classList.toggle("sel", el.dataset.svc === selected));
  renderService(selected);
  drawWires();
  if (!quiet) writeHash();
}
function exampleHtml(s) {
  if (!s.example) return '<p class="pending">' + esc(s.no_example || "השירות הזה לא פונה לאף שירות בבקשה, ולכן אין ערכים למדוד.") + "</p>";
  const ex = s.example, sc = DATA.scenarios.find((x) => x.key === ex.scenario);
  let html = "<p>מתוך התרחיש <b>" + esc(L.scenario_labels[sc.key]) + "</b>:</p>";
  if (ex.kind === "request") {
    html += '<div class="mono">' + esc(sc.request.method + " " + sc.request.url) + '</div><span class="pill good">HTTP ' + sc.response.status + "</span>" +
      '<pre class="json">' + esc(JSON.stringify(sc.response.body, null, 2)) + "</pre>";
  } else if (ex.kind === "frame") {
    const n = sc.frames.findIndex((f) => f.function === ex.function);
    const evs = sc.events.filter((e) => e.frame === n);
    const args = evs[0].changed, ret = evs.filter((e) => e.event === "return").pop();
    html += "<p>הקלט ל-<code>" + esc(ex.function) + "()</code>:</p>" + changedList(args) +
      "<p>מה שהיא מחזירה (מקוצר):</p><div class=\"mono\">" + esc(ret ? ret.detail : "") + "</div>";
  } else if (ex.kind === "calls") {
    html += sc.calls.filter((c) => c.service === ex.service).map((c) => {
      const q = Object.keys(c.query).map((k) => k + "=" + c.query[k]).join("&");
      return '<details><summary class="mono">GET ' + esc(c.path + (q ? "?" + q : "")) + " → " + c.status + '</summary><pre class="json">' + esc(JSON.stringify(c.body, null, 2)) + "</pre></details>";
    }).join("") + '<p class="pending">אלה התשובות של ה' + term("fake", "שירות המדומה") + ", באותה צורה כמו התשובות האמיתיות.</p>";
  }
  return html;
}
function renderService(key) {
  const box = $("svcPanel");
  if (!key) {
    box.innerHTML = '<h2>פרטי השירות</h2><div class="body"><p class="pending">לחצו על שירות במפה, או על <code>engine.py</code> שבתוך planner-service.</p></div>';
    return;
  }
  const s = L.services[key];
  box.innerHTML = "<h2>" + esc(s.title) + ' · <span class="ltr">' + esc(s.name + (s.port ? " " + s.port : "")) + "</span></h2>" +
    '<div class="body"><p class="lead">' + s.role + '</p><p class="not"><b>מה הוא לא יודע או לא עושה:</b> ' + s.not + "</p>" +
    '<div class="io2"><div><h3>נכנס</h3><ul>' + s.inputs.map((x) => "<li>" + x + "</li>").join("") + "</ul></div>" +
    "<div><h3>יוצא</h3><ul>" + s.outputs.map((x) => "<li>" + x + "</li>").join("") + "</ul></div></div>" +
    '<div class="badges">' + s.badges.map((b) => badge(b[0], b[1])).join("") + "</div>" +
    "<div><h3>דוגמה מהריצה " + (s.example ? vtag("traced") : "") + "</h3>" + exampleHtml(s) + "</div>" +
    (s.code.length ? '<div><h3>הקוד</h3><ul class="codelist">' + s.code.map((c) => "<li>" + codeBtn(c) + "</li>").join("") + "</ul></div>" : "") +
    "</div>";
  markNewTerms();
}

/* ---------- architecture: the decision flow ---------- */
const OUTCOMES = {};
function outBtn(nodeId, f) {
  const key = nodeId + ":" + f.status;
  OUTCOMES[key] = Object.assign({ node: nodeId }, f);
  return '<button type="button" class="dout" data-outcome="' + key + '"><b>' + f.status + '</b><span class="cd">' + esc(f.code) + "</span><span>" + esc(f.label) + "</span>" +
    (f.scenarios.length ? "" : '<span class="none">אין תרחיש בדף · יש בדיקה</span>') + "</button>";
}
function weatherSub() {
  return '<details class="wsub"><summary>מה קורה בתוך weather-service?</summary>' +
    '<p class="pending">לא נמדד בבניית הדף: ה-planner רץ מול weather מדומה. כל שלב כאן מצביע על הקוד ועל הבדיקה שמכסה אותו. מעקב אמיתי יתווסף במסלול B.</p>' +
    '<ol class="wflow">' + L.weather_flow.map((w) => "<li><b>" + esc(w.title) + "</b><p>" + w.text + "</p>" +
      ((w.yes || w.no) ? '<div class="yn">' + (w.yes ? '<span class="y">' + (/\?$/.test(w.title) ? "כן" : "הצליח") + " → " + w.yes + "</span>" : "") +
        (w.no ? '<span class="n">לא → ' + w.no + "</span>" : "") + "</div>" : "") +
      '<div class="dmeta">' + codeBtn(w.code, true, "קוד") + testBtn(w.test) + w.badges.map((b) => badge(b[0], b[1])).join("") + "</div></li>").join("") +
    "</ol></details>";
}
function buildDecisions() {
  const chips = $("decScen");
  chips.innerHTML = DATA.scenarios.map((s) => '<button type="button" data-k="' + s.key + '"><span class="st' + (s.response.status < 400 ? " good" : "") + '">' +
    s.response.status + "</span>" + esc(L.scenario_labels[s.key]) + "</button>").join("") + '<button type="button" data-k="">בלי תרחיש</button>';
  chips.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) lightScenario(b.dataset.k || null); });
  const meta = (d) => '<div class="dmeta">' + codeBtn(d.code, true, "קוד") + (d.test ? testBtn(d.test) : "") + d.badges.map((b) => badge(b[0], b[1])).join("") + "</div>";
  const su = L.success;
  OUTCOMES.success = { node: "success", status: 200, code: "", label: su.label, scenarios: su.scenarios, test: su.test };
  $("dflow").innerHTML = L.decisions.map((d, i) => '<li class="drow" data-node="' + d.id + '"><div class="dstep"><h4><span class="dnum">' + (i + 1) + "</span>" + esc(d.title) + "</h4><p>" +
      d.text + "</p>" + meta(d) + (d.weather ? weatherSub() : "") + '</div><div class="dfails">' + d.fails.map((f) => outBtn(d.id, f)).join("") + "</div></li>").join("") +
    '<li class="drow success" data-node="success"><div class="dstep"><h4><b>200</b> ' + esc(su.label) + "</h4><p>" + su.text + "</p>" + meta(su) + "</div>" +
    '<div class="dfails"><button type="button" class="dout ok" data-outcome="success"><b>200</b><span>תוכנית, עם או בלי stale</span></button></div></li>' +
    '<li class="drow front" data-node="front"><div class="dstep"><h4>' + esc(L.frontend.title) + "</h4><p>" + L.frontend.text + '</p><div class="dmeta">' +
    L.frontend.code.map((c) => codeBtn(c, true)).join("") + L.frontend.badges.map((b) => badge(b[0], b[1])).join("") + "</div></div><div></div></li>";
  $("dflow").addEventListener("click", (e) => {
    const out = e.target.closest(".dout");
    if (!out) return;
    const o = OUTCOMES[out.dataset.outcome];
    if (o.scenarios.length) lightScenario(o.scenarios.indexOf(litScenario) !== -1 ? litScenario : o.scenarios[0]);
    else { lightScenario(null); out.classList.add("hit"); showOutcome(out.dataset.outcome, null); }
  });
  $("decOutcome").addEventListener("click", (e) => {
    const b = e.target.closest("[data-trace]");
    if (b) openTrace(b.dataset.trace);
  });
}
function lightScenario(key, quiet) {
  litScenario = key || null;
  const flow = $("dflow");
  document.querySelectorAll("#decScen button").forEach((b) => b.setAttribute("aria-pressed", (b.dataset.k || null) === litScenario ? "true" : "false"));
  flow.querySelectorAll(".drow").forEach((r) => r.classList.remove("on", "last"));
  flow.querySelectorAll(".dout").forEach((o) => o.classList.remove("hit"));
  if (!litScenario) { flow.classList.remove("lit"); $("decOutcome").hidden = true; if (!quiet) writeHash(); return; }
  const sc = DATA.scenarios.find((s) => s.key === litScenario), dp = sc.decision_path;
  flow.classList.add("lit");
  const reached = dp.nodes.concat(dp.outcome === "success" ? ["success", "front"] : ["front"]);
  let last = null;
  flow.querySelectorAll(".drow").forEach((r) => { if (reached.indexOf(r.dataset.node) !== -1) { r.classList.add("on"); last = r; } });
  const end = dp.outcome === "success" ? flow.querySelector('.drow[data-node="success"]') : flow.querySelector('.drow[data-node="' + dp.nodes[dp.nodes.length - 1] + '"]');
  if (end) end.classList.add("last");
  const hit = flow.querySelector('.dout[data-outcome="' + dp.outcome + '"]');
  if (hit) hit.classList.add("hit");
  showOutcome(dp.outcome, litScenario);
  if (!quiet) writeHash();
}
function showOutcome(outKey, scenarioKey) {
  const o = OUTCOMES[outKey], box = $("decOutcome");
  const sc = scenarioKey ? DATA.scenarios.find((s) => s.key === scenarioKey) : null;
  let html = "<h2>התוצאה: <b class=\"ltr\">" + o.status + (o.code ? " " + esc(o.code) : "") + "</b> · " + esc(o.label) + "</h2><div class=\"body\">";
  if (sc) {
    html += "<p>בתרחיש <b>" + esc(L.scenario_labels[sc.key]) + "</b> הבקשה עברה את הצעדים המודגשים והסתיימה כאן, בריצה האמיתית. " + vtag("traced") + "</p>" +
      '<pre class="json">' + esc(JSON.stringify(sc.response.body, null, 2)) + "</pre>" +
      (sc.logs.length ? '<div class="mono">' + sc.logs.map(esc).join("<br>") + "</div>" : "") +
      '<div class="dmeta"><button type="button" class="codebtn small" data-trace="' + sc.key + '"><span>המעקב הגולמי של התרחיש (מצב חוקר)</span></button>' + testBtn(o.test) + "</div>";
  } else {
    html += "<p>אף תרחיש בדף הזה לא מגיע לתוצאה הזו, ולכן אין כאן ערכים מהריצה. הבדיקה שמכסה את המקרה:</p><div class=\"dmeta\">" + testBtn(o.test) + "</div>";
  }
  box.innerHTML = html + "</div>";
  box.hidden = false;
}
function openTrace(key) {
  setExplorer(true);
  stop();
  loadScenario(key, 0);
  // Start where our code answers: the exception handler in main.py, or the last line for a plan.
  const n = T.steps.findIndex((st) => /\/main\.py$/.test(T.s.frames[st.e.frame].file));
  go(n === -1 ? T.steps.length - 1 : n);
  showView("flow");
}
function setPanel(p, quiet) {
  panel = p === "decisions" ? "decisions" : "system";
  $("panelSystem").hidden = panel !== "system";
  $("panelDecisions").hidden = panel !== "decisions";
  document.querySelectorAll("#seg button").forEach((b) => b.setAttribute("aria-selected", b.dataset.panel === panel ? "true" : "false"));
  if (panel === "system") drawWires();
  markNewTerms();
  if (!quiet) writeHash();
}

/* ---------- the guided walkthrough: authored steps tied to real moments of the trace ---------- */
let wIdx = 0;
const LANE_NAME = {};
L.lanes.forEach((l) => { LANE_NAME[l[0]] = l[1]; });
function walk() { return T.s.walkthrough; }
function wGo(n) {
  wIdx = Math.max(0, Math.min(walk().length - 1, n));
  renderWalk();
  writeHash();
}
function renderWalk() {
  // A step's kind is "error" or "ok"; the shared CSS classes are "err" and "ok".
  const steps = walk(), st = steps[wIdx], o = st.observed, kind = st.kind === "error" ? "err" : (st.kind || "");
  $("wCount").textContent = "צעד " + (wIdx + 1) + " מתוך " + steps.length;
  $("wBack").disabled = wIdx === 0;
  $("wNext").disabled = wIdx === steps.length - 1;
  $("wDots").innerHTML = steps.map((s, n) => '<button type="button" data-n="' + n + '" class="' + (s.kind === "error" ? "err" : (s.kind || "")) + (n < wIdx ? " past" : "") + (n === wIdx ? " now" : "") +
    '" title="' + esc((n + 1) + ". " + s.title) + '" aria-label="' + esc("צעד " + (n + 1) + ": " + s.title) + '"></button>').join("");
  $("wLanes").innerHTML = L.lanes.map((l) => '<span class="lane' + (l[0] === st.lane ? " from " + kind : "") + (l[0] === st.to ? " to" : "") + '">' + esc(l[1]) + "</span>").join("");
  // The authored explanation.
  $("wExp").className = "card wexp" + (kind ? " " + kind : "");
  $("wExp").innerHTML = '<div class="ex-head"><span class="act' + (kind ? " " + kind : "") + '">' + esc(LANE_NAME[st.lane]) + (st.to ? " → " + esc(LANE_NAME[st.to]) : "") + "</span>" + vtag("authored") + "</div>" +
    "<h3>" + esc(st.title) + "</h3>" +
    '<dl class="parts"><div><dt>מה אנחנו מנסים להשיג?</dt><dd>' + st.goal + "</dd></div>" +
    "<div><dt>מה קורה?</dt><dd>" + st.what + "</dd></div>" +
    "<div><dt>למה זה חשוב?</dt><dd>" + st.why + "</dd></div></dl>" +
    (st.badges.length ? '<div class="badges">' + st.badges.map((b) => badge(b[0], b[1])).join("") + "</div>" : "");
  // What the run really did at this moment.
  let obs = "";
  if (st.unobserved) obs += '<p class="pending">' + esc(st.unobserved) + "</p>";
  if (o.request) obs += "<div><h3>הבקשה שהגיעה ל-planner</h3><div class=\"mono\">" + esc(o.request.method + " " + o.request.url) + "</div></div>";
  if (o.vars && Object.keys(o.vars).length) obs += "<div><h3>משתנים בשורה הזו</h3>" + changedList(o.vars) + "</div>";
  if (o.returns) obs += Object.keys(o.returns).map((f) => "<div><h3>מה <code>" + esc(f) + "()</code> החזירה</h3><div class=\"ret\">" + esc(o.returns[f]) + "</div></div>").join("");
  if (o.calls) obs += "<div><h3>הקריאה ל-" + term("upstream") + " והתשובה של ה" + term("fake", "שירות המדומה") + "</h3><ul class=\"calls\">" + o.calls.map((c) => {
    const q = Object.keys(c.query).map((k) => k + "=" + c.query[k]).join("&");
    const result = c.error ? '<span class="bad">' + esc(c.error) + "</span>" : '<span class="' + (c.status === 200 ? "good" : "bad") + '">' + c.status + "</span>";
    return "<li><details><summary>" + esc(c.service) + " · GET " + esc(c.path + (q ? "?" + q : "")) + " → " + result + "</summary>" + (c.error ? "" : '<pre class="json">' + esc(JSON.stringify(c.body, null, 2)) + "</pre>") + "</details></li>";
  }).join("") + "</ul></div>";
  if (o.response) obs += "<div><h3>התשובה של ה-planner</h3><span class=\"pill " + (o.response.status < 400 ? "good" : "bad") + "\">HTTP " + o.response.status + "</span>" +
    '<pre class="json">' + esc(JSON.stringify(o.response.body, null, 2)) + "</pre></div>";
  if (o.logs && o.logs.length) obs += "<div><h3>הלוג בטרמינל</h3><div class=\"mono\">" + o.logs.map(esc).join("<br>") + "</div></div>";
  const c = st.code;
  obs += "<div><h3>איפה בקוד</h3><div class=\"whereline\">" + esc(short(c.file)) + " · line " + c.line + "</div>" +
    '<div class="excerpt"><div class="code">' + codeLines(c.file, c.line - 2, c.line + 2, c.line, kind) + "</div></div>" +
    '<div class="dmeta" style="margin-top:6px"><button type="button" class="codebtn small" data-open="' + esc(c.file) + '" data-line="' + c.line + '"><span>הקובץ המלא</span></button>' +
    (st.test ? testBtn(st.test) : "") +
    (typeof st.event === "number" ? '<button type="button" class="codebtn small" data-raw="' + st.event + '"><span>הרגע הזה במעקב הגולמי (מצב חוקר)</span></button>' : "") + "</div></div>";
  $("wObs").innerHTML = "<h2>מה נמדד בריצה " + (st.unobserved && !o.response && !o.request ? "" : vtag("traced")) + '</h2><div class="body">' + obs + "</div>";
  markNewTerms();
}
function bindWalk() {
  $("wBack").addEventListener("click", () => wGo(wIdx - 1));
  $("wNext").addEventListener("click", () => wGo(wIdx + 1));
  $("wDots").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) wGo(Number(b.dataset.n)); });
  $("wObs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-raw]");
    if (b) { setExplorer(true); go(Number(b.dataset.raw)); }
  });
}

/* ---------- the calculation explorer ---------- */
// Every number here is a string the engine produced (build_explorer.py). This code only places those strings into
// the authored formulas, and turns them into positions for the two charts. It computes no irrigation value.
let calcCase = "case3-start-100", calcDay = 5, calcStep = 0, kcCrop = null, veilSkipped = {};
let answered = load("answered", {});
function caseData(key) { return DATA.cases.find((c) => c.key === key); }
function family(key) { return /^case3/.test(key) ? "case3" : key; }
function plotNum(s) {  // for drawing only: "29.75" or "5000/3 (≈1666.667)" as a number of pixels' worth
  const m = String(s).match(/^(-?\d+)\/(\d+)/);
  return m ? Number(m[1]) / Number(m[2]) : parseFloat(s);
}
function fill(template, values, derived) {
  return esc(template).replace(/\{(\w+)\}/g, (all, k) => {
    if (!(k in values)) return all;
    if (k === "compare") return esc(values[k]);
    return '<span class="' + ((derived || []).indexOf(k) !== -1 ? "dv" : "tv") + '">' + esc(values[k]) + "</span>";
  });
}
const VALUE_KEY = '<div class="vkey">ערכים: <span class="tv">קו ירוק</span> נמדד בריצה · <span class="dv">קו סגול מקווקו</span> ערך הסבר</div>';
function fcard(c, values, line) {
  return '<div class="fcard"><h4>' + esc(c.title) + '</h4><div class="formula">' + esc(c.formula) + '</div><div class="subst">' + fill(c.sub, values, c.derived) + "</div>" +
    '<div class="units">יחידות: ' + esc(c.units) + "</div><p>" + c.text + "</p>" + (c.assume ? '<p class="assume"><b>הנחה:</b> ' + c.assume + "</p>" : "") +
    '<div class="badges">' + c.badges.map((b) => badge(b[0], b[1])).join("") + "</div>" +
    (line ? '<div class="excerpt"><div class="code">' + codeLines(ENGINE_FILE, line - 1, line + 1, line, "") + "</div></div>" : "") + "</div>";
}
const ENGINE_FILE = "services/planner-service/engine.py";
function setupValues(c) {
  const iv = c.input_values;
  return { awc: iv.available_water_mm_per_m, zr: iv.root_depth_m, taw: c.setup.taw, threshold: c.setup.threshold, area: iv.area_m2,
           row: iv.row_spacing_m, spacing: iv.emitter_spacing_m, emitters: c.setup.emitters, flow_lph: iv.flow_lph, flow: c.setup.flow, daily_cap_l: c.setup.daily_cap_l };
}
function dayValues(c, i) {
  const d = c.days[i];
  return Object.assign({}, d.values, {
    season_day: d.season_day, prev_end: i ? c.days[i - 1].values.end : c.setup.previous_end, rain_mm: d.rain_mm, et0_mm: d.et0_mm,
    taw: c.setup.taw, threshold: c.setup.threshold, flow: c.setup.flow, daily_cap_l: c.setup.daily_cap_l,
    without_irrigation_mm: d.derived.without_irrigation_mm, desired_l: d.derived.desired_l, compare: d.derived.below_threshold ? "<" : "≥",
  });
}
function section(key, inner) {
  const n = L.calc.sections.findIndex((s) => s[0] === key);
  return '<section class="card csec" id="sec-' + key + '"><h2>' + (n + 1) + ". " + esc(L.calc.sections[n][1]) + '</h2><div class="body">' + inner + "</div></section>";
}
function buildCalc() {
  $("cIntro").innerHTML = "<p>" + L.calc.intro + "</p>";
  $("cNav").innerHTML = L.calc.sections.map((s, n) => '<a href="#calc" data-sec="' + s[0] + '">' + (n + 1) + ". " + esc(s[1]) + "</a>").join("");
  $("cNav").addEventListener("click", (e) => { const a = e.target.closest("a"); if (a) { e.preventDefault(); scrollToSection(a.dataset.sec); } });
  $("cPick").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-family]");
    if (b) setCase(b.dataset.family === "case3" ? "case3-start-100" : b.dataset.family);
  });
  $("cPick").addEventListener("input", (e) => { if (e.target.id === "cStart") setCase("case3-start-" + e.target.value); });
  $("calcBody").addEventListener("click", calcClick);
  renderCalc();
}
function scrollToSection(key) {
  const el = $("sec-" + key);
  if (el) el.scrollIntoView({ block: "start" });
}
function setCase(key, quiet) {
  if (!caseData(key)) return;
  calcCase = key; calcDay = key === "case3-start-100" ? 5 : (key === "b1" || key === "b2" ? 6 : (key === "b4" ? 5 : 0)); calcStep = 0;
  renderCalc();
  if (!quiet) writeHash();
}
function renderPick() {
  const fam = family(calcCase), info = L.calc.case_labels[fam];
  const pct = caseData(calcCase).input_values.initial_soil_water_pct;
  $("cPick").innerHTML = '<div class="row1">' + Object.keys(L.calc.case_labels).map((f) => '<button type="button" data-family="' + f + '" aria-pressed="' + (f === fam) + '">' +
      esc(L.calc.case_labels[f].title) + "</button>").join("") + "</div>" +
    '<p class="about">' + esc(info.text) + "</p>" +
    (fam === "case3" ? '<div class="start"><label for="cStart">הדלי בבוקר יום 1: <b>' + esc(pct) + '%</b></label><input type="range" id="cStart" min="0" max="100" step="10" value="' + esc(pct) + '">' +
      '<span class="pending">' + (pct === "100" ? "100% היא ברירת המחדל (JL-011)." : "סימולציה: לא מדידה, ולא המלצה שנבדקה בשדה.") + "</span></div>" : "");
}
function renderCalc() {
  renderPick();
  const c = caseData(calcCase);
  const sv = setupValues(c);
  const html = [
    section("inputs", inputsHtml(c)),
    section("kc", kcHtml(c)),
    section("etc", etcHtml()),
    section("taw", VALUE_KEY + '<div class="fgrid">' + L.calc.setup_cards.map((k) => fcard(k, sv, k.line)).join("") + "</div>"),
    section("day", '<div id="dayBox"></div>'),
    section("week", weekHtml(c)),
    section("rounding", roundingHtml(c)),
    section("limits", limitsHtml()),
  ].join("");
  $("calcBody").innerHTML = html;
  renderDay();
  markNewTerms();
}
function inputsHtml(c) {
  const iv = c.input_values;
  const rows = L.calc.input_fields.map((f) => "<tr><td>" + esc(f[1]) + '</td><td class="n">' + esc(iv[f[0]]) + "</td><td>" + esc(f[2]) + "</td><td>" + esc(f[3]) + "</td></tr>").join("");
  const days = c.days.map((d, n) => "<tr><td>" + (n + 1) + '</td><td class="n">' + esc(d.date) + '</td><td class="n">' + esc(d.et0_mm) + '</td><td class="n">' + esc(d.rain_mm) + "</td></tr>").join("");
  return "<p>אלה הערכים שהמנוע קיבל בריצה " + vtag("traced") + ". הם הגיעו מהתשובות של ה" + term("fake", "שירותים המדומים") + ", בדיוק כמו בבדיקות.</p>" +
    '<div class="tbl"><table><thead><tr><th>קלט</th><th>ערך</th><th>יחידה</th><th>מאיפה</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
    "<p>והתחזית, מ-weather:</p>" +
    '<div class="tbl"><table><thead><tr><th>יום</th><th>תאריך</th><th>' + term("et0", "ET0") + " (מ\"מ)</th><th>גשם (מ\"מ)</th></tr></thead><tbody>" + days + "</tbody></table></div>";
}
function kcChart(crop, marks) {
  const cv = DATA.kc_curves[crop], n = cv.kc_by_day.length, W = 720, H = 240, pl = 36, pr = 10, pt = 14, pb = 30;
  const x = (day) => pl + (day - 1) / (n - 1) * (W - pl - pr), y = (k) => pt + (1 - k / 1.3) * (H - pt - pb);
  const colors = { ini: "var(--s-units-bg)", dev: "var(--s-fao-bg)", mid: "var(--blue-bg)", late: "var(--s-project-bg)" };
  let s = '<div class="chartwrap"><svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Kc לאורך העונה">';
  Object.keys(cv.stage_days).forEach((st) => {
    const r = cv.stage_days[st];
    s += '<rect class="band" x="' + x(r[0]) + '" y="' + pt + '" width="' + (x(r[1]) - x(r[0])) + '" height="' + (H - pt - pb) + '" fill="' + colors[st] + '"/>' +
      '<text x="' + (x(r[0]) + x(r[1])) / 2 + '" y="' + (pt + 14) + '" text-anchor="middle">' + esc(L.calc.stage_names[st]) + "</text>";
  });
  [0, 0.5, 1].forEach((k) => { s += '<line class="grid" x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(k) + '" y2="' + y(k) + '"/><text x="' + (pl - 6) + '" y="' + (y(k) + 4) + '" text-anchor="end">' + k + "</text>"; });
  (marks || []).forEach((m) => { s += '<rect class="mark" x="' + (x(m[0]) - 2) + '" y="' + pt + '" width="' + Math.max(4, x(m[1]) - x(m[0]) + 4) + '" height="' + (H - pt - pb) + '"/>'; });
  s += '<polyline class="kc" points="' + cv.kc_by_day.map((k, i) => x(i + 1) + "," + y(plotNum(k))).join(" ") + '"/>';
  [1, cv.stage_days.dev[0], cv.stage_days.mid[0], cv.stage_days.late[0], n].forEach((d) => { s += '<text x="' + x(d) + '" y="' + (H - 10) + '" text-anchor="middle">' + d + "</text>"; });
  return s + "</svg></div>";
}
function kcHtml(c) {
  const crop = kcCrop || c.crop_id, cv = DATA.kc_curves[crop];
  const marks = crop === c.crop_id ? [[c.days[0].season_day, c.days[c.days.length - 1].season_day]] : [];
  const stages = Object.keys(cv.stage_days).map((st) => "<tr><td>" + esc(L.calc.stage_names[st]) + '</td><td class="n">' + cv.stage_days[st][0] + "–" + cv.stage_days[st][1] + "</td><td>" +
    (st === "ini" ? "Kc ini = " + esc(cv.kc_ini) : st === "mid" ? "Kc mid = " + esc(cv.kc_mid) : st === "dev" ? "קו ישר מ-" + esc(cv.kc_ini) + " ל-" + esc(cv.kc_mid) : "קו ישר מ-" + esc(cv.kc_mid) + " ל-" + esc(cv.kc_end)) + "</td></tr>").join("");
  const pepper = DATA.kc_curves["bell-pepper"];
  const exCards = DATA.kc_examples.map((ex) => fcard(Object.assign({}, L.calc.kc_card, { title: L.calc.kc_card.title + " · " + ex.source + " (פלפל)" }),
    { kc_ini: pepper.kc_ini, kc_mid: pepper.kc_mid, l_ini: pepper.stages.ini, l_dev: pepper.stages.dev, day: ex.day, kc: ex.kc + (String(ex.kc_api) !== ex.kc ? " → " + ex.kc_api : "") }, L.calc.kc_card.line)).join("");
  const season = DATA.season.map((r) => "<tr><td>" + (r.crop_id === "tomato" ? "עגבנייה" : "פלפל") + '</td><td class="n">' + esc(r.today) + '</td><td class="n">' + r.days + '</td><td class="n">' + r.first_day + "–" + r.last_day +
    '</td><td class="n">' + r.status + "</td><td>" + (r.weather_called ? "כן" : "לא") + "</td></tr>").join("");
  return "<p>" + L.calc.kc_intro + "</p>" +
    '<div class="row1 seg" role="group">' + ["tomato", "bell-pepper"].map((k) => '<button type="button" data-kc="' + k + '" aria-selected="' + (k === crop) + '">' + (k === "tomato" ? "עגבנייה" : "פלפל") + "</button>").join("") + "</div>" +
    kcChart(crop, marks) +
    '<div class="legend2"><span><i class="box" style="background:var(--cur);opacity:.5"></i>ימי התוכנית בדוגמה שנבחרה</span><span>הקו: Kc בכל יום, מ-<code>kc_on</code> של המנוע ' + vtag("traced") + "</span></div>" +
    '<div class="tbl"><table><thead><tr><th>שלב</th><th>ימים בעונה</th><th>Kc</th></tr></thead><tbody>' + stages + "</tbody></table></div>" +
    VALUE_KEY + '<div class="fgrid">' + exCards + "</div>" + quizHtml("b3kc") +
    "<h3>מחוץ לעונה (B6)</h3><p>" + L.calc.season_text + "</p>" +
    '<div class="tbl"><table><thead><tr><th>גידול</th><th>היום בשדה</th><th>days</th><th>ימים בעונה</th><th>תשובה</th><th>weather נשאל?</th></tr></thead><tbody>' + season + "</tbody></table></div>";
}
function etcHtml() {
  return "<p>" + L.calc.etc_intro + "</p>" + VALUE_KEY + '<div class="fgrid">' + L.calc.etc_cards.map((k) => fcard(k, DATA.case_1, k.line)).join("") + "</div>";
}
function pendingQuiz() {
  return L.calc.predictions.find((q) => q.case === calcCase && q.day === calcDay + 1 && answered[q.id] === undefined && !veilSkipped[q.id]);
}
function quizHtml(id) {
  const q = L.calc.predictions.find((x) => x.id === id), a = answered[id];
  const opts = q.options.map((o, n) => '<button type="button" data-quiz="' + id + '" data-opt="' + n + '" class="' + (a !== undefined && a === n ? (o.correct ? "right" : "wrong") : "") +
    (a !== undefined && o.correct ? " right" : "") + '">' + esc(o.text) + "</button>").join("");
  const fb = a !== undefined ? '<div class="fb ' + (q.options[a].correct ? "right" : "wrong") + '"><b>' + (q.options[a].correct ? "נכון." : "לא בדיוק.") + "</b> " + q.options[a].why +
    (q.options[a].correct ? "" : " <b>התשובה:</b> " + esc(q.options.find((o) => o.correct).text) + ".") + "</div>" : "";
  return '<div class="quiz"><h4>שאלת חיזוי</h4><p>' + q.question + '</p><div class="opts">' + opts + "</div>" + fb +
    (a === undefined && q.case ? '<button type="button" class="skip" data-skip="' + id + '">דלגו והציגו את התוצאה</button>' : "") + "</div>";
}
function renderDay() {
  const box = $("dayBox");
  if (!box) return;
  const c = caseData(calcCase), st = L.calc.day_steps[calcStep], d = c.days[calcDay], api = c.plan.days[calcDay];
  const questions = L.calc.predictions.filter((x) => x.case === calcCase && x.day === calcDay + 1);
  const veil = pendingQuiz();  // results stay blurred until every question on this day is answered or skipped
  box.innerHTML = '<div class="daypick" role="group" aria-label="יום">' + c.days.map((x, n) => '<button type="button" data-day="' + n + '" class="' + (x.values.applied_l !== "0" ? "irr" : "") +
      '" aria-pressed="' + (n === calcDay) + '">יום ' + (n + 1) + (x.values.applied_l !== "0" ? " · השקיה" : "") + "</button>").join("") + "</div>" +
    '<div class="steppick" role="group" aria-label="צעד">' + L.calc.day_steps.map((s, n) => '<button type="button" data-step="' + n + '" aria-pressed="' + (n === calcStep) + '">' + (n + 1) + ". " + esc(s.title) + "</button>").join("") + "</div>" +
    questions.map((x) => quizHtml(x.id)).join("") +
    '<div class="' + (veil ? "veiled" : "") + '">' + VALUE_KEY + fcard(st, dayValues(c, calcDay), d.lines[st.var === "desired_mm" ? "desired_mm" : st.var]) +
    '<div class="apirow" style="margin-top:8px"><b>בתשובה של ה-API (מעוגל):</b><span>kc <span class="n">' + api.kc + '</span></span><span>litres <span class="n">' + api.litres + '</span></span><span>run_minutes <span class="n">' + api.run_minutes +
    '</span></span><span>bucket_level_mm <span class="n">' + api.bucket_level_mm + "</span></span></div></div>" +
    '<div class="dmeta"><button type="button" class="codebtn small" data-cstep="-1"><span>הצעד הקודם</span></button><button type="button" class="codebtn small" data-cstep="1"><span>הצעד הבא</span></button></div>';
  markNewTerms();
}
function weekChart(c) {
  const W = 720, H = 280, pl = 40, pr = 10, pt = 16, pb = 40, n = c.days.length, taw = plotNum(c.setup.taw);
  const bw = (W - pl - pr) / n, y = (v) => pt + (1 - v / (taw * 1.08)) * (H - pt - pb);
  let s = '<div class="chartwrap"><svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="מפלס הדלי בסוף כל יום">';
  s += '<line class="taw" x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(taw) + '" y2="' + y(taw) + '"/><text x="' + (pl - 6) + '" y="' + (y(taw) + 4) + '" text-anchor="end">TAW</text>';
  s += '<line class="thr" x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(plotNum(c.setup.threshold)) + '" y2="' + y(plotNum(c.setup.threshold)) + '"/><text x="' + (pl - 6) + '" y="' + (y(plotNum(c.setup.threshold)) + 4) + '" text-anchor="end">סף</text>';
  c.days.forEach((d, i) => {
    const x0 = pl + i * bw + bw * 0.2, w = bw * 0.6, end = plotNum(d.values.end), start = plotNum(d.values.start);
    s += '<rect class="bar' + (i === calcDay ? " sel" : "") + '" data-day="' + i + '" x="' + x0 + '" y="' + y(end) + '" width="' + w + '" height="' + (y(0) - y(end)) + '"><title>' + esc("יום " + (i + 1) + ": סוף היום " + d.values.end + " מ\"מ") + "</title></rect>";
    s += '<circle class="start" cx="' + (x0 + w / 2) + '" cy="' + y(start) + '" r="4"><title>' + esc("בוקר, אחרי הגשם: " + d.values.start) + "</title></circle>";
    if (d.values.applied_l !== "0") s += '<text x="' + (x0 + w / 2) + '" y="' + (y(end) - 8) + '" text-anchor="middle" style="fill:var(--blue);font-weight:600">' + esc(c.plan.days[i].litres + " L") + "</text>";
    s += '<text x="' + (x0 + w / 2) + '" y="' + (H - 22) + '" text-anchor="middle">יום ' + (i + 1) + '</text><text x="' + (x0 + w / 2) + '" y="' + (H - 7) + '" text-anchor="middle">' + esc(d.values.end) + "</text>";
  });
  return s + "</svg></div>";
}
function weekHtml(c) {
  const rows = c.days.map((d, i) => {
    const api = c.plan.days[i];
    return '<tr data-day="' + i + '" class="' + (d.values.applied_l !== "0" ? "irr" : "") + (i === calcDay ? " sel" : "") + '"><td>' + (i + 1) + '</td><td class="n">' + esc(d.et0_mm) + '</td><td class="n">' + esc(d.rain_mm) +
      '</td><td class="n">' + esc(d.values.kc) + '</td><td class="n">' + esc(d.values.start) + '</td><td class="n">' + esc(d.values.etc) + '</td><td class="n"><span class="dv">' + esc(d.derived.without_irrigation_mm) +
      '</span></td><td class="n">' + esc(d.values.applied_l) + (d.derived.capped ? " (תקרה)" : "") + '</td><td class="n">' + esc(d.values.run_minutes) + '</td><td class="n">' + esc(d.values.end) +
      '</td><td class="n">' + api.litres + " / " + api.run_minutes + " / " + api.bucket_level_mm + "</td></tr>";
  }).join("");
  return "<p>המפלס בסוף כל יום. ביום שמשקים, הדלי מתמלא בבוקר ויורד במשך היום. הנקודה היא המפלס בבוקר, אחרי הגשם. לחיצה על יום פותחת אותו ב\"יום אחד בדלי\".</p>" +
    weekChart(c) + '<div class="legend2"><span><i style="border-color:var(--ok)"></i>TAW, דלי מלא</span><span><i style="border-color:var(--err)"></i>הסף, חצי דלי</span><span><i class="box" style="background:var(--s-fao)"></i>סוף היום</span>' +
    "<span>● הבוקר, אחרי הגשם</span>" + vtag("traced") + "</div>" + VALUE_KEY +
    '<div class="tbl"><table><thead><tr><th>יום</th><th>ET0</th><th>גשם</th><th>Kc</th><th>בוקר (start)</th><th>ETc</th><th>start − ETc</th><th>ליטרים</th><th>דקות</th><th>סוף היום</th><th>API: ליטרים / דקות / מפלס</th></tr></thead><tbody>' +
    rows + "</tbody></table></div>";
}
function roundingHtml(c) {
  const b5 = DATA.rounding.map((r) => '<tr><td class="n">' + esc(r.value) + '</td><td class="n">' + r.places + '</td><td class="n">' + esc(r.result) + "</td></tr>").join("");
  const exact = c.days.map((d, i) => "<tr><td>" + (i + 1) + '</td><td class="n">' + esc(d.values.applied_l) + '</td><td class="n">' + c.plan.days[i].litres + '</td><td class="n">' + esc(d.values.run_minutes) +
    '</td><td class="n">' + c.plan.days[i].run_minutes + '</td><td class="n">' + esc(d.values.end) + '</td><td class="n">' + c.plan.days[i].bucket_level_mm + "</td></tr>").join("");
  return "<p>" + L.calc.rounding_text + "</p>" +
    "<p>בדוגמה שנבחרה: הערך המדויק של המנוע, ולידו מה שה-API מחזיר " + vtag("traced") + ".</p>" +
    '<div class="tbl"><table><thead><tr><th>יום</th><th>ליטרים מדויק</th><th>API</th><th>דקות מדויק</th><th>API</th><th>מפלס מדויק</th><th>API</th></tr></thead><tbody>' + exact + "</tbody></table></div>" +
    "<p>פונקציית העיגול על מקרי קצה (B5), מ-<code>round_half_up</code> עצמה:</p>" +
    '<div class="tbl"><table><thead><tr><th>ערך</th><th>ספרות</th><th>תוצאה</th></tr></thead><tbody>' + b5 + "</tbody></table></div>" +
    "<p>למה " + term("fraction") + " ולא float? שלוש דוגמאות מ-<code>worked-examples.md</code>, שם החישוב עם float נעשה בנפרד:</p><ul>" +
    L.calc.float_notes.map((f) => "<li><b>" + esc(f.case) + ":</b> " + esc(f.text) + "</li>").join("") + "</ul>" +
    '<div class="dmeta">' + badge("project", "JL-018") + badge("project", "JL-019") + "</div>";
}
function limitsHtml() {
  const full = caseData("case3-start-100"), half = caseData("case3-start-50");
  const firstIrr = (c) => c.days.findIndex((d) => d.values.applied_l !== "0") + 1;
  return "<p>המודל הזה פשוט בכוונה, כדי שאפשר יהיה לבדוק אותו ביד. אלה הדברים שהוא לא יודע, ומה יכול להשתבש בגללם.</p>" +
    '<div class="limits">' + L.calc.limits.map((l) => {
      let ex = "";
      if (l.example === "first_irrigation") ex = "דוגמה מהריצה: Case 3 מדלי מלא משקה לראשונה ביום " + firstIrr(full) + ". אותה חלקה ואותה תחזית, מחצי דלי: כבר ביום " + firstIrr(half) + ".";
      if (l.example === "cap") ex = "דוגמה: ביום 6 ב-Case 3 הדלי מסתיים ב-" + full.days[5].values.end + " מ\"מ (נמדד בריצה), ולא ב-" + l.quote + " כמו בלי התקרה, לפי worked-examples.";
      return '<div class="limit"><h4>' + esc(l.title) + "</h4><p>" + l.text + '</p><p class="risk"><b>מה יכול להשתבש:</b> ' + l.risk + "</p>" + (ex ? '<p class="ex">' + esc(ex) + "</p>" : "") +
        '<div class="badges">' + l.badges.map((b) => badge(b[0], b[1])).join("") + "</div></div>";
    }).join("") + "</div>";
}
function calcClick(e) {
  const t = e.target;
  const day = t.closest("[data-day]"), step = t.closest("[data-step]"), cstep = t.closest("[data-cstep]"), kc = t.closest("[data-kc]");
  const opt = t.closest("[data-opt]"), skip = t.closest("[data-skip]");
  if (opt) {
    answered[opt.dataset.quiz] = Number(opt.dataset.opt); save("answered", answered);
    if (opt.closest("#dayBox")) renderDay(); else { const box = opt.closest(".quiz"); box.outerHTML = quizHtml(opt.dataset.quiz); markNewTerms(); }
    return;
  }
  if (skip) { veilSkipped[skip.dataset.skip] = true; renderDay(); return; }
  if (kc) { kcCrop = kc.dataset.kc; const sec = $("sec-kc"); sec.outerHTML = section("kc", kcHtml(caseData(calcCase))); markNewTerms(); return; }
  if (step) { calcStep = Number(step.dataset.step); renderDay(); return; }
  if (cstep) {
    const n = calcDay * L.calc.day_steps.length + calcStep + Number(cstep.dataset.cstep), max = caseData(calcCase).days.length * L.calc.day_steps.length - 1;
    const m = Math.max(0, Math.min(max, n));
    calcDay = Math.floor(m / L.calc.day_steps.length); calcStep = m % L.calc.day_steps.length;
    renderDay(); refreshWeekSelection(); return;
  }
  if (day && !t.closest("#dayBox .daypick") && t.closest("#sec-week")) { calcDay = Number(day.dataset.day); renderDay(); refreshWeekSelection(); scrollToSection("day"); return; }
  if (day) { calcDay = Number(day.dataset.day); renderDay(); refreshWeekSelection(); }
}
function refreshWeekSelection() {
  const sec = $("sec-week");
  if (sec) { sec.outerHTML = section("week", weekHtml(caseData(calcCase))); markNewTerms(); }
}

/* ---------- the trace stepper ---------- */
let T = null, idx = 0, playing = false, timer = null, edFile = null;
function prepare(s) {
  const state = s.frames.map(() => ({})), lastLine = s.frames.map(() => null);
  const steps = s.events.map((e, i) => {
    Object.assign(state[e.frame], e.changed);
    lastLine[e.frame] = e.line;
    const stack = [];
    for (let f = e.frame; f !== null && f !== undefined; f = s.frames[f].parent) stack.push({ f: f, line: lastLine[f] });
    const prevInFrame = s.events.slice(0, i).reverse().find((x) => x.frame === e.frame);
    return { e: e, vars: Object.assign({}, state[e.frame]), stack: stack, depth: stack.length,
             unwinding: e.event === "return" && prevInFrame && prevInFrame.event === "exception" };
  });
  const files = [];
  s.frames.forEach((f) => { if (files.indexOf(f.file) === -1) files.push(f.file); });
  return { s: s, steps: steps, files: files };
}
function firstStepIn(t, at) {
  for (let i = 0; i < t.steps.length; i++) {
    const f = t.s.frames[t.steps[i].e.frame];
    if (f.file === at.file && f.function === at.function) return i;
  }
  return 0;
}
function statusText(s) { return s.response.status + (s.response.body && s.response.body.code ? " " + s.response.body.code : ""); }
function buildScenarios() {
  const box = $("scen");
  DATA.scenarios.forEach((s) => {
    const b = document.createElement("button");
    b.type = "button"; b.dataset.k = s.key;
    b.innerHTML = '<span class="st' + (s.response.status < 400 ? " good" : "") + '">' + s.response.status + "</span>" + esc(L.scenario_labels[s.key]);
    b.addEventListener("click", () => { stop(); loadScenario(s.key, 0); });
    box.appendChild(b);
  });
}
function loadScenario(key, at) {
  const s = DATA.scenarios.find((x) => x.key === key) || DATA.scenarios[0];
  T = prepare(s);
  idx = typeof at === "number" ? at : 0;
  edFile = null;
  moves = [];  // "back" never jumps into another scenario
  wIdx = 0;
  document.querySelectorAll("#scen button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.k === s.key ? "true" : "false"));
  $("scrub").max = String(T.steps.length - 1);
  renderTabs();
  renderRequest();
  renderWalk();
  update();
}
function renderRequest() {
  const s = T.s;
  const calls = s.calls.map((c) => {
    const q = Object.keys(c.query).map((k) => k + "=" + c.query[k]).join("&");
    const result = c.error ? '<span class="bad">' + esc(c.error) + "</span>" : '<span class="' + (c.status === 200 ? "good" : "bad") + '">' + c.status + "</span>";
    const body = c.error ? "" : '<pre class="json">' + esc(JSON.stringify(c.body, null, 2)) + "</pre>";
    return "<li><details><summary>" + esc(c.service) + " · GET " + esc(c.path + (q ? "?" + q : "")) + " → " + result + "</summary>" + body + "</details></li>";
  }).join("");
  $("rrTag").innerHTML = vtag("traced");
  $("rr").innerHTML = "<dl>" +
    "<div><dt>הבקשה</dt><dd class=\"mono\">" + esc(s.request.method + " " + s.request.url) + "</dd></div>" +
    "<div><dt>התאריך (UTC) של ה-planner</dt><dd class=\"mono\">" + esc(s.request.utc_today) + "</dd></div>" +
    "<div><dt>קריאות ל-" + term("upstream") + " (" + term("fake", "שירותים מדומים") + ")</dt><dd>" + (calls ? '<ul class="calls">' + calls + "</ul>" : "אין: ה-planner לא פנה לאף שירות.") + "</dd></div>" +
    "<div><dt>התשובה</dt><dd><span class=\"pill " + (s.response.status < 400 ? "good" : "bad") + "\">HTTP " + s.response.status + "</span>" +
    '<pre class="json">' + esc(JSON.stringify(s.response.body, null, 2)) + "</pre></dd></div>" +
    (s.logs.length ? "<div><dt>הלוג בטרמינל</dt><dd class=\"mono\">" + s.logs.map(esc).join("<br>") + "</dd></div>" : "") +
    "</dl>";
  markNewTerms();
}
function renderTabs() {
  const tabs = $("tabs");
  tabs.innerHTML = "";
  T.files.forEach((f) => {
    const b = document.createElement("button");
    b.type = "button"; b.dataset.f = f; b.setAttribute("role", "tab");
    b.textContent = f.replace("services/planner-service/", "");
    b.addEventListener("click", () => { edFile = f; paintEditor(true); });
    tabs.appendChild(b);
  });
}
function paintEditor(peek) {
  const st = T.steps[idx], file = T.s.frames[st.e.frame].file;
  if (!peek) edFile = file;
  const box = $("edCode");
  box.innerHTML = codeLines(edFile, 1, FILES[edFile].length, edFile === file ? st.e.line : 0, stepClass(st));
  $("edPath").innerHTML = "<span>" + esc(short(edFile)).replace(/([^/]+)$/, "<b>$1</b>") + "</span>";
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.f === edFile);
    b.classList.toggle("live", b.dataset.f === file);
  });
  if (edFile === file) scrollToLine(box, st.e.line); else box.scrollTop = 0;
}
function stepClass(st) {
  if (st.e.event === "exception") return "err";
  if (idx === T.steps.length - 1) return T.s.response.status < 400 ? "ok" : "err";
  return "";
}
function changedList(changed) {
  const keys = Object.keys(changed);
  if (!keys.length) return '<span class="pending">אף משתנה לא השתנה בצעד הזה.</span>';
  return '<ul class="chg">' + keys.map((k) => '<li><span class="k">' + esc(k) + '</span><span class="v">' + esc(changed[k]) + "</span></li>").join("") + "</ul>";
}
function update() {
  const st = T.steps[idx], e = st.e, f = T.s.frames[e.frame], last = idx === T.steps.length - 1;
  const cls = stepClass(st);
  $("explain").className = "card explain raw" + (cls ? " " + cls : "");  // keep "raw": the card belongs to explorer mode
  const ACT = { line: "שורה", exception: "חריגה", "return": "יציאה מפונקציה" };
  $("act").textContent = ACT[e.event]; $("act").className = "act" + (cls ? " " + cls : "");
  $("thread").innerHTML = f.thread === "worker" ? term("worker") : (f.thread === "event-loop" ? term("loop") : esc(f.thread));
  $("exTag").innerHTML = vtag("traced");
  $("exTitle").innerHTML = '<span class="ltr">' + esc(f.function + "()") + "</span>";
  $("pGoal").innerHTML = '<span class="pending">אין הסבר כתוב לשורה בודדת במעקב הגולמי. ההסבר המודרך נמצא בתצוגה הרגילה.</span>';
  let what;
  if (e.event === "line") what = "השורה המסומנת עומדת לרוץ. המשתנים מוצגים כפי שהם ממש לפני שהיא רצה, כמו בדיבאגר.";
  else if (e.event === "exception") what = "נזרקה " + term("exception", "חריגה") + ": <code>" + esc(e.detail) + "</code>. אם הפונקציה לא תופסת אותה, היא עוברת לפונקציה שקראה לה.";
  else if (st.unwinding) what = "הפונקציה נעצרת בגלל החריגה, בלי להחזיר ערך. החריגה ממשיכה לפונקציה שקראה לה.";
  else what = "הפונקציה מסתיימת ומחזירה <code>" + esc(e.detail) + "</code>.";
  if (last) what += " זה הצעד האחרון של הקוד שלנו בתרחיש. התשובה שיצאה: <code>HTTP " + esc(statusText(T.s)) + "</code>.";
  $("pWhat").innerHTML = what;
  $("pIo").innerHTML = changedList(e.changed);
  $("pWhere").innerHTML = esc(short(f.file)) + " · " + esc(f.function) + "() · line " + e.line +
    ' · <button type="button" class="linkbtn" data-open="' + esc(f.file) + '" data-line="' + e.line + '">הקובץ המלא</button>';
  $("excerpt").innerHTML = codeLines(f.file, e.line - 2, e.line + 2, e.line, cls);
  // explorer mode
  $("varsTag").innerHTML = '<span class="ltr">' + esc(f.function) + "()</span> " + vtag("traced");
  const names = Object.keys(st.vars);
  $("vars").innerHTML = names.length ? names.map((k) => '<li class="' + (k in e.changed ? "chg2" : "") + '"><span class="k">' + esc(k) + '</span><span class="v">' + esc(st.vars[k]) + "</span></li>").join("")
    : '<li class="pending" style="direction:rtl;text-align:right">אין משתנים מקומיים.</li>';
  let stack = "";
  st.stack.forEach((x, n) => {
    const fr = T.s.frames[x.f];
    stack += '<li class="' + (n === 0 ? "top" : "") + '">' + esc(fr.function + "()   " + short(fr.file) + ":" + x.line) + "</li>";
    const below = st.stack[n + 1];
    if (below && T.s.frames[below.f].thread !== fr.thread) stack += '<li class="thr">↓ מכאן ומטה: תהליכון אחר</li>';
  });
  $("stack").innerHTML = stack;
  if (document.body.classList.contains("explorer")) paintEditor(false);
  // toolbar
  $("counter").textContent = "צעד " + (idx + 1) + " מתוך " + T.steps.length;
  $("scrub").value = String(idx);
  const status = $("status");
  if (last) { status.textContent = "HTTP " + T.s.response.status; status.className = "pill " + (T.s.response.status < 400 ? "good" : "bad"); }
  else if (e.event === "exception") { status.textContent = "חריגה"; status.className = "pill bad"; }
  else { status.textContent = "רץ"; status.className = "pill"; }
  $("bBack").disabled = $("bRestart").disabled = idx === 0;
  $("bOver").disabled = $("bInto").disabled = last;
  $("bOut").disabled = last || st.depth <= 1;
  markNewTerms();
  writeHash();
}
// "Back" undoes the last move (after "step" skipped a called function, it returns to where you were),
// so every move remembers where it came from.
let moves = [];
function go(n) {
  const target = Math.max(0, Math.min(T.steps.length - 1, n));
  if (target !== idx) moves.push(idx);
  idx = target;
  update();
}
function back() {
  idx = moves.length ? moves.pop() : Math.max(0, idx - 1);
  update();
}
// Step over: the next event in this function or one that called it. Into: the very next event. Out: the caller's next event.
function stepOver() { const d = T.steps[idx].depth; for (let j = idx + 1; j < T.steps.length; j++) if (T.steps[j].depth <= d) return go(j); go(T.steps.length - 1); }
function stepOut() { const d = T.steps[idx].depth; for (let j = idx + 1; j < T.steps.length; j++) if (T.steps[j].depth < d) return go(j); go(T.steps.length - 1); }
function stop() { playing = false; clearInterval(timer); timer = null; $("bPlay").textContent = "הפעלה"; $("bPlay").setAttribute("aria-pressed", "false"); }
function play() {
  if (idx === T.steps.length - 1) go(0);
  playing = true; $("bPlay").textContent = "השהיה"; $("bPlay").setAttribute("aria-pressed", "true");
  clearInterval(timer);
  timer = setInterval(() => { if (idx >= T.steps.length - 1) stop(); else stepOver(); }, Number($("speed").value));
}
function bindToolbar() {
  $("bRestart").addEventListener("click", () => { stop(); go(0); });
  $("bBack").addEventListener("click", () => { stop(); back(); });
  $("bOver").addEventListener("click", () => { stop(); stepOver(); });
  $("bInto").addEventListener("click", () => { stop(); go(idx + 1); });
  $("bOut").addEventListener("click", () => { stop(); stepOut(); });
  $("bPlay").addEventListener("click", () => { if (playing) stop(); else play(); });
  $("speed").addEventListener("change", () => { if (playing) play(); });
  $("scrub").addEventListener("input", () => { stop(); go(Number($("scrub").value)); });
  $("bExplorer").addEventListener("click", () => setExplorer(!document.body.classList.contains("explorer")));
  document.addEventListener("keydown", (e) => {
    if (view !== "flow" || $("srcDlg").open) return;
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "SELECT" || tag === "INPUT") return;
    if (!document.body.classList.contains("explorer")) {
      if (e.key === "F10" || e.key === "ArrowDown") { e.preventDefault(); wGo(wIdx + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); wGo(wIdx - 1); }
      return;
    }
    if (e.key === "F10" || e.key === "ArrowDown") { e.preventDefault(); stop(); stepOver(); }
    else if (e.key === "F11" && e.shiftKey) { e.preventDefault(); stop(); stepOut(); }
    else if (e.key === "F11") { e.preventDefault(); stop(); go(idx + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); stop(); back(); }
    else if (e.key === "Home") { e.preventDefault(); stop(); go(0); }
  });
}

/* ---------- modes: explorer, presenter, theme ---------- */
function setExplorer(on) {
  document.body.classList.toggle("explorer", on);
  $("bExplorer").setAttribute("aria-pressed", on ? "true" : "false");
  save("explorer", on);
  if (on && T) {
    const st = walk()[wIdx];
    if (st && typeof st.event === "number" && idx === 0) { idx = st.event; update(); }
    paintEditor(false);
  }
  if (T) writeHash();
}
function setPresenter(on) {
  document.body.classList.toggle("presenter", on);
  $("bPresenter").setAttribute("aria-pressed", on ? "true" : "false");
  save("presenter", on);
  if (on) setExplorer(false);
}
const THEMES = [["auto", "אוטומטית"], ["light", "בהירה"], ["dark", "כהה"]];
function setTheme(name) {
  if (name === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.dataset.theme = name;
  $("bTheme").textContent = "ערכה: " + THEMES.find((t) => t[0] === name)[1];
  save("theme", name);
}

/* ---------- learning paths ---------- */
let path = null; // { key, stop }
function buildPaths() {
  const sel = $("pathSel");
  sel.innerHTML = '<option value="">חקירה חופשית</option>' + Object.keys(L.paths).map((k) => '<option value="' + k + '">מסלול: ' + esc(L.paths[k].label) + "</option>").join("");
  sel.addEventListener("change", () => { if (sel.value) goStop(sel.value, 0); else { path = null; save("path", null); renderPathbar(); } });
  $("pBack").addEventListener("click", () => goStop(path.key, path.stop - 1));
  $("pNext").addEventListener("click", () => goStop(path.key, path.stop + 1));
}
function stopBuilt(stop) { return !stop.stage; }
function goStop(key, n) {
  const stops = L.paths[key].stops;
  n = Math.max(0, Math.min(stops.length - 1, n));
  path = { key: key, stop: n };
  save("path", path);
  const target = stops[n];
  if (target.view === "calc") {
    showView("calc");
    renderPathbar();
    if (target.section) scrollToSection(target.section);
    return;
  }
  if (target.view === "map") {
    setPanel(target.panel || "system", true);
    if (panel === "decisions") lightScenario(target.scenario || null, true);
    else selectService(target.service || null, true);
  } else if (target.scenario) {
    stop();
    loadScenario(target.scenario, 0);
    if (target.at) go(firstStepIn(T, target.at));
    if (target.step) wGo(walk().findIndex((s) => s.key === target.step));
  }
  showView(target.view);
  renderPathbar();
}
function renderPathbar() {
  const bar = $("pathbar");
  $("pathSel").value = path ? path.key : "";
  if (!path) { bar.hidden = true; return; }
  const p = L.paths[path.key], stop = p.stops[path.stop];
  bar.hidden = false;
  $("pName").textContent = "מסלול: " + p.label;
  $("pCount").textContent = "תחנה " + (path.stop + 1) + " מתוך " + p.stops.length;
  $("pTitle").innerHTML = esc(stop.title) + (stopBuilt(stop) ? "" : ' <span class="pending">· התחנה הזו תיבנה בשלב ' + stop.stage + "</span>");
  $("pDots").innerHTML = p.stops.map((s, n) => '<button type="button" class="' + (n === path.stop ? "now" : "") + (stopBuilt(s) ? " built" : " later") +
    '" data-n="' + n + '" aria-label="תחנה ' + (n + 1) + ": " + esc(s.title) + '" title="' + esc((n + 1) + ". " + s.title + (stopBuilt(s) ? "" : " (שלב " + s.stage + ")")) + '"></button>').join("");
  $("pDots").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => goStop(path.key, Number(b.dataset.n))));
  $("pBack").disabled = path.stop === 0;
  $("pNext").disabled = path.stop === p.stops.length - 1;
}

/* ---------- sources & terms view (real examples only) ---------- */
function buildSources() {
  const examples = {
    p2: ["כשהדלי היה יורד מתחת לחצי, משקים", "P2"],
    fao: ["<code>TAW = available_water_mm_per_m × Zr</code>", "Eq. 82"],
    project: ["השקיה מוגבלת ל-24 שעות ביום", "JL-014"],
    units: ["1 מ\"מ מים על 1 מ\"ר הוא ליטר אחד", ""],
  };
  $("srcLegend").innerHTML = Object.keys(L.sources).map((k) => {
    const s = L.sources[k], ex = examples[k];
    return "<li><div>" + badge(k, ex[1] === "P2" ? "" : ex[1]) + "</div><div>" + s.text + '</div><div class="ex">דוגמה: ' + ex[0] + "</div></li>";
  }).join("");
  $("valLegend").innerHTML = Object.keys(L.values).map((k) => "<li><div>" + vtag(k) + "</div><div>" + L.values[k].text + "</div></li>").join("");
  // A real example of both kinds: day 6 of Case 3, the day the 24-hour cap is reached.
  const c3 = DATA.cases.find((c) => c.key === "case3-start-100"), d6 = c3.days[5];
  $("valExample").innerHTML = '<p style="margin:14px 0 6px;font-weight:600">דוגמה מהנתונים: יום 6 ב-Case 3 (' + esc(d6.date) + ")</p>" +
    '<table class="vals"><tbody>' +
    "<tr><td>הליטרים שהמנוע קבע ליום (<code>applied_l</code>)</td><td class=\"num\">" + esc(d6.values.applied_l) + " L</td><td>" + vtag("traced") + "</td></tr>" +
    "<tr><td>תקרת היום: 24 שעות של זרימת המערכת (<code>daily_cap_l</code>)</td><td class=\"num\">" + esc(c3.setup.daily_cap_l) + " L</td><td>" + vtag("traced") + "</td></tr>" +
    "<tr><td>הליטרים שהיו ממלאים את הדלי, לפני התקרה (<code>desired_mm × area_m2</code>)</td><td class=\"num\">" + esc(d6.derived.desired_l) + " L</td><td>" + vtag("derived") + "</td></tr>" +
    "</tbody></table>";
  $("gloss").innerHTML = Object.keys(L.glossary).map((k) => "<dt>" + L.glossary[k].term + "</dt><dd>" + L.glossary[k].text + "</dd>").join("");
}

/* ---------- address bar: #flow/registry-down/12, #sources ---------- */
function writeHash() {
  let h = "#" + view;
  if (view === "flow" && T) h += "/" + T.s.key + "/" + (document.body.classList.contains("explorer") ? String(idx + 1) : "s" + (wIdx + 1));
  if (view === "calc") h += "/" + calcCase;
  if (view === "map") h += "/" + panel + ((panel === "system" ? selected : litScenario) ? "/" + (panel === "system" ? selected : litScenario) : "");
  try { history.replaceState(null, "", h); } catch (e) { /* optional */ }
}
function readHash() {
  const parts = location.hash.slice(1).split("/");
  return { view: L.views[parts[0]] ? parts[0] : null, a: parts[1], b: parts[2] };
}

/* ---------- start ---------- */
(function init() {
  const m = DATA.meta;
  $("build").innerHTML = (m.commit ? "<span>נבנה מ-commit <code>" + esc(m.commit) + "</code></span>" : '<span class="warn">נבנה מעותק בלי git: לא ידוע מאיזה commit</span>') +
    (m.uncommitted_changes ? '<span class="warn">כולל שינויים שלא נשמרו ב-commit</span>' : "") +
    '<span class="ltr" dir="ltr">' + esc(m.versions) + "</span><span>הדף נבנה רק אם כל הבדיקות עברו.</span>";
  buildViews(); buildScenarios(); buildPaths(); buildSources(); bindToolbar(); buildMap(); buildDecisions(); bindWalk(); buildCalc();
  document.querySelectorAll("#seg button").forEach((b) => b.addEventListener("click", () => setPanel(b.dataset.panel)));
  window.addEventListener("resize", () => { if (view === "map") drawWires(); });
  setTheme(load("theme", "auto"));
  $("bTheme").addEventListener("click", () => {
    const cur = load("theme", "auto"), i = THEMES.findIndex((t) => t[0] === cur);
    setTheme(THEMES[(i + 1) % THEMES.length][0]);
  });
  $("bPresenter").addEventListener("click", () => setPresenter(!document.body.classList.contains("presenter")));
  setPresenter(load("presenter", false));
  setExplorer(load("explorer", false) && !document.body.classList.contains("presenter"));
  const h = readHash();
  const q = new URLSearchParams(location.search);  // ?explorer=1 or ?presenter=1, for links and screenshots
  if (q.get("explorer") === "1") setExplorer(true);
  if (q.get("presenter") === "1") setPresenter(true);
  const guidedStep = h.view === "flow" && h.b && h.b[0] === "s";
  loadScenario(h.view === "flow" && h.a ? h.a : "plan", h.view === "flow" && h.b && !guidedStep ? Number(h.b) - 1 : 0);
  if (guidedStep) wGo(Number(h.b.slice(1)) - 1);
  if (h.view === "map") {
    setPanel(h.a, true);
    if (panel === "system" && L.services[h.b]) selectService(h.b, true);
    if (panel === "decisions" && DATA.scenarios.some((s) => s.key === h.b)) lightScenario(h.b, true);
  } else setPanel("system", true);
  if (h.view === "calc" && h.a) setCase(h.a, true);
  path = load("path", null);
  if (path && !L.paths[path.key]) path = null;
  renderPathbar();
  showView(h.view || "map", true);
  writeHash();
  markNewTerms();
})();
