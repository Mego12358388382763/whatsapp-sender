// Gulf Health Community Intelligence dashboard (vanilla JS, no build step).
// All external text is escaped before rendering: comments are untrusted input.

const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
const link = (u, label) => { const s = safeUrl(u); return s ? `<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(label || u)}</a>` : esc(label || u); };
const txt = (v) => `<span dir="auto">${esc(v)}</span>`;
const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const chips = (arr) => `<div class="chips">${(arr || []).map((x) => `<span class="chip" dir="auto">${esc(x)}</span>`).join("")}</div>`;
const empty = (msg) => `<div class="empty">${esc(msg || "No data yet. Add data from the “Add data” tab.")}</div>`;

let META = null;
const state = { tab: "overview", commentsOffset: 0, contentIdeas: [] };

function qs(extra = {}) {
  const p = new URLSearchParams();
  const country = $("#f-country").value, platform = $("#f-platform").value;
  if (country) p.set("country", country);
  if (platform) p.set("platform", platform);
  for (const [k, v] of Object.entries(extra)) if (v !== "" && v != null && v !== false) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
}

function table(cols, rows) {
  if (!rows.length) return empty();
  const head = cols.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr>${cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.render(r)}</td>`).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// ---------------------------------------------------------------- tooltip
const tip = $("#tooltip");
function showTip(e, html) { tip.innerHTML = html; tip.hidden = false; moveTip(e); }
function moveTip(e) {
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + w > innerWidth - 8) x = e.clientX - w - pad;
  if (y + h > innerHeight - 8) y = e.clientY - h - pad;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
function hideTip() { tip.hidden = true; }

// ---------------------------------------------------------------- overview
async function loadOverview() {
  const [o, topics, runs] = await Promise.all([api(`/api/overview${qs()}`), api(`/api/topics/top${qs()}`), api("/api/runs")]);
  const pct = o.comments_analyzed ? Math.round((100 * o.relevant) / o.comments_analyzed) : 0;
  const tiles = [
    ["Communities analysed", fmt(o.communities)], ["Posts analysed", fmt(o.posts)],
    ["Comments analysed", fmt(o.comments_analyzed)], ["Relevant discussions", `${fmt(o.relevant)} <span class="small muted">(${pct}%)</span>`],
    ["Countries", fmt(Object.keys(o.countries).filter((c) => c !== "unknown").length),
     Object.keys(o.countries).filter((c) => c !== "unknown").join(" · ")],
    ["Platforms", fmt(Object.keys(o.platforms).length), Object.keys(o.platforms).join(" · ")],
  ];
  $("#tiles").innerHTML = tiles.map(([l, v, detail]) => `<div class="tile"><div class="v">${v}</div><div class="l">${esc(l)}</div>${detail ? `<div class="small muted">${esc(detail)}</div>` : ""}</div>`).join("");

  const max = Math.max(1, ...topics.map((t) => t.count));
  $("#bars").innerHTML = topics.length ? topics.map((t, i) => `
    <div class="bar-row" data-i="${i}">
      <div class="bar-label" title="${esc(t.topic)}">${esc(t.topic)}${t.discovered ? '<span class="tag-new">new</span>' : ""}</div>
      <div class="bar-track"><div class="bar" style="width:${(92 * t.count) / max}%"></div><span class="bar-value">${fmt(t.count)}</span></div>
    </div>`).join("") : empty();
  document.querySelectorAll(".bar-row").forEach((row) => {
    const t = topics[+row.dataset.i];
    const html = `<strong>${esc(t.topic)}</strong>${t.topic_ar ? ` · <span dir="rtl">${esc(t.topic_ar)}</span>` : ""}<br>
      ${fmt(t.count)} relevant comments<br>${fmt(t.questions)} questions / help requests (${Math.round((100 * t.questions) / t.count)}%)`;
    row.addEventListener("mouseenter", (e) => showTip(e, html));
    row.addEventListener("mousemove", moveTip);
    row.addEventListener("mouseleave", hideTip);
  });
  $("#bars-table").innerHTML = table(
    [{ label: "Topic", render: (t) => esc(t.topic) }, { label: "Arabic", render: (t) => txt(t.topic_ar) },
     { label: "Relevant comments", num: true, render: (t) => fmt(t.count) }, { label: "Questions / help", num: true, render: (t) => fmt(t.questions) }],
    topics);

  $("#runs").innerHTML = table(
    [{ label: "#", render: (r) => r.id }, { label: "Source", render: (r) => esc(r.source) }, { label: "Status", render: (r) => esc(r.status) + (r.error ? ` <span class="small muted">${esc(r.error)}</span>` : "") },
     { label: "New posts", num: true, render: (r) => fmt(r.stats?.posts_new) }, { label: "New comments", num: true, render: (r) => fmt(r.stats?.comments_new) },
     { label: "Duplicates", num: true, render: (r) => fmt(r.stats?.comments_duplicate) }, { label: "When", render: (r) => esc((r.started_at || "").slice(0, 16).replace("T", " ")) }],
    runs.slice(0, 8));
}

$("#toggle-table").addEventListener("click", (e) => {
  const showTable = $("#bars-table").hidden;
  $("#bars-table").hidden = !showTable; $("#bars").hidden = showTable;
  e.target.textContent = showTable ? "Show chart" : "Show table";
  e.target.setAttribute("aria-pressed", String(showTable));
});

// ------------------------------------------------------------- communities
async function loadCommunities() {
  const rows = await api(`/api/communities${qs()}`);
  $("#communities").innerHTML = table([
    { label: "Community", render: (c) => `${link(c.url, c.name)}<div class="small muted">${esc(c.city || "")}</div>` },
    { label: "Country", render: (c) => esc(c.country || "—") },
    { label: "Platform", render: (c) => esc(c.platform) },
    { label: "Comments analysed", num: true, render: (c) => fmt(c.comments_analyzed) },
    { label: "Relevant", num: true, render: (c) => `${fmt(c.relevant)}<div class="small muted">${c.relevant_pct}%</div>` },
    { label: "Top topics", render: (c) => chips(c.top_topics.slice(0, 4).map((t) => `${t.topic} ${Math.round(t.share * 100)}%`)) },
    { label: "Common questions", render: (c) => (c.top_questions || []).slice(0, 2).map((q) => `<div class="small">${txt(q.question)} <span class="muted">×${q.count}</span></div>`).join("") },
    { label: "Growing", render: (c) => chips((c.growth || []).filter((g) => g.growth > 0).slice(0, 3).map((g) => `${g.topic} +${Math.round(g.growth * 100)}%`)) },
    { label: "Opportunity", num: true, render: (c) => `<span class="score">${c.opportunity_score}</span>` },
  ], rows);
}

// ------------------------------------------------------------------ posts
async function loadPosts() {
  const rows = await api(`/api/posts${qs()}`);
  $("#posts").innerHTML = table([
    { label: "Post", render: (p) => `${link(p.url, p.title || p.url)}<div class="small muted">${esc(p.dominant_language || "")}</div>` },
    { label: "Platform", render: (p) => esc(p.platform) },
    { label: "Community", render: (p) => esc(p.community) },
    { label: "Topics", render: (p) => chips(p.topic_distribution.map((t) => `${t.topic} ${t.share}%`)) },
    { label: "Relevant comments", num: true, render: (p) => fmt(p.relevant_comments) },
    { label: "Engagement", num: true, render: (p) => fmt(p.engagement) },
    { label: "Repeated phrases", render: (p) => chips(p.top_phrases.slice(0, 4).map((x) => x.phrase)) },
    { label: "Score", num: true, render: (p) => `<span class="score">${p.score}</span>` },
  ], rows);
}

// --------------------------------------------------------------- comments
async function loadComments() {
  const limit = 50;
  const data = await api(`/api/comments${qs({
    topic_id: $("#c-topic").value, intent: $("#c-intent").value, min_relevance: $("#c-min").value,
    q: $("#c-q").value, questions_only: $("#c-questions").checked, limit, offset: state.commentsOffset,
  })}`);
  $("#comments").innerHTML = table([
    { label: "Comment", render: (c) => txt(c.comment) },
    { label: "Topic", render: (c) => chips(c.topics.filter(Boolean)) },
    { label: "Intent", render: (c) => `${esc(c.intent)}<div class="small muted">conf ${c.confidence} · ${esc(c.method)}</div>` },
    { label: "Country / community", render: (c) => `${esc(c.country || "—")}<div class="small muted">${esc(c.community)}</div>` },
    { label: "Post", render: (c) => link(c.post_url, "open") },
    { label: "Relevance", num: true, render: (c) => `<span class="score">${c.relevance}</span>` },
  ], data.items);
  const from = data.total ? state.commentsOffset + 1 : 0;
  $("#c-page").textContent = `${from}–${Math.min(state.commentsOffset + limit, data.total)} of ${data.total}`;
  $("#c-prev").disabled = state.commentsOffset === 0;
  $("#c-next").disabled = state.commentsOffset + limit >= data.total;
}
$("#c-go").addEventListener("click", () => { state.commentsOffset = 0; loadComments(); });
$("#c-prev").addEventListener("click", () => { state.commentsOffset = Math.max(0, state.commentsOffset - 50); loadComments(); });
$("#c-next").addEventListener("click", () => { state.commentsOffset += 50; loadComments(); });

// -------------------------------------------------------------- scorecards
async function loadScorecards() {
  const rows = await api(`/api/scorecards${qs()}`);
  $("#scorecards").innerHTML = rows.length ? rows.map((o) => `
    <article class="sc">
      <h3 dir="auto">${esc(o.suggested_scorecard)} <span class="score" title="Opportunity score">${o.score}</span></h3>
      <dl class="kv">
        <dt>Problem cluster</dt><dd>${esc(o.problem_cluster)}</dd>
        <dt>Discussions</dt><dd>${fmt(o.discussion_count)} (${esc(o.volume)})</dd>
      </dl>
      <h3>Typical questions</h3>
      ${(o.typical_questions || []).map((q) => `<div class="small">• ${txt(q.question)} <span class="muted">×${q.count}</span></div>`).join("") || '<div class="small muted">—</div>'}
      <h3>Educational hook</h3><p class="hook" dir="auto">“${esc(o.hook)}”</p>
      <p class="cta" dir="auto">CTA: ${esc(o.cta)}</p>
      <div class="small muted">${esc(o.key)} · ${esc(o.method)}</div>
    </article>`).join("") : empty("No scorecard opportunities yet for this selection.");
}

// ----------------------------------------------------------------- content
const KIND_LABELS = { reel: "Reel ideas", hook: "Hooks", faq: "FAQ topics", carousel: "Carousel ideas", article: "Article ideas", lead_magnet: "Lead magnets", scorecard: "Scorecard ideas" };
async function loadContent() {
  state.contentIdeas = await api("/api/content-ideas");
  const sel = $("#ci-topic"), cur = sel.value;
  sel.innerHTML = state.contentIdeas.map((t) => `<option value="${t.topic_id}">${esc(t.topic)}</option>`).join("");
  if (cur) sel.value = cur;
  renderContent();
}
function renderContent() {
  const t = state.contentIdeas.find((x) => String(x.topic_id) === $("#ci-topic").value) || state.contentIdeas[0];
  if (!t) { $("#content").innerHTML = empty(); return; }
  $("#content").innerHTML = `<p class="small muted">Generated from anonymised discussion patterns (${esc(t.method)}). Educational use only. Not medical advice.</p>
    <div class="ideas">${Object.entries(KIND_LABELS).filter(([k]) => t.ideas[k]).map(([k, label]) =>
      `<section><h3>${esc(label)}</h3><ol>${t.ideas[k].map((i) => `<li dir="auto">${esc(i)}</li>`).join("")}</ol></section>`).join("")}</div>`;
}
$("#ci-topic").addEventListener("change", renderContent);

// ------------------------------------------------------------- reply queue
state.replies = [];
async function loadReplies() {
  const data = await api(`/api/replies${qs({ status: $("#r-status").value })}`);
  state.replies = data.items;
  const over = data.today > data.daily_soft_limit;
  $("#r-today").textContent = `${data.today} replies today`;
  $("#r-today").style.color = over ? "var(--warn)" : "";
  if (!data.items.length) {
    $("#replies").innerHTML = empty($("#r-status").value === "pending"
      ? "No questions waiting. Press “Find new questions” after adding or analysing data." : "Nothing here yet.");
    return;
  }
  $("#replies").innerHTML = data.items.map((it) => `
    <article class="rq" data-id="${it.id}">
      <div class="rq-meta">
        <span class="score" title="Relevance">${it.relevance}</span>
        <span class="chip">${esc(it.topic || "")}</span><span>${esc(it.intent)}</span>
        <span>${esc(it.platform)} · ${esc(it.community)}${it.country ? ` · ${esc(it.country)}` : ""}</span>
        <span>${link(it.post_url, "view post")}</span>
      </div>
      <div class="rq-comment" dir="auto">${esc(it.comment)}</div>
      ${it.status === "pending" ? `
        <div class="small muted">Suggested replies (${esc(it.drafts_method)}), linking to the <strong>${esc(it.scorecard)}</strong> Scorecard:</div>
        <div class="rq-drafts">${it.drafts.map((d, i) => `
          <label><input type="radio" name="d-${it.id}" value="${i}" ${i === 0 ? "checked" : ""}><span dir="auto" style="white-space:pre-wrap">${esc(d)}</span></label>`).join("")}</div>
        <textarea dir="auto" aria-label="Reply to post">${esc(it.drafts[0] || "")}</textarea>
        <div class="rq-actions">
          <button data-act="copy">Copy &amp; open post</button>
          <button class="ghost" data-act="posted">Mark as posted</button>
          <button class="ghost" data-act="redraft">New suggestions</button>
          <button class="ghost" data-act="skipped">Skip</button>
        </div>` : `
        ${it.final_reply ? `<div class="small muted">Reply used:</div><div class="rq-comment" dir="auto" style="white-space:pre-wrap">${esc(it.final_reply)}</div>` : ""}
        <div class="rq-actions">
          ${it.status === "copied" ? '<button data-act="posted">Confirm posted</button>' : ""}
          <button class="ghost" data-act="pending">Move back to queue</button>
        </div>`}
      <div class="warn" aria-live="polite"></div>
    </article>`).join("");
}

$("#replies").addEventListener("change", (e) => {
  if (e.target.type !== "radio") return;
  const card = e.target.closest(".rq");
  const it = state.replies.find((x) => String(x.id) === card.dataset.id);
  card.querySelector("textarea").value = it.drafts[+e.target.value];
});

$("#replies").addEventListener("click", async (e) => {
  const act = e.target.dataset.act;
  if (!act) return;
  const card = e.target.closest(".rq");
  const id = card.dataset.id;
  const it = state.replies.find((x) => String(x.id) === id);
  const reply = card.querySelector("textarea")?.value;
  if (act === "redraft") {
    const r = await api(`/api/replies/${id}/redraft`, { method: "POST" });
    it.drafts = r.drafts; it.drafts_method = r.method;
    return loadReplies();
  }
  if (act === "copy") {
    // Open the tab synchronously (before any await) so pop-up blockers allow it.
    const win = window.open(safeUrl(it.open_url) || "about:blank", "_blank", "noopener");
    try { await navigator.clipboard.writeText(reply || ""); } catch { /* clipboard unavailable: text stays in the box */ }
    const r = await api(`/api/replies/${id}/status`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "copied", reply }) });
    card.querySelector(".warn").textContent = [
      win ? "Reply copied. Paste it under the comment in the post that just opened, then press “Mark as posted”." :
            "Reply copied. Open the post and paste it under the comment.", ...r.warnings].join(" ");
    return;
  }
  const r = await api(`/api/replies/${id}/status`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: act, reply: act === "posted" ? reply : undefined }) });
  if (r.warnings.length) alert(r.warnings.join("\n"));
  loadReplies();
});
$("#r-status").addEventListener("change", loadReplies);
$("#r-refresh").addEventListener("click", (e) => withBusy(e.target, async () => {
  const r = await api(`/api/replies/refresh?days=${$("#r-days").value}`, { method: "POST" });
  $("#r-msg").textContent = `${r.added} new question(s) added.`;
  loadReplies();
}));

// ------------------------------------------------------------------- leads
const SCORECARD_KEYS = ["energy", "sleep", "stress", "digestive", "pain", "lifestyle", "health360"];
async function loadLeads() {
  $("#sc-links").innerHTML = "Your Scorecard pages: " + SCORECARD_KEYS.map((k) =>
    `${link(`${META.public_base_url}/s/${k}?lang=ar`, k)} (<a href="/s/${k}?lang=en" target="_blank" rel="noopener">en</a>)`).join(" · ");
  if (!META.leads_enabled) {
    $("#leads").innerHTML = empty("Set ADMIN_PASSWORD (in .env) to protect the dashboard and view leads.");
    return;
  }
  const d = await api("/api/leads");
  $("#leads").innerHTML = `<p class="small muted">${fmt(d.completions)} Scorecards completed · ${fmt(d.leads.length)} opted in to contact</p>` + table([
    { label: "Name", render: (l) => txt(l.name || "—") },
    { label: "WhatsApp", render: (l) => `<span dir="ltr">${esc(l.whatsapp || "")}</span>` },
    { label: "Scorecard", render: (l) => esc(l.scorecard) },
    { label: "Score", num: true, render: (l) => `<span class="score">${l.total_score}</span>` },
    { label: "Lowest areas", render: (l) => chips(Object.entries(l.areas).sort((a, b) => a[1] - b[1]).slice(0, 2).map(([k, v]) => `${k} ${v}`)) },
    { label: "Came from", render: (l) => esc([l.source, l.campaign].filter(Boolean).join(" / ") || "direct") },
    { label: "Status", render: (l) => `<select data-lead="${l.id}">${["new", "contacted", "converted", "closed"].map((s) =>
        `<option ${s === l.status ? "selected" : ""}>${s}</option>`).join("")}</select>` },
    { label: "Date", render: (l) => esc((l.created_at || "").slice(0, 10)) },
    { label: "", render: (l) => `<button class="link" data-del-lead="${l.id}">delete</button>` },
  ], d.leads);
}
$("#leads").addEventListener("change", async (e) => {
  if (e.target.dataset.lead) await api(`/api/leads/${e.target.dataset.lead}/status`, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: e.target.value }) });
});
$("#leads").addEventListener("click", async (e) => {
  if (e.target.dataset.delLead && confirm("Delete this person's details and answers permanently?")) {
    await api(`/api/leads/${e.target.dataset.delLead}`, { method: "DELETE" });
    loadLeads();
  }
});

// ------------------------------------------------------------------ search
const EXAMPLES = ["fatigue Saudi Arabia", "sleep problems UAE", "burnout Riyadh", "gut health Dubai", "chronic pain Saudi"];
$("#search-examples").innerHTML = EXAMPLES.map((e) => `<button class="link" data-q="${esc(e)}">${esc(e)}</button>`).join(" · ");
$("#search-examples").addEventListener("click", (e) => { if (e.target.dataset.q) { $("#search-q").value = e.target.dataset.q; doSearch(); } });
$("#search-form").addEventListener("submit", (e) => { e.preventDefault(); doSearch(); });

async function doSearch() {
  const q = $("#search-q").value.trim();
  if (!q) return;
  const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
  const p = r.parsed;
  const months = [...new Set(Object.values(r.topic_trends).flatMap((m) => Object.keys(m)))].sort();
  const trendTable = months.length ? table(
    [{ label: "Topic", render: (row) => esc(row[0]) }, ...months.map((m) => ({ label: m, num: true, render: (row) => fmt(row[1][m] || 0) }))],
    Object.entries(r.topic_trends)) : empty("No dated discussions for a trend.");
  $("#search-results").innerHTML = `
    <p class="small muted">Interpreted as: topics ${esc(p.topics.join(", ") || "any")} · country ${esc(p.country || "any")} · city ${esc(p.city || "any")}${p.terms.length ? ` · text “${esc(p.terms.join(" "))}”` : ""}</p>
    ${r.note ? `<p class="small">${esc(r.note)}</p>` : ""}
    <div class="tiles"><div class="tile"><div class="v">${fmt(r.discussion_volume)}</div><div class="l">Relevant discussions</div></div>
      ${Object.entries(r.intents).slice(0, 3).map(([k, v]) => `<div class="tile"><div class="v">${fmt(v)}</div><div class="l">${esc(META.intents[k] || k)}</div></div>`).join("")}</div>
    <h3>Relevant communities</h3>
    ${table([{ label: "Community", render: (c) => link(c.url, c.name) }, { label: "Platform", render: (c) => esc(c.platform) },
             { label: "Country", render: (c) => esc(c.country || "—") }, { label: "Top topics", render: (c) => chips(c.top_topics) },
             { label: "Discussions", num: true, render: (c) => fmt(c.relevant_discussions) }], r.communities)}
    <h3>Relevant posts</h3>
    ${table([{ label: "Post", render: (x) => link(x.url, x.title || x.url) }, { label: "Community", render: (x) => esc(x.community) },
             { label: "Top topics", render: (x) => chips(x.top_topics) }, { label: "Discussions", num: true, render: (x) => fmt(x.relevant_discussions) }], r.posts)}
    <h3>Common questions</h3>
    ${r.common_questions.map((q) => `<div>• ${txt(q.question)} <span class="muted small">×${q.count}</span></div>`).join("") || empty("No questions found.")}
    <h3>Topic trend (relevant discussions per month)</h3>${trendTable}`;
}

// ------------------------------------------------------------------ ingest
function showOut(el, data) { el.hidden = false; el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2); }
async function withBusy(btn, fn) { btn.disabled = true; try { await fn(); } finally { btn.disabled = false; } }

$("#ingest-form").addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy(e.submitter, async () => {
    const body = {
      urls: $("#i-urls").value.split(/\s+/).filter(Boolean),
      keywords: $("#i-keywords").value.split(",").map((s) => s.trim()).filter(Boolean),
      country: $("#i-country").value || null, city: $("#i-city").value || null, platform: $("#i-platform").value || null,
      date_from: $("#i-from").value || null, date_to: $("#i-to").value || null, max_posts: +$("#i-maxposts").value || 20,
    };
    try { showOut($("#ingest-out"), await api("/api/ingest/urls", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })); }
    catch (err) { showOut($("#ingest-out"), String(err)); }
  });
});

$("#file-form").addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy(e.submitter, async () => {
    const fd = new FormData();
    fd.append("file", $("#file").files[0]);
    for (const [k, id] of [["platform", "#u-platform"], ["community_name", "#u-community"], ["country", "#u-country"], ["city", "#u-city"]]) {
      if ($(id).value) fd.append(k, $(id).value);
    }
    try { showOut($("#file-out"), await api("/api/ingest/file", { method: "POST", body: fd })); }
    catch (err) { showOut($("#file-out"), String(err)); }
  });
});

$("#reanalyze").addEventListener("click", (e) => withBusy(e.target, async () => {
  try { showOut($("#analyze-out"), await api("/api/analyze?reanalyze=true", { method: "POST" })); }
  catch (err) { showOut($("#analyze-out"), String(err)); }
}));

// --------------------------------------------------------------------- b2b
async function loadB2B() {
  const rows = await api("/api/business");
  $("#b2b").innerHTML = table([
    { label: "Business", render: (b) => esc(b.business_name) }, { label: "Category", render: (b) => esc(b.category || "") },
    { label: "Country", render: (b) => esc(b.country || "") }, { label: "Public email", render: (b) => esc(b.public_email || "") },
    { label: "Website", render: (b) => (b.website ? link(b.website.startsWith("http") ? b.website : `https://${b.website}`, b.website) : "") },
    { label: "Social", render: (b) => (b.social_profiles || []).map((u) => link(u)).join("<br>") },
    { label: "Relevance", num: true, render: (b) => fmt(b.partnership_relevance) },
    { label: "", render: (b) => `<button class="link" data-del="${b.id}">remove</button>` },
  ], rows);
}
$("#b2b").addEventListener("click", async (e) => {
  if (e.target.dataset.del && confirm("Remove this business?")) { await api(`/api/business/${e.target.dataset.del}`, { method: "DELETE" }); loadB2B(); }
});
$("#b2b-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/business", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    business_name: $("#b-name").value, category: $("#b-category").value || null, country: $("#b-country").value || null,
    public_email: $("#b-email").value || null, website: $("#b-website").value || null,
    social_profiles: $("#b-social").value.split("|").map((s) => s.trim()).filter(Boolean),
    partnership_relevance: $("#b-rel").value ? +$("#b-rel").value : null,
  }) });
  e.target.reset(); loadB2B();
});

