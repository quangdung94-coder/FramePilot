/* app.js - giao diện HTML của Trợ lý File Quay (ADR-0010). Chỉ vẽ và nhận thao tác; mọi chức năng gọi Python qua
   window.pywebview.api (src/troly_api.py). Python gửi việc nền về qua hàm toàn cục onEvent(loại, dữ liệu). */
"use strict";

let S = null;                      // trạng thái do Python trả về (api.state())
let INFO = { parsed: { name: "", date: "" } };
let page = 1;
let view = [6 * 60, 22 * 60];      // khoảng giờ đang xem trên thanh thời gian (phút)
let fitted = false;
let editIdx = null;                // giai đoạn đang mở form sửa (bước 1)
let gStage = null;                 // giai đoạn đang XEM ở bước 2; -1 = ngoài mọi giai đoạn
let gSub = null;                   // bin con đang xem: null = cả giai đoạn, tên bin, hoặc NONE = chỉ clip chưa xếp
const NONE = "\u0000chua-xep";     // BẤM bin trong cây chỉ đổi chỗ xem này, không bao giờ đổi nhãn/giai đoạn của clip
let items = [], sel = new Set(), cur = 0, anchor = 0;
let keepCur = null, poolOpen = null, dragging = false;
let keepView = false;              // mở lại panel: giữ thu phóng thanh giờ đã lưu, không tự "Xem hết"
let uiTimer = null;
/* TRẠNG THÁI LÀM VIỆC lưu theo project (Api.save_ui): bước đang ở, giai đoạn/bin con đang xem, thu phóng thanh giờ, ô lọc.
   Nhãn, mốc giờ, chọn tay, bin nguồn đã được Python lưu ngay mỗi khi đổi. */
function saveUi() {
  clearTimeout(uiTimer);
  uiTimer = setTimeout(() => {
    try {
      api().save_ui({ page, view, gStage, gSub: gSub === NONE ? "__none__" : gSub, onlyNew: $("onlyNew").checked });
    } catch (e) { /* cửa sổ đang đóng */ }
  }, 400);
}
function applyUi(ui) {
  if (!ui) return;
  if ([1, 2, 3, 4, 5].includes(ui.page)) page = ui.page;
  if (Array.isArray(ui.view) && ui.view.length === 2 && ui.view[1] > ui.view[0]) { view = ui.view.slice(); keepView = true; }
  if (typeof ui.gStage === "number") gStage = ui.gStage;
  if (ui.gSub !== undefined && ui.gSub !== null) gSub = ui.gSub === "__none__" ? NONE : ui.gSub;
  $("onlyNew").checked = !!ui.onlyNew;
}     // giữ con trỏ sau khi chuyển clip; bin mở khi kéo tới
const thumbs = {}, bigs = {}, notes = {};
const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const FOLDER = '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>';
const folder = (c, s) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${FOLDER}</svg>`;

function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmt(m) {
  m = Math.round(m); const d = Math.floor(m / 1440), r = ((m % 1440) + 1440) % 1440;
  return String(Math.floor(r / 60)).padStart(2, "0") + ":" + String(r % 60).padStart(2, "0") + (d > 0 ? " (+" + d + ")" : "");
}
function parseHM(t, ref) {
  const m = String(t).trim().match(/^(\d{1,2})[:hH.]?(\d{2})$/);
  if (!m || +m[1] > 23 || +m[2] > 59) return null;
  return (ref || 0) * 1440 + (+m[1]) * 60 + (+m[2]);
}
function durTxt(s) { s = Math.round(s || 0); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }
function fmtSec(s) {
  if (s == null) return "--:--:--";
  s = Math.max(0, s);
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
}

/* ------------------------------------------------------------------ trạng thái, sự kiện từ Python */
function status(text, kind) {
  $("statusText").textContent = text;
  $("status").className = "status " + (kind || "");
  if (kind !== "info") $("progBar").style.width = "0";
}
window.onEvent = function (kind, data) {
  if (kind === "bins") {
    const s = $("binSel");
    s.innerHTML = data.bins.map((b) => `<option value="${esc(b.path)}"${b.path === data.pick ? " selected" : ""}>${esc(b.path)}  (${b.n})</option>`).join("");
    BINS = data.bins; if (page === 1) renderTree();
  } else if (kind === "timelines") {
    $("tlSel").innerHTML = `<option value="">Timeline: giờ trong file</option>` + data.names.map((n) => `<option value="${esc(n)}"${n === data.pick ? " selected" : ""}>${esc(n)}</option>`).join("");
  } else if (kind === "speech_progress") lnProgress(data);
  else if (kind === "speech_done") lnDone(data);
  else if (kind.indexOf("analyze_") === 0) anEvent(kind, data);
  else if (kind === "dur_timeline_done") { if (page === 5) renderPage5(); }
  else if (kind.indexOf("inout_sug_") === 0) p3SugEvent(kind, data);
  else if (kind === "state") setState(data);
  else if (kind === "status") status(data.text, data.kind);
  else if (kind === "progress") { status(data.text, "info"); $("progBar").style.width = (data.frac * 100) + "%"; }
  else if (kind === "thumb") {
    if (data.src) thumbs[data.uid] = data.src;
    notes[data.uid] = data.note;
    $("thumbText").textContent = `Thumbnail ${data.done}/${data.n}` + (data.bad ? `, ${data.bad} lỗi` : "");
    const img = document.querySelector(`.card[data-uid="${CSS.escape(data.uid)}"] .thumb`);
    if (img && data.src) setThumb(img, data.src);
    const t1 = data.src ? document.querySelector(`#g1 .tile[data-uid="${CSS.escape(data.uid)}"] .th`) : null; if (t1) setThumb(t1, data.src);
    if (items[cur] && items[cur].uid === data.uid) showCur();
  }
};

function setState(st) {
  if (!st || st.error) { if (st && st.error) status(st.error, "warn"); return; }
  const firstLoad = !S || S.n !== st.n;
  S = st;
  if (firstLoad || !fitted) {
    if (keepView && st.n) { keepView = false; fitted = true; } else fitView();     // giữ thu phóng đã lưu khi mở lại
  }
  if (gStage === null || gStage >= S.stages.length || (gStage === -1 && !S.outside)) { gStage = S.stages.length ? 0 : null; gSub = null; }
  render(firstLoad);
}

/* ------------------------------------------------------------------ vẽ chung */
function render(rebuildItems) {
  const p = INFO.parsed || {};
  const parts = [p.team ? p.team + " · " + p.name : p.name || INFO.project].filter(Boolean);
  if (S && S.src && S.src.n_machines) parts.push(S.src.n_machines + " máy");      // như demo: "Lora · Phuong&Tung · 3 máy"
  else { if (p.date) parts.push(p.date); if (S) parts.push(S.n + " file"); }
  $("sub").textContent = parts.join(" · ");
  document.querySelectorAll(".step").forEach((a) => {
    const n = +a.dataset.page;
    a.className = "step" + (n === page ? " on" : "");
  });
  $("right1").classList.toggle("hidden", page !== 1);
  $("right2").classList.toggle("hidden", page !== 2 && page !== 3 && page !== 5);          // Bước 5 cũng cần ô Kiểu quay (Truyền thống chỉ bỏ nguyên clip)
  $("right4").classList.toggle("hidden", page !== 4);
  $("page1").classList.toggle("hidden", page !== 1);
  $("page2").classList.toggle("hidden", page !== 2);
  $("page3").classList.toggle("hidden", page !== 3);
  placeStage();
  $("page4").classList.toggle("hidden", page !== 4);
  $("page5").classList.toggle("hidden", page !== 5);
  const hasMoves = S && S.moves.length;
  $("undoBtn1").classList.add("hidden");
  $("undoBtn2").classList.add("hidden");
  if (S && $("styleSel").value !== (S.shoot_style || "") && document.activeElement !== $("styleSel")) $("styleSel").value = S.shoot_style || "";
  if (S) {
    $("tplSel").innerHTML = `<option value=""${S.template ? "" : " selected"}>Chọn mẫu sự kiện…</option>` + S.templates.map((t) => `<option${t === S.template ? " selected" : ""}>${esc(t)}</option>`).join("");
  }
  renderPage1();
  renderPage2(rebuildItems);
  if (page === 3) renderPage3();
  if (page === 4) lnRefresh();
}

/* ------------------------------------------------------------------ BƯỚC 1 */
function localAssign() {
  // giống troly_core.stage_of: giai đoạn sau thắng khi chạm nhau
  const cnt = S.stages.map(() => 0); let outside = 0;
  for (const c of S.clips) {
    let hit = null;
    if (c.manual && c.stage !== null && c.stage < S.stages.length) { cnt[c.stage]++; continue; }   // chọn tay thắng giờ
    if (c.m0 != null) S.stages.forEach((s, i) => { if ((s.start <= c.m0 && c.m0 < s.end) || (s.start === s.end && s.end === c.m0)) hit = i; });
    c.stage = hit;
    if (hit === null) outside++; else cnt[hit]++;
  }
  S.stages.forEach((s, i) => { s.count = cnt[i]; s.range = fmtA(s.start) + " – " + fmtA(s.end); });
  S.outside = outside;
}

/* Bước 1: chọn mốc giai đoạn bằng thumbnail (ADR-0033, theo design/trang1_chon_moc).
   Bấm một clip, bấm F1..F9 = mốc ĐẦU của giai đoạn n, Shift+F1..F9 = mốc CUỐI. Trục: timeline DaVinci (H:MM:SS) hoặc giờ trong file (HH:MM). */
