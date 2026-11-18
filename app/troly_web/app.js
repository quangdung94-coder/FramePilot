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
  const parts = [p.team ? p.team + " · " + p.name : p.name || INFO.project, p.date].filter(Boolean);
  if (S) parts.push(S.n + " file");
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
  $("undoBtn1").classList.toggle("hidden", !hasMoves);
  $("undoBtn2").classList.toggle("hidden", !hasMoves);
  if (S && $("styleSel").value !== (S.shoot_style || "") && document.activeElement !== $("styleSel")) $("styleSel").value = S.shoot_style || "";
  if (S) {
    $("tplSel").innerHTML = S.templates.map((t) => `<option${t === S.template ? " selected" : ""}>${esc(t)}</option>`).join("");
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
  S.stages.forEach((s, i) => { s.count = cnt[i]; s.range = fmt(s.start) + " – " + fmt(s.end); });
  S.outside = outside;
}

function fitView() {
  if (!S || !S.clips.length) return;
  const ms = [];
  S.clips.forEach((c) => { if (c.m0 != null) ms.push(c.m0, c.m1); });
  S.stages.forEach((s) => ms.push(s.start, s.end));
  if (!ms.length) return;
  const a = Math.min(...ms), b = Math.max(...ms);
  view = [Math.floor((a - 15) / 60) * 60, Math.ceil((b + 15) / 60) * 60];
  fitted = true;
}

function pct(m) { return ((m - view[0]) / (view[1] - view[0]) * 100).toFixed(3) + "%"; }

function renderPage1() {
  const st = S ? S.stages : [];
  $("stageCount").textContent = st.length + " giai đoạn";
  $("stageList").innerHTML = st.map((s, i) => `
    <div class="stage${editIdx === i ? " open" : ""}" data-i="${i}">
      <div class="stage-row">
        <div class="stage-bar" style="background:${s.color}"></div>
        <div class="stage-txt"><span class="stage-name" title="Bấm đúp để đổi tên giai đoạn">${esc(s.name)}</span><span class="dim12">${esc(s.range)}</span></div>
        <span class="chip">${s.count} file</span>
      </div>
      ${editIdx === i ? `<div class="stage-edit">
        <label class="full">Tên giai đoạn<input class="inp" data-f="name" value="${esc(s.name)}"></label>
        <label>Bắt đầu<input class="inp" data-f="start_txt" value="${fmt(s.start)}"></label>
        <label>Kết thúc<input class="inp" data-f="end_txt" value="${fmt(s.end)}"></label>
        <label class="full">Bin con (cách nhau dấu phẩy, phím 1–9 theo thứ tự; muốn ĐỔI TÊN một bin con thì bấm đúp tên bin ở bước 2)<input class="inp" data-f="bins" value="${esc(s.bins.map((b) => b.name).filter((b) => b !== "Khác").join(", "))}"></label>
        <div class="row-end"><button class="btn-del" data-act="del">Xóa giai đoạn</button><button class="btn" data-act="save" style="height:32px">Lưu</button></div>
      </div>` : ""}
    </div>`).join("");
  // lệch giờ theo máy
  const cams = S ? S.cameras : [];      // một máy thì lệch giờ không đổi gì (giai đoạn chỉnh tay): chỉ hiện khi >= 2 máy
  $("camBox").innerHTML = cams.length > 1 ?`<b style="color:var(--dim2)">Lệch giờ theo máy (giây)</b>` + cams.map((c) =>
    `<div class="cam-row"><span>${esc(c.cam)} · ${c.n} file</span><input class="inp" data-cam="${esc(c.cam)}" value="${c.off || 0}"></div>`).join("") : "";
  $("from").value = fmt(view[0]); $("to").value = fmt(view[1]);
  renderTimeline();
  renderBinGrid();
}