// ------------------------------------------------------------- navigation
const LOADERS = { overview: loadOverview, communities: loadCommunities, posts: loadPosts, comments: loadComments,
  scorecards: loadScorecards, content: loadContent, b2b: loadB2B, replies: loadReplies, leads: loadLeads };

function activate(tab) {
  state.tab = tab;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${tab}`));
  Promise.resolve(LOADERS[tab]?.()).catch((err) => console.error(err));
}
document.querySelector(".tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) activate(e.target.dataset.tab); });
["#f-country", "#f-platform"].forEach((id) => $(id).addEventListener("change", () => activate(state.tab)));

async function init() {
  META = await api("/api/meta");
  const countryOpts = Object.entries(META.countries).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  const platformOpts = META.platforms.map((p) => `<option value="${p}">${esc(p)}</option>`).join("");
  for (const id of ["#f-country", "#i-country", "#u-country", "#b-country"]) $(id).insertAdjacentHTML("beforeend", countryOpts);
  for (const id of ["#f-platform", "#i-platform", "#u-platform"]) $(id).insertAdjacentHTML("beforeend", platformOpts);
  $("#c-intent").insertAdjacentHTML("beforeend", Object.entries(META.intents).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join(""));
  const topics = await api("/api/topics");
  $("#c-topic").insertAdjacentHTML("beforeend", topics.map((t) => `<option value="${t.id}">${esc(t.name)}${t.seed ? "" : " (discovered)"}</option>`).join(""));
  $("#llm-badge").textContent = `AI: ${META.llm_provider}`;
  activate("overview");
}
init().catch((err) => { document.querySelector("main").insertAdjacentHTML("afterbegin", `<div class="card">Failed to load: ${esc(err)}</div>`); });