let selUid = null, mFilter = "all", BINS = [], scrollSel = false;
function axisTl() { return !!(S && S.src && S.src.axis === "timeline"); }
function fmtA(m) {
  if (!axisTl()) return fmt(m);
  const s = Math.round(m * 60), a = Math.abs(s);
  return (s < 0 ? "-" : "") + Math.floor(a / 3600) + ":" + String(Math.floor(a % 3600 / 60)).padStart(2, "0") + ":" + String(a % 60).padStart(2, "0");
}
function parseAx(t) {
  const x = String(t).trim();
  if (axisTl()) {
    const m = x.match(/^(\d{1,3}):(\d{2})(?::(\d{2}))?$/);
    return m && +m[2] < 60 && (m[3] === undefined || +m[3] < 60) ? (+m[1]) * 60 + (+m[2]) + (m[3] ? (+m[3]) / 60 : 0) : null;
  }
  return parseHM(x, Math.floor(view[0] / 1440));
}
function fitView() {
  if (!S || !S.clips.length) return;
  const ms = [];
  S.clips.forEach((c) => { if (c.m0 != null) ms.push(c.m0, c.m1); });
  if (!ms.length) return;
  const a = Math.min(...ms), b = Math.max(...ms);
  if (axisTl()) { const pad = Math.max(1, (b - a) * 0.02); view = [Math.max(0, a - pad), b + pad]; }
  else view = [Math.floor((a - 15) / 60) * 60, Math.ceil((b + 15) / 60) * 60];
  fitted = true;
}
function pct(m) { return ((m - view[0]) / (view[1] - view[0]) * 100).toFixed(3) + "%"; }
const clip1 = (uid) => (S ? S.clips.find((c) => c.uid === uid) : null);
const machOf = (l) => (S && S.machines.find((m) => m.letter === l)) || null;
const chip = (l) => { const m = machOf(l); return l ? `<span class="cam-chip" style="--c:${m ? m.color : "#888"}" title="${esc(m ? m.name : "Máy " + l)}">${esc(l)}</span>` : ""; };
function marksOf(uid) {
  const out = [];
  if (S) S.stages.forEach((s, i) => { if (s.head && !s.head.auto && s.head.uid === uid) out.push({ i, t: "đầu" }); if (s.tail && !s.tail.auto && s.tail.uid === uid) out.push({ i, t: "cuối" }); });
  return out;
}
function list1() {
  if (!S) return [];
  return S.clips.filter((c) => c.m0 != null && (mFilter === "all" || c.mk === mFilter)).sort((a, b) => a.m0 - b.m0 || (a.name < b.name ? -1 : 1));
}

function renderPage1() {
  const st = S ? S.stages : [];
  $("stageCount").textContent = st.length ? st.length + " giai đoạn" : "";
  renderStageList(); renderSrcNote(); renderTimeline(); renderTree(); renderGrid1(); renderMeta(); renderKeys();
  $("applyBtn1").classList.toggle("hidden", !(S && S.n));
  $("clearManual").classList.toggle("hidden", !(S && S.n_manual));
}

function stageCard(s, i) {
  const mk = (what, h, label) => `<div class="mk${h ? (h.auto ? " auto" : "") : " none"}"><span class="kb">${label}</span><span>${what}</span><span class="nm" title="${h && h.auto ? "Tự suy ra từ khoảng giờ; bấm clip rồi F để đặt mốc" : ""}">${h ? esc(h.name) + (h.auto ? " (tự động)" : "") : "chưa chọn"}</span></div>`;
  const chipHtml = s.incomplete ? `<span class="chip" style="color:#E0A030">thiếu mốc</span>` : `<span class="chip">${s.count} file</span>`;
  const subRows = (s.bins || []).map((b) => `<div class="p1-sub"><span class="sq" style="background:${b.color}"></span><span class="t">${esc(b.name)}</span>${b.key ? `<span class="k">${b.key}</span>` : ""}</div>`).join("");
  const editRows = (s.bins || []).filter((b) => b.name !== "Khác").map((b) => `<div class="p1-bin-row"><input class="inp" data-bin-inp="1" value="${esc(b.name)}"><button type="button" class="p1-bin-del" data-act="del-bin" title="Xóa bin con">×</button></div>`).join("");
  return `<div class="stage p1${editIdx === i ? " open" : ""}" data-i="${i}">
    <div class="stage-row"><div class="stage-bar" style="background:${s.color}"></div><div class="stage-txt">
      <div class="inline8" style="justify-content:space-between"><span class="stage-name" title="Bấm đúp để đổi tên giai đoạn">${esc(s.name)}</span>${chipHtml}</div>
      <span class="dim12">${esc(s.range)}</span>
      <div class="lines">${mk("đầu", s.head, "F" + (i + 1))}${mk("cuối", s.tail, "⇧F" + (i + 1))}</div>
      ${editIdx !== i && subRows ? `<div class="p1-subs">${subRows}</div>` : ""}</div></div>
    ${editIdx === i ? `<div class="stage-edit">
      <label class="full">Tên giai đoạn<input class="inp" data-f="name" value="${esc(s.name)}"></label>
      <div class="full"><span class="lbl">Bin con (phím 1–9 theo thứ tự)</span>
        <div class="p1-bin-rows">${editRows}</div>
        <button type="button" class="btn-link" data-act="add-bin" style="margin-top:4px;font-size:12px">+ Thêm bin con</button>
      </div>
      <div class="row-end"><button class="btn-del" data-act="del">Xóa giai đoạn</button><button class="btn" data-act="save" style="height:32px">Lưu</button></div>
    </div>` : ""}</div>`;
}
function renderStageList() {
  $("stageList").innerHTML = S && S.stages.length ? S.stages.map(stageCard).join("")
    : `<div class="empty">${S && S.n ? "Chưa có giai đoạn. Bấm “+ Thêm giai đoạn” hoặc chọn mẫu rồi Gợi ý lại." : 'Bấm "Đọc clip" để đọc clip.'}</div>`;
}

/* nguồn dữ liệu: chỉ hiện khi có cảnh báo (bỏ chú thích dài mặc định) */
function renderSrcNote() {
  const el = $("srcNote");
  if (!S || !S.n) { el.innerHTML = ""; el.classList.add("hidden"); return; }
  const src = S.src;
  let h = "";
  if (src.timeline && !src.synced) h += `<span class="src-line warn">${esc(src.timeline)}: ${esc(src.note || "Chưa sync, đang dùng giờ trong file")}</span>`;
  if (src.n_missing) h += `<span class="src-line warn">${src.n_missing} clip chưa nằm trong timeline</span>`;
  if (src.n_extra) h += `<span class="src-line warn">${src.n_extra} clip trên timeline không có trong bin nguồn</span>`;
  el.innerHTML = h;
  el.classList.toggle("hidden", !h);
  $("vertCams").checked = !!src.vertical;
}
$("vertCams").addEventListener("change", (e) => api().set_vertical(e.target.checked).then(setState));

/* thanh thời gian thấp: thước, mỗi máy một hàng, khối giai đoạn */
function renderTimeline() {
  const W = $("bands").clientWidth || 800, span = view[1] - view[0];
  const step = [1, 2, 5, 10, 15, 30, 60, 120, 180, 240, 360, 720].find((s) => s / span * W >= 70) || 1440;
  let h = "";
  for (let t = Math.ceil(view[0] / step) * step; t <= view[1]; t += step) h += `<span style="left:${((t - view[0]) / span * 100).toFixed(3)}%">${fmtA(t)}</span>`;
  $("ruler").innerHTML = h;
  const mach = S && S.machines.length ? S.machines : [{ letter: "", color: "#4FC1A6", name: "" }];
  let d = "";
  mach.forEach((m) => {
    d += `<div class="dens-row" style="--c:${m.color}">${m.letter ? chip(m.letter).replace('class="cam-chip"', 'class="lab cam-chip"') : ""}`;
    if (S) for (const c of S.clips) {
      if (c.m0 == null || c.m0 < view[0] || c.m0 > view[1] || c.mk !== m.letter) continue;
      d += `<i style="left:${pct(c.m0)}"></i>`;
    }
    d += `</div>`;
  });
  const sc = selUid ? clip1(selUid) : null;
  if (sc && sc.m0 != null) d += `<div class="sel-mark" style="left:${pct(sc.m0)}" title="Clip đang chọn"></div>`;
  $("density").innerHTML = d;
  let b = "";
  if (S) S.stages.forEach((s) => {
    let a, e, partial = false;
    if (s.marks) { if (s.pa == null) return; a = s.pa; e = s.incomplete ? a + Math.max(span * 0.07, 1) : s.end; partial = !!s.incomplete; }
    else { if (!(s.start >= 0 && s.end > s.start)) return; a = s.start; e = s.end; }
    if (e <= view[0] || a >= view[1]) return;
    const x0 = Math.max(a, view[0]), x1 = Math.min(e, view[1]);
    b += `<div class="band${partial ? " dash" : ""}" title="${esc(s.name)}  ${esc(s.range)}" style="left:${pct(x0)};width:${((x1 - x0) / span * 100).toFixed(3)}%;border-color:${s.color};background:${s.color}22">` +
      `<i class="h l" style="background:${s.color}"></i><span class="n" style="color:${s.color}">${esc(s.name)}</span><span class="r">${esc(s.range)}</span>${partial ? "" : `<i class="h r" style="background:${s.color}"></i>`}</div>`;
  });
  $("bands").innerHTML = b;
  $("from").value = fmtA(view[0]); $("to").value = fmtA(view[1]);
}
["from", "to"].forEach((id) => $(id).addEventListener("change", () => {
  const a = parseAx($("from").value), b = parseAx($("to").value);
  if (a === null || b === null || b <= a) { status(axisTl() ? "Mốc hiển thị không hợp lệ (viết kiểu 0:30:00)." : "Giờ hiển thị không hợp lệ (viết kiểu 06:00).", "warn"); renderPage1(); return; }
  view = [a, b]; renderPage1(); saveUi();
}));
window.addEventListener("resize", () => { if (S && page === 1) renderTimeline(); });

/* cây Media bin: bin thật của project; bấm bin để đọc bin đó. Máy A, B, C là chữ cái màu dưới bin đang đọc */
function renderTree() {
  const f = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#C4C4CC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${FOLDER}</svg>`;
  const cur = S ? S.bin : null;
  let h = BINS.length ? "" : `<div class="empty">(đang đọc bin...)</div>`;
  for (const b of BINS) {
    const parts = b.path.split("/"), on = b.path === cur;
    h += `<div class="tn${on && mFilter === "all" ? " on" : ""}" data-path="${esc(b.path)}" style="margin-left:${(parts.length - 1) * 12}px" title="${esc(b.path)}">${f}<span class="t">${esc(parts[parts.length - 1])}</span><span class="chip">${b.n}</span></div>`;
    if (on && S) for (const m of S.machines) {
      const n = S.clips.filter((c) => c.mk === m.letter).length;
      h += `<div class="tn c1${mFilter === m.letter ? " on" : ""}" data-m="${esc(m.letter)}" style="margin-left:${(parts.length - 1) * 12 + 16}px"><span class="cam-dot" style="--c:${m.color}"></span><span class="t">${esc(m.name)}</span><span class="chip">${n}</span></div>`;
    }
  }
  $("tree").innerHTML = h;
}
$("tree").addEventListener("click", (e) => {
  const n = e.target.closest(".tn"); if (!n) return;
  if (n.dataset.m !== undefined) { mFilter = mFilter === n.dataset.m ? "all" : n.dataset.m; renderTree(); renderGrid1(); return; }
  const path = n.dataset.path;
  if (S && path === S.bin) { mFilter = "all"; renderTree(); renderGrid1(); return; }
  if (!BINS.some((b) => b.path === path)) return;
  $("binSel").value = path; mFilter = "all"; selUid = null; $("loadBtn").click();
});