function renderTimeline() {
  const W = $("bands").clientWidth || 800, span = view[1] - view[0];
  const step = [15, 30, 60, 120, 180, 240, 360].find((s) => s / span * W >= 64) || 720;
  let h = "";
  for (let t = Math.ceil(view[0] / step) * step; t <= view[1]; t += step) {
    const left = (t - view[0]) / span * 100;
    h +=`<span style="left:${left.toFixed(3)}%">${fmt(t)}</span>`;
  }
  $("ruler").innerHTML = h;
  let d = "";
  if (S) for (const c of S.clips) {
    if (c.m0 == null || c.m1 < view[0] || c.m0 > view[1]) continue;
    d += `<i style="left:${pct(c.m0)}"></i>`;             // vạch mảnh 2 px như demo, đặt ở giờ bấm quay
  }
  $("density").innerHTML = d;
  $("bands").innerHTML = (S ? S.stages : []).map((s, i) => `
    <div class="band" data-i="${i}" style="left:${pct(s.start)};width:${((s.end - s.start) / span * 100).toFixed(3)}%;background:${s.color}26;border-color:${s.color}">
      <div class="h l" data-mode="start" style="background:${s.color}"></div><div class="h r" data-mode="end" style="background:${s.color}"></div>
      <span class="n">${esc(s.name)}</span><span class="r">${esc(s.range)}</span>
    </div>`).join("");
  $("gapText").textContent = !S ? "Chưa đọc clip" : S.gap ? `Nghỉ quay ${S.gap.text} (không có file)` : "Không có khoảng nghỉ quay";
  $("sumText").textContent = S ? `${S.n} file · ${S.stages.length} giai đoạn · ${S.outside} file ngoài giai đoạn` +
    (S.n_manual ? ` · ${S.n_manual} file chọn tay (giữ giai đoạn khi kéo giờ)` : "") +
    (S.new_n ? ` · ${S.new_n} file MỚI chưa phân loại` : "") : "";
  $("clearManual").classList.toggle("hidden", !(S && S.n_manual));
}

function renderBinGrid() {
  if (!S || !S.stages.length) { $("binGrid").innerHTML = `<div class="empty">Bấm "Đọc clip" để đọc giờ quay và chia giai đoạn.</div>`; return; }
  let h = S.stages.map((s) => `<div class="bin-card">${folder(s.color, 20)}<span class="t">${esc(s.bin)}</span><span class="dim12">${s.count}</span></div>`).join("");
  if (S.outside) h += `<div class="bin-card">${folder("#6A6A72", 20)}<span class="t" style="color:var(--dim)">Giữ nguyên chỗ cũ</span><span class="dim12">${S.outside}</span></div>`;
  $("binGrid").innerHTML = h;
}

/* kéo khối giai đoạn / trượt / phóng */
let drag = null;
$("bands").addEventListener("pointerdown", (e) => {
  const band = e.target.closest(".band"); if (!band) return;
  const i = +band.dataset.i, s = S.stages[i];
  drag = { mode: e.target.dataset.mode || "move", i, x: e.clientX, a: s.start, b: s.end };
  band.setPointerCapture(e.pointerId);
  e.preventDefault();
});
$("density").addEventListener("pointerdown", (e) => {
  drag = { mode: "pan", x: e.clientX, v: view.slice() };
  $("density").setPointerCapture(e.pointerId);
});
document.addEventListener("pointermove", (e) => {
  hoverLine(e);
  if (!drag) return;
  const W = $("bands").clientWidth, dm = (e.clientX - drag.x) / W * (view[1] - view[0]);
  if (drag.mode === "pan") { view = [drag.v[0] - dm, drag.v[1] - dm]; renderPage1(); return; }
  const s = S.stages[drag.i], q = Math.round(dm * 6) / 6;     // bước 10 giây
  if (drag.mode === "move") { s.start = drag.a + q; s.end = drag.b + q; }
  else if (drag.mode === "start") s.start = Math.min(drag.a + q, s.end);
  else s.end = Math.max(drag.b + q, s.start);
  drag.moved = true;
  localAssign(); renderPage1();
});
document.addEventListener("pointerup", () => {
  if (drag && drag.mode === "pan") saveUi();                // trượt thanh giờ xong: lưu khoảng đang xem
  if (drag && drag.mode !== "pan" && drag.moved) {
    const s = S.stages[drag.i];
    api().set_stage(drag.i, { start: s.start, end: s.end }).then(setState);
  }
  drag = null;
});
function hoverLine(e) {
  const d = $("density"), r = d.getBoundingClientRect();
  const old = d.querySelector(".hover"); if (old) old.remove();
  if (page !== 1 || e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
  const m = view[0] + (e.clientX - r.left) / r.width * (view[1] - view[0]);
  const el = document.createElement("div"); el.className = "hover"; el.style.left = (e.clientX - r.left) + "px";
  el.innerHTML = `<b>${fmt(m)}</b>`; d.appendChild(el);
}
$("tlCard").addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = $("bands").getBoundingClientRect();
  const m = view[0] + (e.clientX - r.left) / r.width * (view[1] - view[0]);
  const k = e.deltaY < 0 ? 0.8 : 1.25, na = m - (m - view[0]) * k, nb = m + (view[1] - m) * k;
  if (nb - na < 5) return;
  view = [na, nb]; renderPage1(); saveUi();
}, { passive: false });
$("tlCard").addEventListener("dblclick", () => { fitView(); renderPage1(); saveUi(); });
["from", "to"].forEach((id) => $(id).addEventListener("change", () => {
  const a = parseHM($("from").value, Math.floor(view[0] / 1440)), b = parseHM($("to").value, Math.floor(view[0] / 1440));
  if (a === null || b === null || b <= a) { status("Giờ hiển thị không hợp lệ (viết kiểu 06:00).", "warn"); renderPage1(); return; }
  view = [a, b]; renderPage1(); saveUi();
}));
window.addEventListener("resize", () => { if (S) renderTimeline(); });

