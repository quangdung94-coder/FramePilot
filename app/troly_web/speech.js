/* speech.js - BƯỚC 4 · LỜI NÓI, tầng 1: bản đồ (ADR-0014). Chỉ vẽ và nhận thao tác; chép lời, kho dữ liệu, In/Out gợi ý ở
   Python (troly_api.speech_*). Dùng chung $, api, S, esc, status, setState, page từ app.js. Chữ chép lời chỉ hiện trên màn hình. */
"use strict";

const LN = { rows: [], all: [], summary: null, info: null, sel: null, stage: "all", onlyKey: false, min20: false, find: "",
  detail: null, edit: null, run: null, lastRefresh: 0, timer: null };
const mmss = (s) => Math.floor((s || 0) / 60) + ":" + String(Math.round((s || 0) % 60)).padStart(2, "0");
const pad2 = (n) => String(n).padStart(2, "0");

/* timecode "HH:MM:SS:FF" + giây -> "HH:MM:SS:FF" (giống troly_speech_store.add_timecode) */
function addTc(tc, sec, fps) {
  const m = /^\s*(\d+):(\d+):(\d+)[:;.](\d+)\s*$/.exec(tc || "");
  if (!m || !fps) return "--:--:--:--";
  const fr = Math.round(fps);
  let t = ((+m[1] * 60 + +m[2]) * 60 + +m[3]) * fr + +m[4] + Math.round(sec * fr);
  const f = t % fr; t = Math.floor(t / fr);
  return pad2(Math.floor(t / 3600) % 24) + ":" + pad2(Math.floor(t / 60) % 60) + ":" + pad2(t % 60) + ":" + pad2(f);
}
const stageOf = (r) => (r.stage === null || r.stage === undefined ? -1 : r.stage);
const inStage = (r) => LN.stage === "all" || stageOf(r) === +LN.stage;

/* ------------------------------------------------------------------ nạp dữ liệu */
async function lnRefresh() {
  if (!window.pywebview || !window.pywebview.api) return;
  LN.lastRefresh = Date.now();
  LN.info = await api().speech_info();
  const d = await api().speech_clips(LN.onlyKey, LN.min20 ? 20 : 0, LN.find);
  LN.rows = d.rows || []; LN.all = d.all || []; LN.summary = d.summary;
  const cur = LN.rows.find((r) => r.uid === LN.sel);
  if (!cur || !inStage(cur)) {
    const first = LN.rows.find(inStage);
    if (first) { LN.sel = first.uid; LN.detail = null; LN.edit = null; } else { LN.sel = null; LN.detail = null; }
  }
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
}

async function lnLoadDetail(uid) {
  const d = await api().speech_detail(uid);
  if (LN.sel !== uid) return;
  LN.detail = d;
  renderRight();
}

function lnSelect(uid) {
  LN.sel = uid; LN.detail = null; LN.edit = null;
  renderRows(); renderRight(); lnLoadDetail(uid);
}

/* ------------------------------------------------------------------ vẽ */
function barHtml(r, big) {
  const dur = r.dur || 1;
  const segs = (r.segs || []).map(([a, b, c]) => `<i class="${c}" style="left:${(a / dur * 100).toFixed(2)}%;width:${Math.max(0.6, (b - a) / dur * 100).toFixed(2)}%"></i>`).join("");
  const sp = r.span;
  const box = sp && !big ? `<b class="box" style="left:${(sp.in_s / dur * 100).toFixed(2)}%;width:${((sp.out_s - sp.in_s) / dur * 100).toFixed(2)}%"></b>` : "";
  return segs + box;
}

function renderSpeech() {
  const stages = S ? S.stages : [];
  const sel = $("lnStage");
  const opts = ['<option value="all">Cả project</option>'].concat(stages.map((s, i) => `<option value="${i}">${esc(s.name)} · ${esc(s.range || "")}</option>`));
  if (S && S.outside) opts.push('<option value="-1">Ngoài mọi giai đoạn</option>');
  const html = opts.join("");
  if (sel.dataset.sig !== html) { sel.innerHTML = html; sel.dataset.sig = html; }
  sel.value = String(LN.stage);
  const st = stages[+LN.stage];
  $("lnTitle").textContent = LN.stage === "all" ? "Lời nói · Cả project" : (st ? `Lời nói · ${st.name} · ${st.range || ""}` : "Lời nói · Ngoài mọi giai đoạn");
  $("lnKey").setAttribute("aria-pressed", LN.onlyKey); $("lnMin").setAttribute("aria-pressed", LN.min20);
  renderSummary(); renderStore(); renderRows(); renderRight();
}