/* lưới thumbnail theo giờ quay (hoặc vị trí timeline) */
function tileHtml(c) {
  const m = marksOf(c.uid), col = m.length ? S.stages[m[0].i].color : "";
  const rib = m.map((x) => `<span style="background:${S.stages[x.i].color}">F${x.i + 1} ${x.t.toUpperCase()}</span>`).join("");
  const mach = machOf(c.mk), bg = mach ? mach.color : "#4FC1A6";
  return `<div class="tile${c.uid === selUid ? " picked" : ""}" data-uid="${esc(c.uid)}">
    <div class="th${m.length ? " mark" : ""}" style="${thumbs[c.uid] ? "" : `background:linear-gradient(135deg,${bg}55,#18181B);`}${m.length ? "--mc:" + col + ";" : ""}">${thumbs[c.uid] ? `<img src="${thumbs[c.uid]}" draggable="false">` : PLAY}
      ${c.mk ? chip(c.mk) : ""}<span class="dur">${durTxt(c.dur)}</span>${m.length ? `<div class="rib" style="left:4px;top:4px;transform:none">${rib}</div>` : ""}</div>
    <span class="fn" title="${esc(c.name)}">${esc(c.name)}</span><span class="tm">${axisTl() ? fmtA(c.m0) : esc(c.time)}</span></div>`;
}
function renderGrid1() {
  const list = list1(), keep = $("g1").scrollTop;
  const last = S && S.bin ? S.bin.split("/").pop() : "Source";
  $("g1Title").textContent = mFilter === "all" ? last : ((machOf(mFilter) || {}).name || last);
  $("g1Count").textContent = S && S.n ? `${list.length} clip · theo ${axisTl() ? "vị trí timeline" : "giờ quay"}` : "";
  $("g1").innerHTML = list.length ? list.map(tileHtml).join("") : `<div class="empty">${S && S.n ? "Không có clip có vị trí trên trục." : 'Bấm "Đọc clip" để đọc clip.'}</div>`;
  $("g1").scrollTop = keep;
  observeTiles();
  if (scrollSel) { scrollSel = false; const t = $("g1").querySelector(".tile.picked"); if (t) t.scrollIntoView({ block: "nearest" }); }
}
let io1 = null, want1 = null;
const vis1 = new Set();
function observeTiles() {
  if (io1) io1.disconnect();
  vis1.clear();
  io1 = new IntersectionObserver((ents) => {
    ents.forEach((en) => { if (en.isIntersecting) vis1.add(en.target.dataset.uid); else vis1.delete(en.target.dataset.uid); });
    clearTimeout(want1);
    want1 = setTimeout(() => api().want_thumbs([...vis1]).then((ready) => {
      for (const u in ready) if (ready[u]) {
        thumbs[u] = ready[u];
        const box = document.querySelector(`#g1 .tile[data-uid="${CSS.escape(u)}"] .th`); if (box) setThumb(box, ready[u]);
      }
    }), 120);
  }, { root: $("g1"), rootMargin: "300px" });
  document.querySelectorAll("#g1 .tile").forEach((el) => io1.observe(el));
}
$("g1").addEventListener("click", (e) => {
  const t = e.target.closest(".tile"); if (!t) return;
  selUid = t.dataset.uid; $("g1").focus({ preventScroll: true });
  document.querySelectorAll("#g1 .tile.picked").forEach((x) => x.classList.remove("picked"));
  t.classList.add("picked"); renderMeta(); renderTimeline();
});

/* thông tin clip (thanh thu nhỏ sát dưới lưới Source: 6 mục cần thiết về file) */
function renderMeta() {
  const el = $("meta"), c = selUid ? clip1(selUid) : null;
  if (!c) { el.innerHTML = `<span class="dim12">Bấm một clip trong lưới để xem thông tin file, rồi bấm F1, F2… để đặt làm mốc.</span>`; return; }
  const m = marksOf(c.uid), mach = machOf(c.mk);
  const durS = c.m1 != null && c.m0 != null ? (c.m1 - c.m0) * 60 : c.dur;
  const markTxt = m.length ? m.map((x) => `${esc(S.stages[x.i].name)} (${x.t})`).join(", ") : "chưa";
  el.innerHTML =
    `<span class="mi"><span class="ml">File:</span><span class="mv">${esc(c.name)}</span></span>` +
    `<span class="mi"><span class="ml">Giờ quay:</span><span class="mv">${esc(c.time)}</span></span>` +
    `<span class="mi"><span class="ml">Dài:</span><span class="mv">${durTxt(durS)}</span></span>` +
    `<span class="mi"><span class="ml">FPS / TC:</span><span class="mv">${Math.round(c.fps || 25)}fps · ${esc(c.tc || "--:--:--:--")}</span></span>` +
    `<span class="mi"><span class="ml">LUT:</span><span class="mv">${esc(c.lut || "Không")}</span></span>` +
    `<span class="mi"><span class="ml">Máy / Mốc:</span><span class="mv">${c.mk ? esc(mach ? mach.name : c.mk) : "1 máy"} · ${markTxt}</span></span>`;
}
function renderKeys() {
  const n = S ? Math.min(S.stages.length, 9) : 0;
  $("keybar").innerHTML = `<span>Bấm clip → <b>F1…F${n || 1}</b> = mốc <b>ĐẦU</b> · <b>Shift+F1…</b> = mốc <b>CUỐI</b> · Esc bỏ chọn</span>
    <span class="alt">Phương án phụ, chưa làm: bấm F1 hai lần thay Shift+F1.</span>`;
}

/* phím F1..F9 (đọc bằng event.code): đặt mốc đầu; Shift+F = mốc cuối */
async function setMark(i, isTail) {
  if (!selUid) return status("Chưa chọn clip. Bấm một clip trong lưới trước.", "warn");
  if (!S || i >= S.stages.length) return status(`Chưa có giai đoạn ${i + 1}. Bấm "+ Thêm giai đoạn" trước.`, "warn");
  const r = await api().set_mark(i, selUid, isTail ? "tail" : "head");
  if (r.error) return status(r.error, "error");
  setState(r); status(r.mark_msg, "ok");
}
function key1(e) {
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || e.ctrlKey || e.altKey || e.metaKey) return;
  const m = /^F([1-9])$/.exec(e.code || "");
  if (m) { e.preventDefault(); setMark(+m[1] - 1, e.shiftKey); return; }
  const list = list1(), dv = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols1(), ArrowUp: -cols1() }[e.code];
  if (dv && list.length) {
    e.preventDefault();
    let p = list.findIndex((c) => c.uid === selUid);
    p = p < 0 ? 0 : Math.max(0, Math.min(list.length - 1, p + dv));
    selUid = list[p].uid; scrollSel = true; renderGrid1(); renderMeta(); renderTimeline();
  }
}
function cols1() { return Math.max(1, getComputedStyle($("g1")).gridTemplateColumns.split(" ").length); }



/* danh sách giai đoạn */
let nameClick = { i: -1, t: 0, prev: null };
$("stageList").addEventListener("click", async (e) => {
  const card = e.target.closest(".stage"); if (!card) return;
  const i = +card.dataset.i, act = e.target.dataset.act;
  if (act === "save") return saveStage(i, card);
  if (act === "add-bin") {
    const box = card.querySelector(".p1-bin-rows");
    if (box) {
      box.insertAdjacentHTML("beforeend", `<div class="p1-bin-row"><input class="inp" data-bin-inp="1" placeholder="Tên bin con"><button type="button" class="p1-bin-del" data-act="del-bin" title="Xóa bin con">×</button></div>`);
      const last = box.querySelector(".p1-bin-row:last-child input"); if (last) last.focus();
    }
    return;
  }
  if (act === "del-bin") { const r = e.target.closest(".p1-bin-row"); if (r) r.remove(); return; }
  if (act === "del") return ask("Xóa giai đoạn", `Xóa giai đoạn "${esc(S.stages[i].name)}" khỏi kế hoạch?<br>(Chỉ xóa trong Trợ lý, không đụng DaVinci. Nhãn đã ghi vẫn giữ.)`, "Xóa").then((ok) => {
    if (ok) { editIdx = null; api().del_stage(i).then(setState); }
  });
  if (e.target.closest(".stage-edit")) return;
  if (e.target.closest(".stage-name")) {                           // bấm đúp tên = đổi tên tại chỗ (nhận bằng thời gian vì lần bấm đầu vẽ lại danh sách)
    const now = Date.now();
    if (nameClick.i === i && now - nameClick.t < 500) {
      editIdx = nameClick.prev; nameClick = { i: -1, t: 0, prev: null }; renderPage1();
      const el = document.querySelector(`.stage[data-i="${i}"] .stage-name`);
      if (el) inlineRename(el, S.stages[i].name, (v) => doRename("stage", i, S.stages[i].name, v));
      return;
    }
    nameClick = { i, t: now, prev: editIdx };
  }
  editIdx = editIdx === i ? null : i; renderPage1();
});
$("stageList").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.target.dataset.f || e.target.dataset.binInp)) saveStage(+e.target.closest(".stage").dataset.i, e.target.closest(".stage"));
});
async function saveStage(i, card) {
  const f = {};
  card.querySelectorAll("[data-f]").forEach((el) => { f[el.dataset.f] = el.value; });
  f.bins = [...card.querySelectorAll("[data-bin-inp]")].map((el) => el.value.trim()).filter(Boolean);
  const old = S.stages[i].name;
  if (f.name !== undefined && f.name.trim() !== old) {            // đổi tên qua đường có kiểm tên (chỉ trong kế hoạch của panel)
    if (!(await doRename("stage", i, old, f.name))) return;
    f.name = S.stages[i].name;
  }
  api().set_stage(i, f).then((st) => { if (st.error) return status(st.error, "warn"); editIdx = null; setState(st); });
}
$("clearManual").onclick = async () => {
  if (await ask("Bỏ chọn tay", `Bỏ chọn tay của ${S.n_manual} clip? Các clip này quay về giai đoạn tính theo giờ quay.<br>(Nhãn bin con đã xếp vẫn giữ, chỉ có hiệu lực khi clip về đúng giai đoạn của nhãn.)`, "Bỏ chọn tay")) {
    setState(await api().clear_manual()); status("Đã bỏ chọn tay.", "ok");
  }
};
$("addStage").onclick = () => api().add_stage().then((st) => {
  if (st.error) return status(st.error, "warn");
  editIdx = null; setState(st); status(`Đã thêm giai đoạn ${st.stages.length}. Dùng F${st.stages.length} để đặt mốc.`, "ok");
});
$("suggestBtn").onclick = async () => {
  if (!S || !S.n) return status('Hãy bấm "Đọc clip" trước.', "warn");
  if (!$("tplSel").value) return status("Hãy chọn một mẫu sự kiện trước khi bấm Gợi ý lại.", "warn");
  if (S.stages.length && !(await ask("Gợi ý lại giai đoạn", "Thay các giai đoạn đang có bằng gợi ý mới theo khoảng nghỉ quay dài nhất?<br>(Nhãn phân loại đã ghi vẫn giữ.)", "Gợi ý lại"))) return;
  const r = await api().suggest($("tplSel").value);
  if (r.error) return status(r.error, "warn");
  setState(r); fitView(); renderPage1();
};
$("saveTpl").onclick = async () => {
  if (!S || !S.stages.length) return;
  const st = await api().settings_get();
  const curPath = (st && st.templates_path) || "";
  const ok = await ask("Lưu mẫu giờ cho đám sau",
    `<div class="v8"><label class="lbl">Tên mẫu (trùng tên thì ghi đè):<input id="tplName" class="inp" style="width:100%;margin-top:4px" value="${esc(S.template)}"></label>` +
    `<label class="lbl">Đường dẫn lưu file mẫu:<div class="inline8" style="margin-top:4px"><input id="tplDir" class="inp flex1" value="${esc(curPath)}"><button type="button" class="btn" id="tplPick">Chọn...</button></div></label></div>`,
    "Lưu mẫu", () => ({ name: document.getElementById("tplName").value, dir: document.getElementById("tplDir").value }));
  if (ok && ok.name) {
    const r = await api().save_template(ok.name, ok.dir);
    if (r && r.error) return status(r.error, "warn");
    setState(r); status(`Đã lưu mẫu "${ok.name}".`, "ok");
  }
};
document.addEventListener("click", async (e) => {
  if (e.target && e.target.id === "tplPick") {
    const r = await api().settings_pick_dir();
    const inp = document.getElementById("tplDir");
    if (r && r.dir && inp) inp.value = r.dir + "\\templates.json";
  }
});
$("loadBtn").onclick = () => { const b = $("binSel").value; if (b) { fitted = false; api().load(b, $("tlSel").value); } };
$("tlSel").addEventListener("change", () => { if (S && S.n) $("loadBtn").click(); });          // đổi timeline nguồn: đọc lại ngay (chỉ đọc)