/* danh sách giai đoạn */
let nameClick = { i: -1, t: 0, prev: null };
$("stageList").addEventListener("click", (e) => {
  const card = e.target.closest(".stage"); if (!card) return;
  const i = +card.dataset.i, act = e.target.dataset.act;
  if (act === "save") return saveStage(i, card);
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
  if (e.key === "Enter" && e.target.dataset.f) saveStage(+e.target.closest(".stage").dataset.i, e.target.closest(".stage"));
});
async function saveStage(i, card) {
  const f = {};
  card.querySelectorAll("[data-f]").forEach((el) => { f[el.dataset.f] = el.value; });
  f.bins = f.bins.split(",").map((x) => x.trim()).filter(Boolean);
  const old = S.stages[i].name;
  if (f.name !== undefined && f.name.trim() !== old) {            // đổi tên qua đường có kiểm tên (chỉ trong kế hoạch của panel)
    if (!(await doRename("stage", i, old, f.name))) return;
    f.name = S.stages[i].name;
  }
  api().set_stage(i, f).then((st) => { if (st.error) return status(st.error, "warn"); editIdx = null; setState(st); });
}
$("camBox").addEventListener("change", (e) => {
  const c = e.target.dataset.cam; if (c === undefined) return;
  api().set_offset(c, e.target.value).then(setState);
});
$("clearManual").onclick = async () => {
  if (await ask("Bỏ chọn tay", `Bỏ chọn tay của ${S.n_manual} clip? Các clip này quay về giai đoạn tính theo giờ quay.<br>(Nhãn bin con đã xếp vẫn giữ, chỉ có hiệu lực khi clip về đúng giai đoạn của nhãn.)`, "Bỏ chọn tay")) {
    setState(await api().clear_manual()); status("Đã bỏ chọn tay.", "ok");
  }
};
$("addStage").onclick =() => api().add_stage().then((st) => { editIdx = st.stages.length - 1; setState(st); });
$("suggestBtn").onclick = async () => {
  if (!S || !S.n) return status('Hãy bấm "Đọc clip" trước.', "warn");
  if (S.stages.length && !(await ask("Gợi ý lại giai đoạn", "Thay các giai đoạn đang có bằng gợi ý mới theo khoảng nghỉ quay dài nhất?<br>(Nhãn phân loại đã ghi vẫn giữ.)", "Gợi ý lại"))) return;
  setState(await api().suggest($("tplSel").value)); fitView(); renderPage1();
};
$("saveTpl").onclick = async () => {
  if (!S || !S.stages.length) return;
  const name = await ask("Lưu mẫu giờ cho đám sau", `Tên mẫu (trùng tên thì ghi đè):<br><input id="tplName" class="inp" style="width:100%;margin-top:8px" value="${esc(S.template)}">`, "Lưu mẫu", () => $("tplName").value);
  if (name) { setState(await api().save_template(name)); status(`Đã lưu mẫu "${name}".`, "ok"); }
};
$("loadBtn").onclick = () => { const b = $("binSel").value; if (b) { fitted = false; api().load(b); } };

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
    Trợ lý không tự xóa bin, anh xóa tay trong DaVinci nếu không cần.</p>` : "";
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
/* cột MEDIA POOL: bin giai đoạn (⇧số) và bin con (số) */
function renderPool() {
  let h = S.stages.map((s, i) => {
    // khi kéo tới: mở THÊM bin con của bin đang trỏ, không gập bin đang mở (cây không dịch dưới con trỏ)
    const open = i === gStage || i === poolOpen;
    return `<div class="pool-stage"><div class="pool-row${i === gStage && gSub === null ? " on" : ""}${i === gStage && gSub !== null ? " parent" : ""}" data-stage="${i}" title="Bấm để xem cả giai đoạn (chỉ xem). Bấm đúp tên để đổi tên.">${folder(s.color, 18)}<span class="t">${esc(s.bin)}</span><span class="dim12">${s.count}</span>${i < 9 ? `<span class="k" title="Shift+${i + 1}: chuyển clip đang chọn sang giai đoạn này">⇧${i + 1}</span>` : ""}</div>` +
      (open ? `<div class="pool-subs"><div class="sub-none${i === gStage && gSub === NONE ? " on" : ""}" data-stage="${i}" title="Bấm để xem clip chưa có nhãn (chỉ xem)"><span class="sq" style="background:var(--dim2);opacity:.5"></span><span class="t">Chưa xếp</span><span class="dim12">${s.none.length}</span></div>${s.bins.map((b) => `<div class="sub${i === gStage && gSub === b.name ? " on" : ""}" data-stage="${i}" data-bin="${esc(b.name)}" title="Bấm để xem clip của bin này (chỉ xem). Bấm đúp tên để đổi tên. Muốn chuyển clip vào: phím ${b.key || "số"} hoặc kéo thả"><span class="sq" style="background:${b.color}"></span><span class="t">${esc(b.name)}</span><span class="dim12">${b.count}</span>${b.key ? `<span class="k" title="${i === gStage ? "Phím " + b.key : "Shift+" + (i + 1) + " rồi " + b.key}">${b.key}</span>` : ""}</div>`).join("")}
        ${i === gStage ? `<button class="sub-add" id="subAdd">+ Bin mới</button>` : ""}</div>` : "") + `</div>`;
  }).join("");
  if (S.outside) h += `<div class="pool-stage"><div class="pool-row${gStage === -1 ? " on" : ""}" data-stage="-1">${folder("#6A6A72", 18)}<span class="t" style="color:var(--dim)">Ngoài giai đoạn</span><span class="dim12">${S.outside}</span></div></div>`;
  $("pool").innerHTML = h;
}
function renderPage2b(s, nk, rebuild) {
  $("gridHint").textContent = s ? `Bấm bin bên trái để XEM. Muốn xếp clip: kéo thumbnail vào bin, hoặc phím số 1–${nk}; Shift+số chuyển sang giai đoạn khác. Mỗi lần anh xếp, AI ghi lại để học.`
    : "Clip ngoài giai đoạn: Shift+số hoặc kéo thả vào bin giai đoạn bên trái để chuyển.";
  $("starCount").textContent = S.n_starred || 0;
  $("doneText").textContent = s ? `${s.done} / ${s.count} đã xếp` : "";
  $("keyList").innerHTML = (s ? s.bins.filter((b) => b.key).map((b) => `<div class="key-row" data-bin="${esc(b.name)}"><span class="l"><i style="background:${b.color}"></i>${esc(b.name)}</span><span class="r">phím ${b.key} · ${b.count} clip</span></div>`).join("") : "") +
    `<div class="key-stages">${S.stages.slice(0, 9).map((x, i) => `<span class="ks" data-stage="${i}" title="Chuyển clip đang chọn sang ${esc(x.bin)}"><b>⇧${i + 1}</b> ${esc(x.name)}</span>`).join("")}</div>`;
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
  if (b && c.label_by === "ai_auto") return `<span class="tag aiauto" title="AI xếp (chưa phải anh xếp, không tính vào dữ liệu AI học): ${esc(b.name)}" style="border-color:${b.color}">AI xếp · ${esc(b.name)}</span>`;
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
  // BẤM bin chỉ để XEM (như mở thư mục trong Windows): không gọi api().label / move, nhãn và giai đoạn không đổi.
  if (row) { viewBin(+row.dataset.stage, null); return; }
  const none = e.target.closest(".sub-none");
  if (none) { viewBin(+none.dataset.stage, NONE); return; }
  const sub = e.target.closest(".sub");
  if (sub) { viewBin(+sub.dataset.stage, sub.dataset.bin); return; }
  if (e.target.id === "subAdd") {
    const inp = document.createElement("input");
    inp.className = "inp sub-input"; inp.placeholder = "Tên bin mới, Enter để thêm";
    e.target.replaceWith(inp); inp.focus();
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && inp.value.trim()) api().add_bin(gStage, inp.value).then(setState);
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
    S.stages.map((x, k) => `<div class="ctx-i${k === gStage ? " off" : ""}" data-stage="${k}"><i style="background:${x.color}"></i>${esc(x.bin)}<span>${k < 9 ? "Shift+" + (k + 1) : ""}</span></div>`).join("") +
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

/* Dấu sao ★ (phím J): chọn nhiều clip thì đặt đồng loạt. Có clip chưa sao -> gắn sao cho tất cả; tất cả đã sao -> bỏ sao. */
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
  if (!n) return status("Chưa có clip nào có sao ★. Bấm phím J để gắn sao.", "warn");
  const ok = await ask("Đưa clip có sao lên timeline",
    `<p>Sẽ TẠO một timeline MỚI trong DaVinci gồm <b>${n}</b> clip có sao ★, xếp theo giai đoạn rồi theo giờ quay.</p><p>Timeline đang có không bị sửa. Điểm In/Out sẽ chỉnh lại trong DaVinci sau.</p>`, "Tạo timeline mới");
  if (!ok) return;
  const r = await api().append_starred();
  if (r && r.error) status(r.error, "warn");
}
$("appendStarBtn").onclick = () => appendStarred();
$("revealBtn").onclick = () => reveal();
function reveal() { if (items[cur]) api().reveal(items[cur].uid).then((n) => status("Đã mở " + n + " trong Media Pool của DaVinci.", "info")); }

/* Bàn phím bước 2: đọc event.code (Digit1..9, Numpad1..9), KHÔNG dùng event.key: Shift+3 ra "#",
   và Unikey kiểu VNI dùng phím số. Bỏ qua phím khi đang gõ trong ô nhập chữ. */
let pending = null;                                   // Shift+số đang chờ số bin con: KHÔNG hết hạn theo giờ
function digitOf(e) { const m = /^(Digit|Numpad)([0-9])$/.exec(e.code || ""); return m ? +m[2] : null; }
/* Shift+số: chuyển clip đang chọn sang giai đoạn đó NGAY, rồi chờ số bin con. Chỉ kết thúc khi: bấm số bin con (xếp xong),
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
  if (!$("modal").classList.contains("hidden")) {
    if (e.key === "Escape") $("mNo").click(); else if (e.key === "Enter") $("mYes").click();
    return;
  }
  if (e.key === "Escape") { $("ctx").classList.add("hidden"); if (pending) { cancelPending(); status("Đã thôi chờ bin con (clip giữ nguyên giai đoạn mới).", "info"); } return; }
  if (page === 4) { lnKey(e); return; }
  if (page === 3) {                                                  // Bước 3: chỉ J, ↑/↓ đổi clip, Enter; số KHÔNG xếp bin ở đây
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.code === "KeyJ" && !e.shiftKey) { e.preventDefault(); toggleStar(); return; }
    if (e.code === "ArrowUp" || e.code === "ArrowDown") { e.preventDefault(); moveCur(cur + (e.code === "ArrowUp" ? -1 : 1)); return; }
    if (e.code === "Enter") { e.preventDefault(); reveal(); }
    return;
  }
  if (page !== 2 || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.code === "KeyJ" && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) { cancelPending(); e.preventDefault(); toggleStar(); return; }
  const d = digitOf(e);
  if (pending && d !== null && !e.ctrlKey && !e.altKey) {          // số thứ hai sau Shift+số: vào bin con
    e.preventDefault();
    if (d === 0) return finishPending(null);
    const b = S.stages[pending.si].bins.find((x) => x.key === String(d));
    if (b) finishPending(b.name);
    return;
  }
  if (d !== null && e.shiftKey && !e.ctrlKey && !e.altKey) {       // Shift+số: sang giai đoạn số đó rồi chờ bin con
    e.preventDefault();
    if (d >= 1 && d <= S.stages.length && items.length) startPending(d - 1);
    return;
  }
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
  $("starToggleBtn").textContent = c.star ? "★ Bỏ sao (phím J)" : "☆ Gắn sao (phím J)";
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
  const showImg = (src) => { const v = $("preview").querySelector("video"), lc = $("preview").querySelector("canvas.pv-lut"); $("preview").innerHTML = `<img src="${src}">`; if (v) $("preview").appendChild(v); if (lc) $("preview").appendChild(lc); };
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
  status(e.target.value ? "Đã chọn kiểu quay " + (e.target.value === "psc" ? "PSC" : "Truyền thống") + ": chỉ đổi gợi ý màu xanh, In/Out anh đặt tay vẫn thắng." : "Đã bỏ chọn kiểu quay: gợi ý như mặc định.", "ok");
};