function renderSummary() {
  const c = LN.summary, run = LN.run;
  let t;
  if (!c || (!c.total && !run)) t = "Chưa chép lời. Chọn thư mục kho rồi bấm “Chép lời cả bin”.";
  else {
    t = `Cả project: ${c.speech} clip có tiếng, đã chép ${c.done}, lỗi ${c.err}, ${c.suspect} clip có thể sai. Chữ lưu trong một kho trên máy.`;
    const n = S ? S.n : 0;
    if (n > c.total) t += ` Còn ${n - c.total} clip chưa chép.`;
  }
  if (run) t = `Đang chép lời: ${run.n}/${run.total} clip. ` + t;
  $("lnSummary").textContent = t;
  $("lnRun").textContent = LN.info && LN.info.running ? "Dừng chép lời" : "Chép lời cả bin";
}

function renderStore() {
  const i = LN.info || {};
  $("lnStore").innerHTML = `<span class="nw">Kho lời nói:</span><b style="color:var(--dim2)" title="${esc(i.dir || "")}">${esc(i.dir || "chưa chọn")}</b>
    <button class="btn-link" id="lnPick">Chọn thư mục…</button><span class="nw">· Ngôn ngữ mặc định</span>
    <select id="lnLang" class="sel" style="height:28px;font-size:12px"><option value="vi"${i.lang !== "en" ? " selected" : ""}>Tiếng Việt</option><option value="en"${i.lang === "en" ? " selected" : ""}>English</option></select>`;
  $("lnPick").onclick = lnPick;
  $("lnLang").onchange = async (e) => {
    if (i.dir) await api().speech_set_dir(i.dir, e.target.value); else status("Hãy chọn thư mục kho trước.", "warn");
    lnRefresh();
  };
}

function renderRows() {
  const rows = LN.rows.filter(inStage);
  const total = LN.all.filter(inStage).length;
  $("lnCount").textContent = `Hiện ${rows.length} / ${total} clip`;
  const box = $("lnRows");
  if (!rows.length) {
    box.innerHTML = `<div class="empty">${total ? "Không có clip nào khớp bộ lọc." : "Chưa có clip nào trong giai đoạn này được chép lời."}</div>`;
    return;
  }
  box.innerHTML = rows.map((r) => {
    const hl = r.silent ? '<span class="ln-text none">Không có tiếng nói</span>'
      : `${r.suspect ? '<span class="ln-flag">có thể sai</span>' : ""}<span class="ln-text${r.headline ? (r.n_keys ? "" : " dim") : " none"}">${esc(r.headline || "Có tiếng nhưng chưa ra chữ")}</span>`;
    return `<button class="ln-row${r.uid === LN.sel ? " on" : ""}" data-uid="${esc(r.uid)}">
      <span class="ln-id"><b${r.star ? ' class="star"' : ""}>${esc(r.name)}</b><span>${esc(r.time || "--:--:--")} · ${mmss(r.dur)} · nói ${Math.round(r.spoken_s)}s</span></span>
      <span class="ln-bar">${barHtml(r, false)}</span>
      <span class="ln-hl">${hl}</span>
      <span class="ln-k${r.n_keys ? "" : " zero"}">${r.n_keys || "·"}</span>
      <span class="ln-lang">${r.silent ? "–" : esc(r.lang || "–")}</span></button>`;
  }).join("");
}

function curRow() { return LN.rows.find((r) => r.uid === LN.sel) || null; }
function editSpan() {
  if (LN.edit) return LN.edit;
  const d = LN.detail, r = curRow();
  const sp = (d && d.span) || (r && r.span);
  return sp ? { in_s: sp.in_s, out_s: sp.out_s, src: sp.src, dirty: false } : null;
}