/* ------------------------------------------------------------------ áp dụng / hoàn tác (hỏi trước, ADR-0009) */
let gotoAfterApply = false;
async function confirmApply(thenPage2) {
  if (!S || !S.n || !S.stages.length) return status('Hãy bấm "Đọc clip" và chia giai đoạn trước.', "warn");
  const pv = await api().apply_preview();
  const rows = pv.rows.map((r) => `<div class="m-row">${folder(r.color, 18)}<span class="t">${esc(r.bin)}</span><b>${r.n} clip</b></div>` +
    (r.sub.length ? `<div class="m-sub">${r.sub.map((x) => esc(x.name) + " " + x.n).join(" · ")}</div>` : "")).join("");
  const body = `Trợ lý sẽ GHI vào Media Pool của DaVinci: tạo bin con trong <b style="color:var(--text)">${esc(pv.src)}</b> và chuyển clip vào đó.
    <div style="margin:12px 0">${rows || "(không có clip nào)"}</div>
    ${pv.stay} clip ngoài mọi giai đoạn giữ nguyên chỗ cũ. Không xóa clip, không đổi tên, in/out, màu hay file trên ổ.
    Hoàn tác được bằng "Hoàn tác lần chuyển gần nhất".`;
  const note = (pv.emptied && pv.emptied.length) ? `<p><b>Bin cũ trong Media Pool sẽ còn lại RỖNG</b> (do đã đổi tên hoặc xếp lại): ${pv.emptied.map((x) => "<b>" + esc(x) + "</b>").join(", ")}.
    Trợ lý không tự xóa bin, bạn xóa tay trong DaVinci nếu không cần.</p>` : "";
  const nAi = S.clips.filter((c) => c.label_by === "ai_auto").length;
  const aiNote = nAi ? `<p>Trong đó <b>${nAi} clip do AI tự xếp</b> (dấu "AI xếp" trên thẻ). Muốn bỏ thì Hoàn tác AI xếp trước khi áp dụng.</p>` : "";
  if (!(await ask("Áp dụng vào Media Pool", body + note + aiNote, "Đồng ý, chuyển " + pv.total + " clip"))) return status("Đã hủy, chưa ghi gì vào DaVinci.", "info");
  gotoAfterApply = thenPage2;
  api().apply();
}
$("applyBtn1").onclick = () => confirmApply(true);
$("applyBtn2").onclick = () => confirmApply(false);
async function confirmUndo() {
  const m = S.moves[S.moves.length - 1];
  if (await ask("Hoàn tác", `Chuyển ${m.n} clip của lần áp dụng lúc ${esc(m.at)} về lại bin cũ?<br>(Bin con đã tạo để lại, không xóa.)`, "Hoàn tác")) api().undo();
}
$("undoBtn1").onclick = confirmUndo; $("undoBtn2").onclick = confirmUndo;
const _setState = setState;
setState = function (st) {
  const before = S ? S.moves.length : 0;
  _setState(st);
  if (gotoAfterApply && S && S.moves.length > before) { gotoAfterApply = false; goPage(2); }
};

/* hộp hỏi dùng chung: trả Promise true/false (hoặc giá trị getter) */
function ask(title, html, yes, getter) {
  return new Promise((res) => {
    $("mTitle").textContent = title; $("mBody").innerHTML = html; $("mYes").textContent = yes || "Đồng ý";
    $("modal").classList.remove("hidden");
    const inp = $("mBody").querySelector("input"); if (inp) { inp.focus(); inp.select(); }
    const done = (v) => { $("modal").classList.add("hidden"); $("mYes").onclick = $("mNo").onclick = null; res(v); };
    $("mYes").onclick = () => done(getter ? getter() : true);
    $("mNo").onclick = () => done(getter ? null : false);
  });
}

/* ------------------------------------------------------------------ BƯỚC 2: phân loại */
function stageObj() { return S && gStage !== null && gStage >= 0 ? S.stages[gStage] : null; }
/* Danh sách uid của lưới đang xem. Cùng nguồn với số đếm cạnh mỗi bin (Api.state: stage.uids / none / bins[].uids). */
function viewUids() {
  const base = viewUidsBase();
  if (!$("onlyStar") || !$("onlyStar").checked || !S) return base;
  const st = new Set(S.clips.filter((c) => c.star).map((c) => c.uid));
  return base.filter((u) => st.has(u));
}
function viewUidsBase() {
  if (!S || gStage === null) return [];
  if (gStage === -1) return S.clips.filter((c) => c.stage === null).map((c) => c.uid);
  const s = S.stages[gStage];
  if (!s) return [];
  if (gSub === NONE) return s.none;
  if (gSub !== null) { const b = s.bins.find((x) => x.name === gSub); return b ? b.uids : []; }
  return $("onlyNew").checked ? s.none : s.uids;
}
function viewLabel() {
  if (!S || gStage === null) return "";
  if (gStage === -1) return "Ngoài mọi giai đoạn";
  const s = S.stages[gStage];
  if (!s) return "";
  if (gSub === NONE) return `${s.name} > Chưa xếp`;
  if (gSub !== null) return `${s.name} > ${gSub}`;
  return `${s.name} · ${s.range}`;
}
function buildItems() {
  if (!S || gStage === null) { items = []; return; }
  if (gStage !== -1 && gSub !== null && gSub !== NONE && S.stages[gStage] && !S.stages[gStage].bins.some((b) => b.name === gSub)) gSub = null;
  const prevSel = new Set([...sel].map((i) => items[i] && items[i].uid).filter(Boolean));
  const prevCur = items[cur] && items[cur].uid;
  const want = new Set(viewUids());
  items = S.clips.filter((c) => want.has(c.uid));
  if (keepCur !== null) {                                        // vừa chuyển clip đi: giữ vị trí con trỏ
    cur = Math.max(0, Math.min(keepCur, items.length - 1));
    keepCur = null;
    sel = new Set(items.length ? [cur] : []);
  } else {                                                       // đổi bin đang xem: bỏ chọn clip không còn trong lưới
    sel = new Set(); items.forEach((c, i) => { if (prevSel.has(c.uid)) sel.add(i); });
    const ci = items.findIndex((c) => c.uid === prevCur);
    cur = ci >= 0 ? ci : (sel.size ? Math.min(...sel) : 0);
    if (!sel.size && items.length) sel = new Set([cur]);
  }
  anchor = cur;
}

