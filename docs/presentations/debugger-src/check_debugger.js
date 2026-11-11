const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const m = html.match(/<script id="data">([\s\S]*?)<\/script>/);
const vm = require("vm");
const ctx = {}; vm.createContext(ctx);
vm.runInContext(m[1] + "\nthis.out={FILES,MISSING,SCEN,LANES,build,requestText,responseText,CFG};", ctx);
const { FILES, MISSING, SCEN, LANES, build, requestText, responseText } = ctx.out;
const lanes = new Set(LANES.map(l => l.k));
let problems = [...MISSING.map(x => "MISSING " + x)];
const stats = { steps: 0, flow: 0, tech: 0 };
const verbose = process.argv[3];
for (const s of SCEN) {
  const k = s.key;
  if (k !== "startup") { FILES["request.http"] = requestText(k).split("\n"); FILES["response.http"] = responseText(k).split("\n"); }
  FILES["terminal"] = ["a","b","c","d","e","f"];
  const steps = build(k);
  steps.forEach((st, i) => {
    const f = FILES[st.file];
    const where = `${k}#${i + 1}`;
    if (!f) { problems.push(where + " unknown file " + st.file); return; }
    const chk = n => { if (!(n >= 1 && n <= f.length)) problems.push(`${where} line ${n} out of ${st.file} (${f.length})`); };
    chk(st.line); (st.range || []).forEach(chk); (st.extra || []).forEach(chk);
    if (st.range && !(st.range[0] <= st.line && st.line <= st.range[1])) problems.push(`${where} line ${st.line} outside its range ${st.range}`);
    if (!lanes.has(st.at)) problems.push(where + " bad lane " + st.at);
    (st.arrows || []).forEach(a => { if (!lanes.has(a[0]) || !lanes.has(a[1])) problems.push(where + " bad arrow " + a); if (!["call","ret","err","in","out","outerr"].includes(a[2])) problems.push(where + " bad kind " + a[2]); });
    for (const key of ["title", "text", "act", "phase"]) if (!st[key]) problems.push(where + " missing " + key);
    if (!st.vars || !st.stack || !st.stack.length) problems.push(where + " missing vars/stack");
    if (!st.why) problems.push(where + " missing why");
    if (st.does && !["run", "define", "register", "skip"].includes(st.does)) problems.push(where + " bad does " + st.does);
    if (st.tech && !(Array.isArray(st.tech) && st.tech.every(t => typeof t === "string" && t))) problems.push(where + " bad tech");
    const prose = [st.title, st.text, st.why, st.flow || ""].concat(st.tech || []).join(" ");
    if (/undefined|\$\{/.test(prose)) problems.push(where + " broken text: " + prose.match(/.{0,40}(undefined|\$\{).{0,20}/)[0]);
    if ((prose.match(/<code>/g) || []).length !== (prose.match(/<\/code>/g) || []).length) problems.push(where + " unbalanced <code>");
    stats.steps++; if (st.flow) stats.flow++; if (st.tech) stats.tech++;
    if (verbose === k) console.log(String(i + 1).padStart(2), st.phase.padEnd(7), st.at.padEnd(8), (st.file + ":" + st.line).padEnd(32), "|", (f[st.line - 1] || "").trim().slice(0, 70), "|", st.title);
  });
  console.log(k.padEnd(10), steps.length, "steps");
}
console.log(`steps ${stats.steps} · with flow ${stats.flow} · with tech ${stats.tech}`);
console.log(problems.length ? problems.join("\n") : "OK: no problems");