function renderRight() {
  const r = curRow(), d = LN.detail;
  if (!r) {
    $("lnName").textContent = "Chọn một clip"; $("lnMeta").textContent = ""; $("lnBar").innerHTML = ""; $("lnDurEnd").textContent = "";
    $("lnSugg").classList.add("hidden"); $("lnLines").innerHTML = ""; return;
  }
  const fps = (d && d.fps) || r.fps || 25;
  $("lnName").textContent = r.name;
  $("lnMeta").innerHTML = `${esc(r.time || "--:--:--")} · ${mmss(r.dur)} · <button class="btn-link ln-lang" id="lnLangBtn" title="Bấm để đổi ngôn ngữ của clip này (vi ⇄ en); lần chép lại sẽ giữ lựa chọn của anh">${esc(r.silent ? "–" : (r.lang || "–"))}</button>`;
  $("lnLangBtn").onclick = async () => { if (r.silent) return; await api().speech_set_lang(r.key, r.lang === "en" ? "vi" : "en"); lnRefresh(); };
  $("lnDurEnd").textContent = mmss(r.dur);
  const e = editSpan(), dur = r.dur || 1;
  let bar = barHtml(r, true);
  if (e) {
    const l = e.in_s / dur * 100, w = (e.out_s - e.in_s) / dur * 100;
    bar += `<b class="box" style="left:${l.toFixed(2)}%;width:${w.toFixed(2)}%"></b>
      <span class="h" data-h="in" style="left:${l.toFixed(2)}%"></span><span class="h" data-h="out" style="left:${(l + w).toFixed(2)}%"></span>`;
  }
  $("lnBar").innerHTML = bar;
  const sg = $("lnSugg");
  sg.classList.toggle("hidden", !e);
  if (e) {
    const tc = (d && d.tc) || r.tc;
    $("lnIn").textContent = "In " + addTc(tc, e.in_s, fps); $("lnOut").textContent = "Out " + addTc(tc, e.out_s, fps);
    $("lnHold").textContent = "Giữ " + Math.round(e.out_s - e.in_s) + " giây";
    $("lnSuggTitle").textContent = { manual: "Đoạn anh đã đặt (lưu trong panel, chưa ghi vào DaVinci)", davinci: "Đoạn đã đặt In / Out trong DaVinci, giờ theo timecode của file gốc" }[e.src] || "Đoạn gợi ý, giờ theo timecode của file gốc";
    $("lnSuggNote").textContent = e.dirty ? "Đã kéo mép khung. Bấm “Đặt In / Out” để lưu vào kế hoạch của panel." : "Kéo mép khung trắng để chỉnh. Anh đặt tay thì lấy theo anh.";
  }
  const lines = (d && d.lines) || [];
  $("lnLines").innerHTML = !d ? '<span class="dim13" style="padding:8px">Đang tải...</span>'
    : lines.length ? lines.map((l) => {
      const inside = e && l.t0 >= e.in_s - 0.01 && l.t1 <= e.out_s + 0.01;
      return `<div class="ln-line${l.keys.length && !l.why.length ? " key" : ""}${inside ? " in" : ""}${l.why.length ? " bad" : ""}"><span class="t">${fmtSec(l.t0)}</span><span class="x">${esc(l.text)}${l.why.length ? " · nghi sai" : ""}</span></div>`;
    }).join("")
    : `<span class="dim13" style="padding:8px">${r.silent ? "Clip này không có tiếng nói, chỉ có tiếng nền." : "Có tiếng nói nhưng Whisper không ra chữ."}</span>`;
  $("lnStar").textContent = ((d ? d.star : r.star) ? "Bỏ sao (J)" : "Gắn sao (J)");
}

/* ------------------------------------------------------------------ thao tác */
async function lnPick() {
  const r = await api().speech_pick_dir();
  if (r && r.error) status(r.error, "warn");
  else if (r && r.ok) status("Đã chọn thư mục kho lời nói.", "ok");
  await lnRefresh();
}