function renderPage2(rebuild) {
  if (!S) { $("pool").innerHTML = ""; $("grid").innerHTML = ""; return; }
  renderPool();
  const s = stageObj();
  $("gridTitle").textContent = (viewLabel() || "Chưa chọn giai đoạn") + (S.n && gStage !== null ? ` (${viewUids().length} clip)` : "");
  const nk = s ? s.bins.filter((b) => b.key).length : 0;
  renderPage2b(s, nk, rebuild);
}
/* cột MEDIA POOL: thu gọn/mở bin mẹ tùy ý bằng mũi tên ▸/▾; khi mở bin khác thì bin phía trên KHÔNG tự đóng */
const p2Open = new Set();
const p2Touched = new Set();
function renderPool() {
  if (gStage !== null && gStage >= 0 && !p2Touched.has(gStage)) p2Open.add(gStage);
  let h = S.stages.map((s, i) => {
    const open = p2Open.has(i) || i === poolOpen;
    return `<div class="pool-stage"><div class="pool-row${i === gStage && gSub === null ? " on" : ""}${i === gStage && gSub !== null ? " parent" : ""}" data-stage="${i}" title="Bấm để xem cả giai đoạn. Bấm ▾/▸ để thu gọn/mở."><span class="p2-ar" data-ar="1">${open ? "▾" : "▸"}</span>${folder(s.color, 18)}<span class="t">${esc(s.bin)}</span><span class="dim12">${s.count}</span>${i < MAX_F ? `<span class="k" title="F${i + 1}: chuyển clip sang giai đoạn này">F${i + 1}</span>` : ""}</div>` +
      (open ? `<div class="pool-subs"><div class="sub-none${i === gStage && gSub === NONE ? " on" : ""}" data-stage="${i}"><span class="sq" style="background:var(--dim2);opacity:.5"></span><span class="t">Chưa xếp</span><span class="dim12">${s.none.length}</span></div>${s.bins.map((b) => `<div class="sub${i === gStage && gSub === b.name ? " on" : ""}" data-stage="${i}" data-bin="${esc(b.name)}"><span class="sq" style="background:${b.color}"></span><span class="t">${esc(b.name)}</span><span class="dim12">${b.count}</span>${b.key ? `<span class="k">${b.key}</span>` : ""}</div>`).join("")}
        ${i === gStage ? `<button class="sub-add" id="subAdd">+ Bin mới</button>` : ""}</div>` : "") + `</div>`;
  }).join("");
  if (S.outside) h += `<div class="pool-stage"><div class="pool-row${gStage === -1 ? " on" : ""}" data-stage="-1">${folder("#6A6A72", 18)}<span class="t" style="color:var(--dim)">Ngoài giai đoạn</span><span class="dim12">${S.outside}</span></div></div>`;
  $("pool").innerHTML = h;
}
function renderPage2b(s, nk, rebuild) {
  $("gridHint").textContent = s ? `Bấm bin bên trái để XEM. Muốn xếp clip: kéo thumbnail vào bin, hoặc phím số 1–${nk}; F1–F12 chuyển sang giai đoạn khác. Mỗi lần bạn xếp, AI ghi lại để học.`
    : "Clip ngoài giai đoạn: phím F1–F12 hoặc kéo thả vào bin giai đoạn bên trái để chuyển.";
  $("starCount").textContent = S.n_starred || 0;
  $("doneText").textContent = s ? `${s.done} / ${s.count} đã xếp` : "";
  $("keyList").innerHTML = (s ? s.bins.filter((b) => b.key).map((b) => `<div class="key-row" data-bin="${esc(b.name)}"><span class="l"><i style="background:${b.color}"></i>${esc(b.name)}</span><span class="r">phím ${b.key} · ${b.count} clip</span></div>`).join("") : "") +
    `<div class="key-stages">${S.stages.slice(0, MAX_F).map((x, i) => `<span class="ks" data-stage="${i}" title="Chuyển clip đang chọn sang ${esc(x.bin)}"><b>F${i + 1}</b> ${esc(x.name)}</span>`).join("")}</div>` +
    (S.stages.length > MAX_F ? `<div class="ks-warn" id="ksWarn">Có ${S.stages.length} giai đoạn nhưng bàn phím chỉ có F1–F12. Giai đoạn thứ ${MAX_F + 1} trở đi (${S.stages.slice(MAX_F).map((x) => esc(x.name)).join(", ")}) không có phím: dùng kéo thả vào bin bên trái hoặc bấm chuột phải thumbnail.</div>` : "");
  if (rebuild || !sameItems()) { buildItems(); renderGrid(); } else patchGrid();
  showCur();
}
function sameItems() {
  const want = viewUids();
  if (want.length !== items.length) return false;
  const byUid = new Map(S.clips.map((c) => [c.uid, c]));
  const wantSet = new Set(want);
  for (let k = 0; k < items.length; k++) {
    if (!wantSet.has(items[k].uid)) return false;
    items[k] = byUid.get(items[k].uid);
  }
  return true;
}
function tagHtml(c) {
  const s = stageObj();
  const b = s && c.label ? s.bins.find((x) => x.name === c.label) : null;
  if (b && c.label_by === "ai_auto") return `<span class="tag aiauto" title="AI xếp (chưa phải bạn xếp, không tính vào dữ liệu AI học): ${esc(b.name)}" style="border-color:${b.color}">AI xếp · ${esc(b.name)}</span>`;
  if (b) return `<span class="tag" style="background:${b.color}33;color:var(--text);border:1px solid ${b.color}">${esc(b.name)}</span>`;
  const w = aiWait(c);                                                   // đã Tự phân loại mà hạng 1 dưới ngưỡng: viền cam đứt, chờ bạn duyệt
  if (w) return `<span class="tag wait" title="${esc("Chờ bạn duyệt: hạng 1 của AI là " + w.bin + " chỉ " + Math.round(w.score * 100) + "% (dưới ngưỡng). Bấm A để nhận hạng 1, hoặc xếp tay.")}">chờ bạn duyệt</span>`;
  const g = !c.label && AI.group && AI.group[c.uid];                      // gợi ý AI của cả nhóm (ai.js): viền đứt, chờ bạn duyệt
  if (g && g.top) return `<span class="tag ai" title="${esc("AI gợi ý (chờ bạn duyệt): " + g.top.map((t) => t.bin + " " + Math.round(t.score * 100) + "%").join(" · "))}">AI · ${esc(g.top[0].bin)} ${Math.round(g.top[0].score * 100)}%</span>`;
  return `<span class="tag none">Chưa xếp</span>`;
}
function cardKey(c) { return (c.label || "") + "|" + (c.label_by || "") + "|" + aiKey(c); }
function setThumb(box, src) {
  let img = box.querySelector("img");
  if (!img) { img = document.createElement("img"); img.draggable = false; box.prepend(img); const ic = box.querySelector("svg"); if (ic) ic.remove(); }
  if (img.getAttribute("src") !== src) img.src = src;
}
const PLAY = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M10 9.5l4 2.5-4 2.5z"></path></svg>';
function renderGrid() {
  $("grid").innerHTML = items.length ? items.map((c, i) => `
    <div class="card${i === cur ? " cur" : sel.has(i) ? " picked" : ""}${c.star ? " starred" : ""}${aiWait(c) ? " wait" : ""}" data-i="${i}" data-uid="${esc(c.uid)}" data-label="${esc(cardKey(c))}" draggable="true">
      <div class="thumb">${thumbs[c.uid] ? `<img src="${thumbs[c.uid]}" draggable="false">` : PLAY}<span class="badge tl">${c.time}</span><span class="badge br">${durTxt(c.dur)}</span>${c.star ? '<span class="star-badge">★</span>' : ""}</div>
      <div class="card-foot"><span class="f">${esc(c.name)}</span>${tagHtml(c)}</div>
    </div>`).join("") : `<div class="empty">${S && S.n ? "Không có clip." : 'Bấm "Đọc clip" ở bước 1 trước.'}</div>`;
  observeCards();
}
function patchGrid() {
  document.querySelectorAll("#grid .card").forEach((el) => {
    const i = +el.dataset.i, c = items[i]; if (!c) return;
    const cls = "card" + (i === cur ? " cur" : sel.has(i) ? " picked" : "") + (c.star ? " starred" : "") + (aiWait(c) ? " wait" : "");
    const hasStar = !!el.querySelector(".star-badge");
    if (!!c.star !== hasStar) { if (c.star) el.querySelector(".thumb").insertAdjacentHTML("beforeend", '<span class="star-badge">★</span>'); else el.querySelector(".star-badge").remove(); }
    if (el.className !== cls) el.className = cls;               // chỉ đổi class, không dựng lại ô
    const key = cardKey(c);
    if (el.dataset.label !== key) { el.dataset.label = key; el.querySelector(".tag").outerHTML = tagHtml(c); }
  });
}
let io = null, wantTimer = null;
const visible = new Set();
function observeCards() {
  if (io) io.disconnect();
  visible.clear();
  io = new IntersectionObserver((ents) => {
    ents.forEach((en) => { if (en.isIntersecting) visible.add(en.target.dataset.uid); else visible.delete(en.target.dataset.uid); });
    clearTimeout(wantTimer);
    wantTimer = setTimeout(() => api().want_thumbs([...visible]).then((ready) => {
      for (const u in ready) if (ready[u]) {
        thumbs[u] = ready[u];
        const box = document.querySelector(`.card[data-uid="${CSS.escape(u)}"] .thumb`); if (box) setThumb(box, ready[u]);
      }
    }), 120);
  }, { root: $("gridScroll"), rootMargin: "300px" });
  document.querySelectorAll("#grid .card").forEach((el) => io.observe(el));
}

function moveCur(i, extend, keepSel) {
  if (!items.length) return;
  i = Math.max(0, Math.min(items.length - 1, i));
  cur = i;
  if (extend) { sel = new Set(); for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) sel.add(k); }
  else if (!keepSel) { sel = new Set([i]); anchor = i; }
  patchGrid();
  const el = document.querySelector(`#grid .card[data-i="${i}"]`); if (el) el.scrollIntoView({ block: "nearest" });
  showCur();
}
function cols() { return getComputedStyle($("grid")).gridTemplateColumns.split(" ").length; }

async function assign(binName) {
  const s = stageObj(); if (!s || !items.length) return;
  const idx = [...(sel.size ? sel : new Set([cur]))].sort((a, b) => a - b);
  const first = items[idx[0]].uid;
  keepCur = idx[0];
  const st = await api().label(idx.map((i) => items[i].uid), gStage, binName);
  if (st.error) { keepCur = null; return status(st.error, "warn"); }
  setState(st);
  keepCur = null;
  const stays = items.some((c) => c.uid === first);                      // còn trong lưới (xem cả giai đoạn): sang clip kế
  if (stays && idx.length === 1 && cur < items.length - 1) moveCur(cur + 1);
}
function keyBin(k) { const s = stageObj(); const b = s && s.bins.find((x) => x.key === k); return b ? b.name : null; }

