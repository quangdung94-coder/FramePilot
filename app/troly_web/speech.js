/* speech.js - BƯỚC 4 · LỜI NÓI, tầng 1: bản đồ (ADR-0014). Chỉ vẽ và nhận thao tác; chép lời, kho dữ liệu, In/Out gợi ý ở
   Python (troly_api.speech_*). Dùng chung $, api, S, esc, status, setState, page từ app.js. Chữ chép lời chỉ hiện trên màn hình. */
"use strict";

const LN = { rows: [], all: [], summary: null, info: null, sel: null, pick: new Set(), anchor: null, stage: "all", sub: "all", onlyStar: false, onlyKey: false, min20: false, hideBad: false, find: "",
  detail: null, edit: null, run: null, lastRefresh: 0, timer: null, vid: null, mediaUid: null };
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
function clipMeta(uid) { return (window.S && S.clips) ? S.clips.find((c) => c.uid === uid) : null; }
const inStage = (r) => {
  if (LN.stage !== "all" && stageOf(r) !== +LN.stage) return false;
  const cm = clipMeta(r.uid);
  if (LN.onlyStar && !(cm ? cm.star : r.star)) return false;
  if (LN.hideBad && r.suspect && !r.headline) return false;
  if (LN.sub !== "all") {
    const lb = cm ? (cm.label || "") : "";
    if (LN.sub === "__none__") { if (lb) return false; }
    else if (lb !== LN.sub) return false;
  }
  return true;
};

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
  const subSel = $("lnSub");
  if (subSel) {
    const bins = [];
    const srcStages = LN.stage === "all" ? stages : (stages[+LN.stage] ? [stages[+LN.stage]] : []);
    srcStages.forEach((s) => (s.bins || []).forEach((b) => { if (!bins.includes(b.name)) bins.push(b.name); }));
    const sHtml = ['<option value="all">Tất cả bin con</option>', '<option value="__none__">Chưa xếp bin con</option>']
      .concat(bins.map((b) => `<option value="${esc(b)}">${esc(b)}</option>`)).join("");
    if (subSel.dataset.sig !== sHtml) { subSel.innerHTML = sHtml; subSel.dataset.sig = sHtml; }
    if (LN.sub !== "all" && LN.sub !== "__none__" && !bins.includes(LN.sub)) LN.sub = "all";
    subSel.value = LN.sub;
  }
  const st = stages[+LN.stage];
  $("lnTitle").textContent = LN.stage === "all" ? "Lời nói · Cả project" : (st ? `Lời nói · ${st.name} · ${st.range || ""}` : "Lời nói · Ngoài mọi giai đoạn");
  if ($("lnStarOnly")) $("lnStarOnly").setAttribute("aria-pressed", LN.onlyStar);
  if ($("lnHideBad")) $("lnHideBad").setAttribute("aria-pressed", LN.hideBad);
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
    return `<button class="ln-row${r.uid === LN.sel ? " on" : ""}${LN.pick.has(r.uid) ? " pk" : ""}" data-uid="${esc(r.uid)}">
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

function lnEnsureMedia(r) {
  const lt = $("lnThumb");
  if (!lt || !r) return;
  if (LN.mediaUid === r.uid) return;
  LN.mediaUid = r.uid;
  const src = thumbs[r.uid];
  lt.innerHTML = src ? `<img src="${src}" draggable="false">` : "";
  lt.classList.remove("hidden");
  $("lnPlayBtn").textContent = "▶";
  $("lnTime").textContent = `0:00 / ${mmss(r.dur)}`;
  $("lnPlayNote").textContent = "";
  if (LN.vid) { try { LN.vid.pause(); LN.vid.removeAttribute("src"); LN.vid.load(); } catch (e) {} LN.vid = null; }
  if (typeof lutDetachEl === "function" && lt) lutDetachEl(lt);
  if (!src && typeof api === "function") {
    api().want_thumbs([r.uid]).then((ready) => {
      if (ready && ready[r.uid]) { thumbs[r.uid] = ready[r.uid]; if (LN.sel === r.uid && lt && !lt.querySelector("img")) lt.insertAdjacentHTML("afterbegin", `<img src="${ready[r.uid]}" draggable="false">`); }
    });
  }
  if (typeof api === "function") {
    api().play_info(r.uid).then((pi) => {
      if (LN.sel !== r.uid) return;
      if (!pi || pi.error) { $("lnPlayNote").textContent = (pi && pi.error) || ""; return; }
      const v = document.createElement("video");
      v.preload = "auto"; v.playsInline = true; v.crossOrigin = "anonymous"; v.src = pi.url; v.style.opacity = "0";
      v.addEventListener("loadeddata", () => { if (LN.sel === r.uid) v.style.opacity = "1"; });
      v.addEventListener("play", () => { if ($("lnPlayBtn")) $("lnPlayBtn").textContent = "❚❚"; });
      v.addEventListener("pause", () => { if ($("lnPlayBtn")) $("lnPlayBtn").textContent = "▶"; });
      v.addEventListener("timeupdate", () => {
        if (LN.sel !== r.uid) return;
        const dur = v.duration || r.dur || 1;
        $("lnTime").textContent = `${mmss(v.currentTime)} / ${mmss(dur)}`;
        $("lnWHead").style.left = Math.min(100, (v.currentTime / dur) * 100).toFixed(2) + "%";
      });
      v.addEventListener("error", () => { $("lnPlayNote").textContent = "Không giải mã được video trực tiếp"; });
      lt.appendChild(v); LN.vid = v;
      if (typeof lutAttachEl === "function" && typeof S !== "undefined" && S && Array.isArray(S.clips)) {
        const cl = S.clips.find((x) => x.uid === r.uid);
        if (cl) lutAttachEl(cl, v, lt);
      }
    });
    api().wave(r.uid).then((w) => {
      if (LN.sel !== r.uid) return;
      if (w && w.pending) { setTimeout(() => { if (LN.sel === r.uid) { LN.mediaUid = null; lnEnsureMedia(r); } }, 450); return; }
      const cv = $("lnWaveCv"); if (!cv || !w || !w.peaks) return;
      const g = cv.getContext("2d"), W = cv.width = cv.clientWidth || 320, H = cv.height = cv.clientHeight || 42;
      g.clearRect(0, 0, W, H); g.fillStyle = "#5B9BF5";
      const pk = w.peaks, n = pk.length;
      for (let i = 0; i < W; i += 2) {
        const v = pk[Math.min(n - 1, Math.floor(i / W * n))] / 100;
        const h = Math.max(2, v * (H - 4));
        g.fillRect(i, (H - h) / 2, 1.5, h);
      }
    });
  }
}

function renderRight() {
  const r = curRow(), d = LN.detail;
  if (!r) {
    $("lnName").textContent = "Chọn một clip"; $("lnMeta").textContent = ""; $("lnBar").innerHTML = ""; $("lnDurEnd").textContent = "";
    if ($("lnThumb")) { $("lnThumb").innerHTML = ""; $("lnThumb").classList.add("hidden"); }
    LN.mediaUid = null;
    $("lnSugg").classList.add("hidden"); $("lnLines").innerHTML = ""; renderExportBtns(); return;
  }
  lnEnsureMedia(r);
  const fps = (d && d.fps) || r.fps || 25;
  $("lnName").textContent = r.name;
  $("lnMeta").innerHTML = `${esc(r.time || "--:--:--")} · ${mmss(r.dur)} · <button class="btn-link ln-lang" id="lnLangBtn" title="Bấm để đổi ngôn ngữ của clip này (vi ⇄ en); lần chép lại sẽ giữ lựa chọn của bạn">${esc(r.silent ? "–" : (r.lang || "–"))}</button>`;
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
    $("lnSuggTitle").textContent = { manual: "Đoạn bạn đã đặt (lưu trong panel, chưa ghi vào DaVinci)", davinci: "Đoạn đã đặt In / Out trong DaVinci, giờ theo timecode của file gốc" }[e.src] || "Đoạn gợi ý, giờ theo timecode của file gốc";
    $("lnSuggNote").textContent = e.dirty ? "Đã kéo mép khung. Bấm “Đặt In / Out” để lưu vào kế hoạch của panel." : "Kéo mép khung trắng để chỉnh. Bạn đặt tay thì lấy theo bạn.";
  }
  const lines = (d && d.lines) || [];
  const visLines = LN.hideBad ? lines.filter((l) => !l.why.length) : lines;
  $("lnLines").innerHTML = !d ? '<span class="dim13" style="padding:8px">Đang tải...</span>'
    : visLines.length ? visLines.map((l) => {
      const inside = e && l.t0 >= e.in_s - 0.01 && l.t1 <= e.out_s + 0.01;
      return `<div class="ln-line${l.keys.length && !l.why.length ? " key" : ""}${inside ? " in" : ""}${l.why.length ? " bad" : ""}" data-t="${l.t0}"><span class="t">${fmtSec(l.t0)}</span><span class="x">${esc(l.text)}${l.why.length ? " · nghi sai" : ""}</span></div>`;
    }).join("")
    : `<span class="dim13" style="padding:8px">${r.silent ? "Clip này không có tiếng nói, chỉ có tiếng nền." : (lines.length ? "Các câu đều nghi sai (đang bật Ẩn câu sai)." : "Có tiếng nói nhưng Whisper không ra chữ.")}</span>`;
  $("lnStar").textContent = ((d ? d.star : r.star) ? "Bỏ sao (P)" : "Gắn sao (P)");
  renderExportBtns();
}

function renderExportBtns() {
  const n = LN.pick.size;
  $("lnExpSel").textContent = `SRT phần đã chọn (${n})`;
  $("lnExpSel").disabled = !n;
  $("lnExpOne").disabled = !curRow() || curRow().silent;
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
  LN.sub = "all";
  const f = LN.rows.find(inStage);
  LN.sel = f ? f.uid : null; LN.detail = null; LN.edit = null;
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
};
if ($("lnSub")) $("lnSub").onchange = (e) => {
  LN.sub = e.target.value;
  const f = LN.rows.find(inStage);
  LN.sel = f ? f.uid : null; LN.detail = null; LN.edit = null;
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
};
if ($("lnStarOnly")) $("lnStarOnly").onclick = () => {
  LN.onlyStar = !LN.onlyStar;
  const f = LN.rows.find(inStage);
  LN.sel = f ? f.uid : null; LN.detail = null; LN.edit = null;
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
};
if ($("lnPlayBtn")) $("lnPlayBtn").onclick = () => {
  if (!LN.vid) return;
  if (LN.vid.paused) LN.vid.play().catch(() => {}); else LN.vid.pause();
};
if ($("lnWaveBox")) $("lnWaveBox").addEventListener("mousemove", (ev) => {
  const r = curRow(); if (!r || !LN.vid || ev.buttons) return;
  const rect = $("lnWaveBox").getBoundingClientRect(), dur = LN.vid.duration || r.dur || 1;
  const t = Math.max(0, Math.min(dur, (ev.clientX - rect.left) / rect.width * dur));
  LN.vid.currentTime = t;
});
$("lnLines").addEventListener("click", (ev) => {
  const ln = ev.target.closest(".ln-line"); if (!ln || !LN.vid) return;
  LN.vid.currentTime = +ln.dataset.t || 0;
  LN.vid.play().catch(() => {});
});
$("lnKey").onclick = () => { LN.onlyKey = !LN.onlyKey; lnRefresh(); };
$("lnMin").onclick = () => { LN.min20 = !LN.min20; lnRefresh(); };
if ($("lnHideBad")) $("lnHideBad").onclick = () => {
  LN.hideBad = !LN.hideBad;
  const cur = curRow();
  if (LN.hideBad && (!cur || !inStage(cur))) {
    const f = LN.rows.find(inStage);
    LN.sel = f ? f.uid : null; LN.detail = null; LN.edit = null;
  }
  renderSpeech();
  if (LN.sel) lnLoadDetail(LN.sel);
};
$("lnFind").oninput = (e) => { clearTimeout(LN.timer); LN.find = e.target.value; LN.timer = setTimeout(lnRefresh, 250); };
$("lnRows").onclick = (e) => {
  const b = e.target.closest(".ln-row"); if (!b) return;
  const uid = b.dataset.uid, rows = LN.rows.filter(inStage).map((r) => r.uid);
  if (e.shiftKey && LN.anchor && rows.includes(LN.anchor)) {                 // Shift + bấm: chọn một dải
    const a = rows.indexOf(LN.anchor), z = rows.indexOf(uid);
    LN.pick = new Set(rows.slice(Math.min(a, z), Math.max(a, z) + 1));
  } else if (e.ctrlKey || e.metaKey) {                                      // Ctrl + bấm: thêm/bớt một clip
    if (LN.pick.has(uid)) LN.pick.delete(uid); else LN.pick.add(uid);
    LN.anchor = uid;
  } else { LN.pick = new Set(); LN.anchor = uid; }
  lnSelect(uid);
};

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

/* Ghi vào DaVinci: dùng chung hộp xác nhận + sao lưu + Hoàn tác của player.js (ADR-0016). Chỉ clip có In/Out ĐẶT TAY mới ghi. */
$("lnWrite").onclick = () => {
  const ids = LN.pick && LN.pick.size ? [...LN.pick] : (LN.sel ? [LN.sel] : []);
  if (!ids.length) return status("Chưa chọn clip nào.", "warn");
  plWrite("selected", ids);
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
  if (e.code === "Space") { e.preventDefault(); if (LN.vid) { if (LN.vid.paused) LN.vid.play().catch(() => {}); else LN.vid.pause(); } return; }
  if (e.ctrlKey && e.code === "KeyA") { e.preventDefault(); LN.pick = new Set(LN.rows.filter(inStage).map((r) => r.uid)); renderRows(); renderExportBtns(); return; }
  if (e.code === "KeyP" && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) { e.preventDefault(); lnToggleStar(); return; }
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

/* ------------------------------------------------------------------ xuất SRT (mục A4) */
async function lnExport(scope, uids) {
  status("Chọn thư mục để lưu file SRT...", "info");
  const r = await api().speech_export(scope, uids || [], null);
  if (r && r.cancel) return status("Đã hủy xuất SRT.", "info");
  if (r && r.error) return status(r.error, "warn");
  const lines = r.files.reduce((a, f) => a + f.lines, 0);
  status(`Đã xuất ${r.files.length} file SRT (${lines} dòng${r.skipped_lines ? `, bỏ ${r.skipped_lines} dòng nghi bịa` : ""}) vào ${r.dir}.`, "ok");
}
$("lnExport").onclick = () => lnExport("stages");
$("lnExpOne").onclick = () => { const r = curRow(); if (r) lnExport("clip", [r.uid]); };
$("lnExpSel").onclick = () => lnExport("selection", [...LN.pick]);

/* ------------------------------------------------------------------ PHÂN TÍCH CẢ PROJECT + TẮT MÁY (ADR-0017) */
const AN = { running: false, text: "" };
function renderAnalyze() {
  $("anRun").textContent = AN.running ? "Dừng phân tích" : "Phân tích cả project";
  $("anShut").disabled = AN.running;                              // không đổi ý giữa chừng bằng ô tick (muốn dừng thì bấm Dừng)
  if (AN.text) $("anText").textContent = AN.text;
}
$("anRun").onclick = async () => {
  if (AN.running) { await api().analyze_stop(); status("Đang dừng phân tích. Máy sẽ KHÔNG tắt.", "info"); return; }
  if (!LN.info || !LN.info.dir) { await lnPick(); if (!LN.info || !LN.info.dir) return; }
  if (!S || !S.n) return status("Chưa có clip. Hãy sang bước 1 và bấm “Đọc clip” trước.", "warn");
  const sd = $("anShut").checked;
  const body = `<p>Trợ lý sẽ chép lời cả bin rồi làm sẵn thumbnail cho <b>${S.n}</b> clip. Có thể mất vài giờ. Clip đã chép mà file không đổi được bỏ qua. Không ghi gì vào DaVinci và không đụng file quay.</p>` +
    (sd ? `<p><b>Khi xong máy sẽ TẮT.</b> Trợ lý lưu project DaVinci, rồi đếm ngược 2 phút (có nút Huỷ) trước khi tắt. Nếu bị dừng giữa chừng, chép lời lỗi hoặc lưu lỗi thì KHÔNG tắt máy.</p>`
      : `<p>Máy sẽ không tự tắt.</p>`);
  if (!(await ask("Phân tích cả project", body, sd ? "Bắt đầu, tắt máy khi xong" : "Bắt đầu"))) return;
  const r = await api().analyze_start(sd);
  if (r && r.error) return status(r.error, "warn");
  AN.running = true; AN.text = "Đang chép lời cả bin..."; renderAnalyze();
  status(`Bắt đầu phân tích ${r.count} clip` + (sd ? ", sẽ tắt máy khi xong." : "."), "info");
};
$("shutCancel").onclick = async () => { await api().analyze_cancel_shutdown(); $("shut").classList.add("hidden"); status("Đã huỷ tắt máy.", "ok"); };
function anEvent(kind, d) {
  if (kind === "analyze_phase") { AN.text = d.text; AN.running = d.phase !== "done"; renderAnalyze(); status(d.text, "info"); }
  else if (kind === "analyze_thumbs") { AN.text = `Đang làm sẵn thumbnail ${d.n}/${d.total}...`; renderAnalyze(); }
  else if (kind === "analyze_countdown") { $("shutSec").textContent = d.remaining; $("shut").classList.remove("hidden"); }
  else if (kind === "analyze_shutdown") {
    $("shut").classList.add("hidden");
    if (d.state === "skipped") status(d.reason, "warn"); else if (d.state === "cancelled") status("Đã huỷ tắt máy.", "ok"); else if (d.state === "sent") status("Đang tắt máy...", "warn");
  } else if (kind === "analyze_done") {
    AN.running = false; renderAnalyze();
    const s = d.speech || {};
    AN.text = d.ok ? `Phân tích xong: ${s.done || 0} clip đã chép, ${s.silent || 0} im lặng, ${s.errors || 0} lỗi.` : `Phân tích dừng: ${d.reason || "có lỗi"}.`;
    $("anText").textContent = AN.text;
    if (d.shutdown !== "sent" && d.shutdown !== "cancelled") status(AN.text + (d.shutdown === "skipped" ? " Máy KHÔNG tắt." : ""), d.ok ? "ok" : "warn");
    if (page === 4) lnRefresh();
  }
}