$("lnRun").onclick = async () => {
  if (LN.info && LN.info.running) { await api().speech_stop(); status("Đang dừng sau nhóm clip hiện tại...", "info"); return; }
  if (!LN.info || !LN.info.dir) { await lnPick(); if (!LN.info || !LN.info.dir) return; }
  if (!S || !S.n) return status("Chưa có clip. Hãy sang bước 1 và bấm “Đọc clip” trước.", "warn");
  const r = await api().speech_start();
  if (r && r.error) return status(r.error, "warn");
  LN.run = { n: 0, total: r.count };
  status(`Bắt đầu chép lời ${r.count} clip (clip đã chép và file không đổi sẽ được bỏ qua).`, "info");
  lnRefresh();
};
$("lnStage").onchange = (e) => {
  LN.stage = e.target.value;
  const f = LN.rows.find(inStage);
  LN.sel = f ? f.uid : null; LN.detail = null; LN.edit = null;
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
};
$("lnKey").onclick = () => { LN.onlyKey = !LN.onlyKey; lnRefresh(); };
$("lnMin").onclick = () => { LN.min20 = !LN.min20; lnRefresh(); };
$("lnFind").oninput = (e) => { clearTimeout(LN.timer); LN.find = e.target.value; LN.timer = setTimeout(lnRefresh, 250); };
$("lnRows").onclick = (e) => { const b = e.target.closest(".ln-row"); if (b) lnSelect(b.dataset.uid); };

async function lnToggleStar() {
  const r = curRow(); if (!r) return;
  const was = (LN.detail ? LN.detail.star : r.star);
  setState(await api().toggle_star([r.uid]));
  await lnRefresh();
  status(was ? "Đã bỏ sao của clip." : "Đã gắn sao ★ cho clip.", "ok");
}
$("lnStar").onclick = lnToggleStar;

$("lnSet").onclick = async () => {
  const r = curRow(), e = editSpan();
  if (!r || !e) return status("Clip này chưa có đoạn gợi ý để đặt.", "warn");
  await api().speech_set_inout(r.uid, e.in_s, e.out_s);
  status("Đã lưu In / Out vào kế hoạch của panel (chưa ghi vào DaVinci).", "ok");
  LN.edit = null;
  await lnRefresh();
};

/* kéo mép khung trắng ở thanh lớn */
$("lnBar").addEventListener("mousedown", (ev) => {
  const h = ev.target.closest(".h"); const r = curRow(); if (!h || !r) return;
  ev.preventDefault();
  const rect = $("lnBar").getBoundingClientRect(), dur = r.dur || 1;
  const e0 = editSpan(); const which = h.dataset.h;
  const move = (m) => {
    const t = Math.min(dur, Math.max(0, (m.clientX - rect.left) / rect.width * dur));
    const cur = LN.edit || { ...e0 };
    if (which === "in") cur.in_s = Math.min(t, cur.out_s - 0.5); else cur.out_s = Math.max(t, cur.in_s + 0.5);
    cur.in_s = Math.round(cur.in_s * 100) / 100; cur.out_s = Math.round(cur.out_s * 100) / 100; cur.dirty = true; cur.src = "manual";
    LN.edit = cur; renderRight();
  };
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
});

function lnKey(e) {
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.code === "KeyJ" && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) { e.preventDefault(); lnToggleStar(); return; }
  const dir = { ArrowUp: -1, ArrowDown: 1 }[e.key];
  if (!dir) return;
  e.preventDefault();
  const rows = LN.rows.filter(inStage), i = rows.findIndex((r) => r.uid === LN.sel);
  const n = rows[Math.min(rows.length - 1, Math.max(0, i + dir))];
  if (n) { lnSelect(n.uid); const el = document.querySelector(`.ln-row[data-uid="${CSS.escape(n.uid)}"]`); if (el) el.scrollIntoView({ block: "nearest" }); }
}

/* sự kiện từ luồng chép lời */
function lnProgress(d) {
  LN.run = d;
  status(`Chép lời ${d.n}/${d.total} clip...`, "info");
  $("progBar").style.width = (d.n / Math.max(1, d.total) * 100) + "%";
  if (page === 4 && Date.now() - LN.lastRefresh > 5000) lnRefresh(); else renderSummary();
}
function lnDone(s) {
  LN.run = null;
  const msg = s.ok && !s.stopped
    ? `Chép lời xong: ${s.done} đã chép, ${s.silent} im lặng, ${s.errors} lỗi, ${s.suspect} có thể sai. ${s.message}`
    : (s.message || "Chép lời dừng.");
  status(msg, s.ok ? "ok" : "error");
  lnRefresh();
}