$("pool").addEventListener("click", (e) => {
  const row = e.target.closest(".pool-row");
  if (row) {
    const si = +row.dataset.stage;
    if (e.target.closest("[data-ar]")) {
      p2Touched.add(si);
      if (p2Open.has(si)) p2Open.delete(si); else p2Open.add(si);
      renderPool();
      return;
    }
    if (si >= 0) p2Open.add(si);
    viewBin(si, null);
    return;
  }
  const none = e.target.closest(".sub-none");
  if (none) { viewBin(+none.dataset.stage, NONE); return; }
  const sub = e.target.closest(".sub");
  if (sub) { viewBin(+sub.dataset.stage, sub.dataset.bin); return; }
  if (e.target.id === "subAdd") {
    const inp = document.createElement("input");
    inp.className = "inp sub-input"; inp.placeholder = "Tên bin mới, Enter để thêm";
    e.target.replaceWith(inp); inp.focus();
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && inp.value.trim()) api().add_bin(gStage, inp.value).then((r) => { if (r && r.error) status(r.error, "warn"); else setState(r); });
      if (ev.key === "Escape") renderPage2();
    });
  }
});
function viewBin(si, sub) {
  if (si === gStage && sub === gSub) { $("gridScroll").focus(); return; }
  gStage = si; gSub = sub;
  $("onlyNew").checked = false;
  saveUi();
  renderPage2(true);
  $("gridScroll").focus();
}
$("keyList").addEventListener("click", (e) => {
  const r = e.target.closest(".key-row"); if (r) return assign(r.dataset.bin);
  const k = e.target.closest(".ks"); if (k) moveSel(+k.dataset.stage, null);
});
$("grid").addEventListener("mousedown", (e) => {
  if (e.shiftKey || e.ctrlKey) e.preventDefault();          // Shift/Ctrl + bấm: không để trình duyệt tự bôi chọn chữ/ảnh
  cancelPending();                                           // bấm chuột chọn ô khác: kết thúc chế độ chờ bin con
});
$("grid").addEventListener("selectstart", (e) => e.preventDefault());
$("grid").addEventListener("click", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  const i = +card.dataset.i;
  $("gridScroll").focus();
  if (e.shiftKey) { sel = new Set(e.ctrlKey ? sel : []); for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) sel.add(k); moveCur(i, false, true); }
  else if (e.ctrlKey) { sel.has(i) ? sel.delete(i) : sel.add(i); anchor = i; moveCur(i, false, true); }
  else moveCur(i);
});
$("grid").addEventListener("dblclick", () => reveal());
/* kéo thả: kéo một hoặc nhiều thumbnail đang chọn, thả vào bin giai đoạn (đổi giai đoạn) hoặc bin con (+ nhãn) */
$("grid").addEventListener("dragstart", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  const i = +card.dataset.i;
  if (!sel.has(i)) { sel = new Set([i]); cur = i; anchor = i; patchGrid(); }
  dragging = true;
  e.dataTransfer.setData("text/plain", "troly"); e.dataTransfer.effectAllowed = "move";
  status(`Đang kéo ${sel.size} clip: thả vào bin giai đoạn (đổi giai đoạn) hoặc bin con (đổi giai đoạn + xếp nhãn).`, "info");
});
$("grid").addEventListener("dragend", () => endDrag());
function dropTarget(e) { return e.target.closest ? e.target.closest(".sub, .pool-row") : null; }
let hoverTimer = null, hoverStage = null;
$("pool").addEventListener("dragover", (e) => {
  const t = dropTarget(e); if (!t || !dragging) return;
  if (t.dataset.stage === "-1") return;                       // không thả vào "Ngoài giai đoạn"
  e.preventDefault(); e.dataTransfer.dropEffect = "move";
  document.querySelectorAll("#pool .drop").forEach((x) => { if (x !== t) x.classList.remove("drop"); });
  t.classList.add("drop");
  if (t.classList.contains("pool-row")) {                      // giữ chuột trên bin giai đoạn: mở bin con của nó
    const i = +t.dataset.stage;
    if (hoverStage !== i) {
      hoverStage = i; clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => {
        if (dragging && poolOpen !== i) {
          poolOpen = i; renderPool();
          const r = document.querySelector(`#pool .pool-row[data-stage="${i}"]`); if (r) r.classList.add("drop");
        }
      }, 600);
    }
  }
});
$("pool").addEventListener("dragleave", (e) => { const t = dropTarget(e); if (t && !t.contains(e.relatedTarget)) t.classList.remove("drop"); });
$("pool").addEventListener("drop", (e) => {
  const t = dropTarget(e); if (!t || !dragging) return;
  e.preventDefault();
  const si = +t.dataset.stage;
  const bin = t.classList.contains("sub") ? t.dataset.bin : null;
  endDrag();
  moveSel(si, bin);
});
function endDrag() {
  dragging = false; clearTimeout(hoverTimer); hoverStage = null;
  document.querySelectorAll("#pool .drop").forEach((x) => x.classList.remove("drop"));
  if (poolOpen !== null) { poolOpen = null; renderPool(); }
}

/* chuyển clip đang chọn sang giai đoạn si (chọn tay), kèm bin con nếu có */
async function moveSel(si, bin) {
  if (!items.length || si === null || si < 0 || !S.stages[si]) return;
  const idx = [...(sel.size ? sel : new Set([cur]))].sort((a, b) => a - b);
  const uids = idx.map((i) => items[i].uid);
  keepCur = idx[0];
  const st = await api().move(uids, si, bin);
  if (st.error) { keepCur = null; return status(st.error, "warn"); }
  setState(st);
  keepCur = null;
  status(`Đã chuyển ${uids.length} clip sang ${S.stages[si].bin}${bin ? " › " + bin : ""} (chọn tay).`, "ok");
}

/* menu chuột phải trên thumbnail */
$("grid").addEventListener("contextmenu", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  e.preventDefault();
  const i = +card.dataset.i;
  if (!sel.has(i)) { sel = new Set([i]); anchor = i; }
  cur = i; patchGrid(); showCur();
  const s = stageObj(), m = $("ctx");
  m.innerHTML = `<div class="ctx-h">Chuyển ${sel.size} clip sang giai đoạn</div>` +
    S.stages.map((x, k) => `<div class="ctx-i${k === gStage ? " off" : ""}" data-stage="${k}"><i style="background:${x.color}"></i>${esc(x.bin)}<span>${k < MAX_F ? "F" + (k + 1) : ""}</span></div>`).join("") +
    (s ? `<div class="ctx-h">Xếp vào bin con của ${esc(s.name)}</div>` +
      s.bins.map((b) => `<div class="ctx-i" data-bin="${esc(b.name)}"><i style="background:${b.color}"></i>${esc(b.name)}<span>${b.key}</span></div>`).join("") +
      `<div class="ctx-i" data-bin=""><i></i>Bỏ nhãn<span>0</span></div>` : "");
  m.classList.remove("hidden");
  const r = m.getBoundingClientRect();
  m.style.left = Math.max(8, Math.min(e.clientX, innerWidth - r.width - 8)) + "px";
  m.style.top = Math.max(8, Math.min(e.clientY, innerHeight - r.height - 8)) + "px";
});
$("ctx").addEventListener("click", (e) => {
  const it = e.target.closest(".ctx-i"); if (!it || it.classList.contains("off")) return;
  $("ctx").classList.add("hidden");
  if (it.dataset.stage !== undefined) moveSel(+it.dataset.stage, null);
  else assign(it.dataset.bin || null);
});
document.addEventListener("mousedown", (e) => {
  if (!e.target.closest("#ctx")) $("ctx").classList.add("hidden");
  if (!e.target.closest("#pend")) cancelPending();                 // bấm chuột ở bất kỳ đâu ngoài dải chờ: thôi chờ
});

$("onlyNew").addEventListener("change", () => { saveUi(); renderPage2(true); });
$("onlyStar").addEventListener("change", () => renderPage2(true));

/* Dấu sao ★ (phím P): chọn nhiều clip thì đặt đồng loạt. Có clip chưa sao -> gắn sao cho tất cả; tất cả đã sao -> bỏ sao. */
async function toggleStar() {
  if (!items.length) return;
  const idx = sel.size ? [...sel] : [cur];
  const cs = idx.map((i) => items[i]).filter(Boolean);
  if (!cs.length) return;
  const target = !cs.every((c) => c.star);                       // true = gắn sao, false = bỏ sao
  const uids = cs.filter((c) => !!c.star !== target).map((c) => c.uid);
  if (!uids.length) return;
  const st = await api().toggle_star(uids);
  setState(st);
  status((target ? "Đã gắn sao ★ cho " : "Đã bỏ sao của ") + uids.length + " clip.", "ok");
}
$("starToggleBtn").onclick = () => toggleStar();
async function appendStarred() {
  const n = S ? (S.n_starred || 0) : 0;
  if (!n) return status("Chưa có clip nào có sao ★. Bấm phím P để gắn sao.", "warn");
  const ok = await ask("Đưa clip có sao lên timeline",
    `<p>Sẽ TẠO một timeline MỚI trong DaVinci gồm <b>${n}</b> clip có sao ★, xếp theo giai đoạn rồi theo giờ quay.</p><p>Timeline đang có không bị sửa. Điểm In/Out sẽ chỉnh lại trong DaVinci sau.</p>`, "Tạo timeline mới");
  if (!ok) return;
  const r = await api().append_starred();
  if (r && r.error) status(r.error, "warn");
}
$("appendStarBtn").onclick = () => appendStarred();
$("revealBtn").onclick = () => reveal();
function reveal() { if (items[cur]) api().reveal(items[cur].uid).then((n) => status("Đã mở " + n + " trong Media Pool của DaVinci.", "info")); }

/* Bàn phím bước 2: đọc event.code (Digit1..9, Numpad1..9, F1..F12), KHÔNG dùng event.key: Unikey kiểu VNI dùng phím số.
   Bỏ qua phím khi đang gõ trong ô nhập chữ. Giai đoạn chọn bằng F1–F12 (ADR-0030), bin con bằng số 1–9. */
const MAX_F = 12;
function fKeyOf(e) { const m = /^F([1-9]|1[0-2])$/.exec(e.code || ""); return m ? +m[1] : null; }
const F_BLOCK = new Set(["F1", "F5", "F11", "F12"]);   // trợ giúp, tải lại, toàn màn hình, công cụ dev: chặn mặc định trong pywebview
let pending = null;                                   // F1–F12 đang chờ số bin con: KHÔNG hết hạn theo giờ
function digitOf(e) { const m = /^(Digit|Numpad)([0-9])$/.exec(e.code || ""); return m ? +m[2] : null; }
/* F1–F12: chuyển clip đang chọn sang giai đoạn đó NGAY, rồi chờ số bin con. Chỉ kết thúc khi: bấm số bin con (xếp xong),
   0 (bỏ nhãn), Esc, bấm chuột chọn ô khác, phím mũi tên, hoặc đổi bước. Phân loại source không gấp nên không có đếm ngược. */
async function startPending(si) {
  cancelPending();
  if (!items.length) return;
  const idx = [...(sel.size ? sel : new Set([cur]))].sort((a, b) => a - b);
  const uids = idx.map((i) => items[i].uid);
  keepCur = idx[0];
  const st = await api().move(uids, si, null);
  if (st.error) { keepCur = null; return status(st.error, "warn"); }
  setState(st);
  keepCur = null;
  pending = { si, uids };
  const x = S.stages[si], box = $("pend");
  box.innerHTML = `<div class="pend-h">Đang chờ bin con của ${esc(x.bin)} (${uids.length} clip vừa chuyển sang giai đoạn này)</div>` +
    x.bins.filter((b) => b.key).map((b) => `<span><b>${b.key}</b> ${esc(b.name)}</span>`).join("") +
    `<span class="dim12"><b>0</b> bỏ nhãn · <b>Esc</b> để thôi (giữ nguyên giai đoạn)</span>`;
  box.classList.remove("hidden");
  status(`Đã chuyển ${uids.length} clip sang ${x.bin}. Bấm số để xếp vào bin con, 0 bỏ nhãn, Esc để thôi.`, "info");
}
function cancelPending() { pending = null; $("pend").classList.add("hidden"); }
async function finishPending(binName) {
  if (!pending) return;
  const { si, uids } = pending;
  cancelPending();
  const st = await api().label(uids, si, binName);
  if (st.error) return status(st.error, "warn");
  setState(st);
  status(binName ? `Đã xếp ${uids.length} clip vào ${S.stages[si].bin} › ${binName}.` : `Đã bỏ nhãn ${uids.length} clip.`, "ok");
}

document.addEventListener("keydown", (e) => {
  if (F_BLOCK.has(e.code) && !e.ctrlKey && !e.altKey && !e.metaKey) e.preventDefault();   // không để F1/F5/F11/F12 làm việc của trình duyệt
  if (!$("modal").classList.contains("hidden")) {
    if (e.key === "Escape") $("mNo").click(); else if (e.key === "Enter") $("mYes").click();
    return;
  }
  if (e.ctrlKey && !e.altKey && !e.metaKey && e.code === "KeyZ") {
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
    e.preventDefault();
    if (page === 3) return $("ioUndo").click();
    if (S && S.moves && S.moves.length) { confirmUndo(); return; }
    status("Chưa có thao tác nào để hoàn tác (Ctrl+Z).", "info");
    return;
  }
  if (page === 1) { if (e.key === "Escape") { if (selUid) { selUid = null; renderGrid1(); renderMeta(); renderTimeline(); } return; } key1(e); return; }
  if (e.key === "Escape") { $("ctx").classList.add("hidden"); if (pending) { cancelPending(); status("Đã thôi chờ bin con (clip giữ nguyên giai đoạn mới).", "info"); } return; }
  if (page === 4) { lnKey(e); return; }
  if (page === 3) {                                                  // Bước 3: P sao, 4 phím mũi tên di chuyển source, Enter; số KHÔNG xếp bin ở đây
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.code === "KeyP" && !e.shiftKey) { e.preventDefault(); toggleStar(); return; }
    if (e.code === "ArrowUp" || e.code === "ArrowDown" || e.code === "ArrowLeft" || e.code === "ArrowRight") {
      e.preventDefault();
      let step = (e.code === "ArrowLeft" || e.code === "ArrowUp") ? -1 : 1;
      if (e.code === "ArrowUp" || e.code === "ArrowDown") {
        const tg = document.querySelector("#p3List .p3-clips.thumbs");
        if (tg) {
          const cards = tg.querySelectorAll(".p3-clip"), cw = cards.length ? cards[0].offsetWidth : 0;
          const p3c = cw > 0 ? Math.max(1, Math.floor((tg.clientWidth + 6) / (cw + 6))) : 1;
          step *= p3c;
        }
      }
      moveCur(cur + step);
      return;
    }
    if (e.code === "Enter") { e.preventDefault(); reveal(); }
    return;
  }
  if (page !== 2 || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.code === "KeyP" && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) { cancelPending(); e.preventDefault(); toggleStar(); return; }
  const d = digitOf(e);
  if (pending && d !== null && !e.ctrlKey && !e.altKey) {          // số sau phím F: vào bin con
    e.preventDefault();
    if (d === 0) return finishPending(null);
    const b = S.stages[pending.si].bins.find((x) => x.key === String(d));
    if (b) finishPending(b.name);
    return;
  }
  const f = fKeyOf(e);
  if (f !== null && !e.ctrlKey && !e.altKey && !e.metaKey) {       // F1–F12: sang giai đoạn số đó rồi chờ bin con
    e.preventDefault();
    if (f > S.stages.length) status(`Chưa có giai đoạn thứ ${f}: kế hoạch này có ${S.stages.length} giai đoạn.`, "warn");
    else if (items.length) startPending(f - 1);
    return;
  }
  if (d !== null && e.shiftKey) { e.preventDefault(); status("Đã đổi phím: giai đoạn chọn bằng F1–F12, rồi bấm số bin con.", "info"); return; }
  const dir = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -cols(), ArrowDown: cols() }[e.key];
  if (dir) { cancelPending(); e.preventDefault(); moveCur(cur + dir, e.shiftKey); return; }
  if (e.ctrlKey && e.code === "KeyA") { cancelPending(); e.preventDefault(); sel = new Set(items.map((_, i) => i)); patchGrid(); showCur(); return; }
  if (e.key === "Enter") { e.preventDefault(); reveal(); return; }
  if (d !== null && !e.ctrlKey && !e.altKey) {                    // 1-9: bin con của giai đoạn đang xem, 0: bỏ nhãn
    e.preventDefault();
    if (d === 0) assign(null); else { const b = keyBin(String(d)); if (b) assign(b); }
  }
});

async function showCur() {
  const c = items[cur];
  if (!c) {
    plStop(); PL.uid = null;
    renderPage3Cur(null);
    $("curName").textContent = ""; $("preview").innerHTML = "<span>Chọn một clip để xem</span>"; $("curBin").textContent = "—"; $("curInfo").textContent = "";
    $("ioIn").textContent = "In --:--:--"; $("ioIn").className = "io-in";
    $("ioOut").textContent = "Out --:--:--"; $("ioOut").className = "io-in";
    $("ioDur").textContent = "Giữ --:--:--";
    $("ioBar").innerHTML = '<div class="io-empty">Chưa chọn clip</div>';
    $("ioRule").textContent = "";
    return;
  }
  $("curName").textContent = c.name;
  $("starToggleBtn").textContent = c.star ? "★ Bỏ sao (phím P)" : "☆ Gắn sao (phím P)";
  $("starToggleBtn").classList.toggle("active", !!c.star);
  renderPage3Cur(c);
  aiBoxRender();                                           // hộp Gợi ý AI (ai.js)
  $("curBin").textContent = c.label ? c.label + (c.label_by === "ai_auto" ? " (AI xếp)" : "") : "Chưa xếp";
  const src = { created: "Date Created", modified: "Date Modified − độ dài", none: "không rõ" }[c.src] || c.src;
  $("curInfo").textContent = `Giờ quay ${c.time} (${src}) · dài ${durTxt(c.dur)}\nMáy ${c.camera}\nHình: ${notes[c.uid] || "đang làm..."}\nLUT: ${c.lut || "(không gắn)"}` +
    (sel.size > 1 ? `\nĐang chọn ${sel.size} clip` : "");

  plRenderIo(c);                                           // thanh In/Out (player.js): đặt tay > DaVinci > gợi ý

  const uid = c.uid;
  if (PL.uid !== uid) { plStop(); PL.uid = uid; plOpen(c); }          // trình phát proxy (player.js); thumbnail là nền
  const showImg = (src) => {
    const host = $("preview");
    const sp = host.querySelector("span"); if (sp) sp.remove();
    let img = host.querySelector("img");
    if (!img) { img = document.createElement("img"); img.draggable = false; host.prepend(img); }
    img.src = src;
    // giữ nguyên video, canvas.pv-lut và canvas.pv-frame không tháo khỏi DOM
  };
  if (bigs[uid]) { showImg(bigs[uid]); return; }
  if (thumbs[uid]) showImg(thumbs[uid]); else if (!$("preview").querySelector("video")) $("preview").innerHTML = "<span>Đang làm hình xem trước...</span>";
  const r = await api().big(uid);
  if (r && r.src) { bigs[uid] = r.src; notes[uid] = notes[uid] || r.note; }
  if (items[cur] && items[cur].uid === uid && bigs[uid]) showImg(bigs[uid]);
}

/* ------------------------------------------------------------------ chuyển bước, khởi động */
function goPage(n) { cancelPending(); saveUi(); if (page === 3 && n !== 3) p3Leave(); page = n; render(false); if (n === 5) renderPage5(); if (n === 2) $("gridScroll").focus(); if (n === 3) $("p3List").focus(); if (n === 1) renderTimeline(); }
document.querySelectorAll(".step").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); goPage(+a.dataset.page); }));

window.addEventListener("pywebviewready", async () => {
  INFO = await api().init();
  applyUi(INFO.ui);                                          // khôi phục bước, bin đang xem, thu phóng đã lưu
  render(true);
  const st = await api().state();
  if (st.n) setState(st);
});

/* ------------------------------------------------------------------ ĐỔI TÊN giai đoạn / bin con (ADR-0015) */
/* Bấm đúp tên giai đoạn (bước 1 và cột Media Pool) hoặc tên bin con (cột Media Pool): sửa tại chỗ, Enter đổi, Esc hoặc bấm ra ngoài thì hủy.
   Chỉ đổi trong kế hoạch của panel (nhãn clip đi theo tên mới). Bin thật trong Media Pool chỉ tạo khi bấm Áp dụng.
   Python kiểm tên mới (rỗng, ký tự cấm, trùng tên cùng cấp) và báo lỗi rõ. */
async function doRename(kind, i, old, raw) {
  const r = await api().rename(kind, i, old, raw);
  if (r && r.error) { status(r.error, "warn"); return false; }
  if (r && r.same) return true;
  setState(await api().state());
  status(`Đã đổi tên ${kind === "stage" ? "giai đoạn" : "bin con"} thành “${r.name}”. Nhãn clip đi theo tên mới.` +
    (r.old_bin_left ? " Bin cũ trong Media Pool sẽ còn lại rỗng sau khi Áp dụng, Trợ lý không tự xóa." : " Bin trong Media Pool chỉ tạo khi bấm Áp dụng."), "ok");
  return true;
}
function inlineRename(el, current, commit) {
  const inp = document.createElement("input");
  inp.className = "inp rename-inp"; inp.value = current; inp.maxLength = 60; inp.setAttribute("aria-label", "Tên mới");
  el.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const finish = async (ok) => {
    if (done) return; done = true;
    if (ok && inp.value.trim() !== current) await commit(inp.value);
    render(false);
  };
  inp.addEventListener("keydown", (e) => {
    e.stopPropagation();                                           // gõ số hay chữ không bị coi là phím 1–9 hay J
    if (e.key === "Enter") { e.preventDefault(); finish(true); } else if (e.key === "Escape") { e.preventDefault(); finish(false); }
  });
  ["click", "dblclick", "mousedown"].forEach((t) => inp.addEventListener(t, (e) => e.stopPropagation()));
  inp.addEventListener("blur", () => finish(false));
}
$("pool").addEventListener("dblclick", (e) => {
  const t = e.target.closest(".t"); if (!t || !S) return;
  const sub = e.target.closest(".sub"), row = e.target.closest(".pool-row");
  if (sub && sub.dataset.bin) inlineRename(t, sub.dataset.bin, (v) => doRename("bin", +sub.dataset.stage, sub.dataset.bin, v));
  else if (row && +row.dataset.stage >= 0) { const i = +row.dataset.stage; inlineRename(t, S.stages[i].name, (v) => doRename("stage", i, S.stages[i].name, v)); }
});

/* Kiểu quay (ADR-0018): chỉ đổi gợi ý màu xanh; In/Out đặt tay luôn thắng */
$("styleSel").onchange = async (e) => {
  const st = await api().set_shoot_style(e.target.value);
  if (st && st.error) return status(st.error, "warn");
  setState(st);
  if (page === 5) renderPage5();
  status(e.target.value ? "Đã chọn kiểu quay " + (e.target.value === "psc" ? "PSC" : "Truyền thống") + ": chỉ đổi gợi ý màu xanh, In/Out bạn đặt tay vẫn thắng." : "Đã bỏ chọn kiểu quay: gợi ý như mặc định.", "ok");
};

/* ---- Zoom Thumbnail Page 1 & Page 2 + Quét chuột chọn nhiều clip ---- */
(function initZoomAndMarquee() {
  const z1 = $("g1Zoom"), z2 = $("g2Zoom");
  if (z1) {
    const applyZ1 = (v) => {
      v = Math.max(80, Math.min(260, +v || 118));
      z1.value = v;
      const g1 = $("g1"); if (g1) g1.style.setProperty("--g1-w", v + "px");
    };
    z1.addEventListener("input", () => applyZ1(z1.value));
    $("g1").addEventListener("wheel", (e) => {
      if (e.ctrlKey) { e.preventDefault(); applyZ1(+z1.value + (e.deltaY < 0 ? 18 : -18)); }
    }, { passive: false });
  }
  if (z2) {
    const applyZ2 = (v) => {
      v = Math.max(120, Math.min(320, +v || 200));
      z2.value = v;
      const gr = $("grid"); if (gr) gr.style.gridTemplateColumns = `repeat(auto-fill, minmax(${v}px, 1fr))`;
    };
    z2.addEventListener("input", () => applyZ2(z2.value));
    $("gridScroll").addEventListener("wheel", (e) => {
      if (e.ctrlKey) { e.preventDefault(); applyZ2(+z2.value + (e.deltaY < 0 ? 20 : -20)); }
    }, { passive: false });
  }
  const gs = $("gridScroll"), mq = document.createElement("div");
  mq.className = "marquee-box"; document.body.appendChild(mq);
  let drag = null;
  gs.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || e.target.closest(".card")) return;
    drag = { x0: e.clientX, y0: e.clientY };
    mq.style.display = "block"; mq.style.left = e.clientX + "px"; mq.style.top = e.clientY + "px";
    mq.style.width = "0px"; mq.style.height = "0px";
  });
  document.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const x = Math.min(drag.x0, e.clientX), y = Math.min(drag.y0, e.clientY);
    const w = Math.abs(e.clientX - drag.x0), h = Math.abs(e.clientY - drag.y0);
    mq.style.left = x + "px"; mq.style.top = y + "px"; mq.style.width = w + "px"; mq.style.height = h + "px";
    if (w < 6 && h < 6) return;
    const mr = mq.getBoundingClientRect(), next = new Set();
    document.querySelectorAll("#grid .card").forEach((el) => {
      const cr = el.getBoundingClientRect();
      if (!(cr.right < mr.left || cr.left > mr.right || cr.bottom < mr.top || cr.top > mr.bottom)) next.add(+el.dataset.i);
    });
    if (next.size) { sel = next; cur = [...next][0]; patchGrid(); }
  });
  document.addEventListener("mouseup", () => {
    if (!drag) return;
    drag = null; mq.style.display = "none";
    if (sel.size) showCur();
  });
})();

/* ---- Hộp Cài đặt (bánh răng): Project mới (1 dòng) + thư mục Cache & SRT ---- */
(function initSettingsModal() {
  const modal = $("settingsModal"), btn = $("btnSettings");
  if (!modal || !btn) return;
  let defDataRoot = "";
  const shortTplName = (t) => /tiệc/i.test(t) && !/sáng|đầy đủ/i.test(t) ? "Chỉ tiệc" : (/đầy đủ/i.test(t) ? "Lễ sáng + Tiệc tối" : t);
  const addLutRow = (pref, path, hint) => {
    const list = $("setLutList");
    if (!list) return;
    const row = document.createElement("div");
    row.className = "inline8 lut-row";
    row.innerHTML = `<input class="inp lut-pref" style="width:92px" placeholder="VD: C0, DG" value="${esc(pref || "")}" title="${esc(hint || "Tiền tố đầu tên file")}">`
      + `<input class="inp flex1 lut-path" placeholder="File LUT (.cube / .3dl)" value="${esc(path || "")}">`
      + `<button class="btn lut-pick" type="button">Chọn...</button>`
      + `<button class="btn lut-del" type="button" title="Xóa dòng">✕</button>`;
    row.querySelector(".lut-pick").onclick = async () => {
      const r = await api().settings_pick_lut();
      if (r && r.path) row.querySelector(".lut-path").value = r.path;
      else if (r && r.error) status(r.error, "warn");
    };
    row.querySelector(".lut-del").onclick = () => row.remove();
    list.appendChild(row);
    return row;
  };
  const renderLutRows = (saved, detected) => {
    const list = $("setLutList");
    if (!list) return;
    list.innerHTML = "";
    const map = (saved && typeof saved === "object") ? saved : {};
    const seen = new Set();
    for (const d of (detected || [])) {
      if (!d || !d.prefix) continue;
      seen.add(d.prefix.toUpperCase());
      const key = Object.keys(map).find((k) => k.toUpperCase() === d.prefix.toUpperCase()) || d.prefix;
      addLutRow(key, map[key] || "", `${d.count} clip trong project`);
    }
    for (const [k, v] of Object.entries(map)) {
      if (!seen.has(k.toUpperCase())) addLutRow(k, v, "");
    }
    if (!list.children.length) addLutRow("", "", "");
  };
  const collectLutMap = () => {
    const out = {};
    const list = $("setLutList");
    if (!list) return out;
    for (const row of list.querySelectorAll(".lut-row")) {
      const p = (row.querySelector(".lut-pref").value || "").trim();
      const v = (row.querySelector(".lut-path").value || "").trim();
      if (p && v) out[p] = v;
    }
    return out;
  };
  btn.onclick = async () => {
    const r = await api().settings_get();
    defDataRoot = (r && r.data_root) || "";
    $("setCacheInp").value = (r && r.cache_root) || defDataRoot;
    $("setSrtInp").value = (r && r.srt_root) || "";
    if ($("setTplPathInp")) $("setTplPathInp").value = (r && r.templates_path) || "";
    const tplSel = $("setTplSel"), stSel = $("setStyleSel");
    if (tplSel && S && Array.isArray(S.templates)) {
      tplSel.innerHTML = S.templates.map((t) => `<option value="${esc(t)}">${esc(shortTplName(t))}</option>`).join("");
      tplSel.value = S.template || $("tplSel").value || (S.templates[0] || "");
    }
    if (stSel && S) stSel.value = S.shoot_style || "";
    renderLutRows(r && r.camera_luts, r && r.detected_prefixes);
    modal.classList.remove("hidden");
  };
  if ($("setLutAdd")) $("setLutAdd").onclick = () => {
    const row = addLutRow("", "", "");
    if (row) row.querySelector(".lut-pref").focus();
  };
  if ($("setRefreshThumbs")) $("setRefreshThumbs").onclick = async () => {
    const tplPath = $("setTplPathInp") ? $("setTplPathInp").value : null;
    const sv = await api().settings_save($("setCacheInp").value, $("setSrtInp").value, tplPath, collectLutMap());
    if (sv && sv.error) return status(sv.error, "warn");
    if (typeof LUT !== "undefined" && LUT.cache) LUT.cache.clear();
    const st = await api().thumbs_refresh();
    if (st && !st.error) setState(st);
    status("Đã xóa cache thumbnail của project này và đang tạo lại theo LUT mới.", "ok");
  };
  $("setCancel").onclick = () => modal.classList.add("hidden");
  $("setPickCache").onclick = async () => {
    const r = await api().settings_pick_dir();
    if (r && r.dir) $("setCacheInp").value = r.dir;
    else if (r && r.error) status(r.error, "warn");
  };
  $("setPickSrt").onclick = async () => {
    const r = await api().settings_pick_dir();
    if (r && r.dir) $("setSrtInp").value = r.dir;
    else if (r && r.error) status(r.error, "warn");
  };
  if ($("setPickTpl")) $("setPickTpl").onclick = async () => {
    const r = await api().settings_pick_dir();
    if (r && r.dir) $("setTplPathInp").value = r.dir + "\\templates.json";
    else if (r && r.error) status(r.error, "warn");
  };
  $("setReset").onclick = () => {
    $("setCacheInp").value = defDataRoot;
    $("setSrtInp").value = "";
    if ($("setTplPathInp")) $("setTplPathInp").value = "";
  };
  $("setSave").onclick = async () => {
    const tplPath = $("setTplPathInp") ? $("setTplPathInp").value : null;
    const r = await api().settings_save($("setCacheInp").value, $("setSrtInp").value, tplPath, collectLutMap());
    if (r && r.error) return status(r.error, "warn");
    if (typeof LUT !== "undefined" && LUT.cache) LUT.cache.clear();
    const tpl = $("setTplSel") ? $("setTplSel").value : "";
    const sty = $("setStyleSel") ? $("setStyleSel").value : "";
    if (S && sty !== (S.shoot_style || "")) {
      const st = await api().set_shoot_style(sty);
      if (st && !st.error) setState(st);
    }
    if (S && tpl && tpl !== S.template) {
      $("tplSel").value = tpl;
      if (S.n) {
        const sr = await api().suggest(tpl);
        if (sr && !sr.error) { setState(sr); fitView(); renderPage1(); }
      }
    } else if (S && S.n) {
      const st2 = await api().state();
      if (st2 && !st2.error) setState(st2);
    }
    modal.classList.add("hidden");
    status("Đã lưu cài đặt project & thư mục (Ctrl+Z để hoàn tác khi cần).", "ok");
  };
})();
