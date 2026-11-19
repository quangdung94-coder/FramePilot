/* step3.js - Trang Bước 3 · In / Out (ADR-0019; bố cục theo design/3_inout).
   Cột trái: clip theo bin. Giữa: trình phát (player.js) + sóng âm + thanh In/Out kéo tay. Phải: bảng quy tắc gợi ý từng bin.
   Chỉ vẽ và gọi Python (api.wave, set_bin_rule, reset_bin_rule, set_trad_trim). Gợi ý màu xanh không bao giờ tự ghi vào DaVinci. */
"use strict";

const WV = { uid: null, peaks: null, err: "", timer: null };
const P3 = { sig: "", rulesSig: "", onlyStar: true, saved2: false, entered: false, anchor: null, tx: { uid: null, data: null, now: -2 }, poll: 0, fold: {}, sugRun: false };

/* Khối xem clip (hình + nút phát) nằm ở Bước 2 hoặc Bước 3: chuyển chỗ khi đổi bước, rồi trình phát tự mở lại */
function placeStage() {
  const box = $("stageBox"); if (!box) return;
  const host = page === 3 ? $("stageHost3") : $("stageHost2");
  if (box.parentNode !== host) { plStop(); PL.uid = null; host.appendChild(box); }
}

/* ---- cột trái: cây giai đoạn > bin con (giống Bước 2), mỗi dòng "số clip sao / tổng" ---- */
function p3Dot(c) {
  if (c.in_s != null) {
    const sameDv = c.dv && Math.abs(c.dv[0] - c.in_s) < 0.02 && Math.abs(c.dv[1] - c.out_s) < 0.02;
    return c.io_src === "manual" && !sameDv ? "man" : "dv";
  }
  return c.sug ? "sug" : "";
}
const p3Keep = (c) => (c.in_s != null ? c.out_s - c.in_s : (c.sug ? c.sug.dur : null));
function p3Enter() {                                            // vào Bước 3: công tắc "Chỉ hiện clip có sao" (mặc định BẬT) dùng chung bộ lọc của lưới Bước 2
  P3.entered = true; P3.saved2 = $("onlyStar").checked; $("onlyStar").checked = P3.onlyStar; $("p3OnlyStar").checked = P3.onlyStar;
  renderPage2(true);
  renderPage3();
}
function p3Leave() {
  if (!P3.entered) return;
  P3.entered = false; P3.onlyStar = $("onlyStar").checked; $("onlyStar").checked = P3.saved2; $("p3Sum").classList.add("hidden");
  clearTimeout(P3.poll);
}
function renderPage3() {
  if (!S) return;
  if (!P3.entered) { p3Enter(); return; }
  if (gStage === null && S.stages.length) { gStage = 0; gSub = null; renderPage2(true); return; }
  const star = new Set(S.clips.filter((c) => c.star).map((c) => c.uid));
  const cnt = (uids) => `<span class="n"><b>${uids.filter((u) => star.has(u)).length}</b> / ${uids.length}</span>`;
  const clipsHtml = () => {
    if (!items.length) return `<div class="p3-empty">${S.n ? ($("onlyStar").checked ? "Chưa có clip sao ★ trong mục này." : "Không có clip.") : 'Bấm "Đọc clip" ở bước 1 trước.'}</div>`;
    return `<div class="p3-clips">` + items.map((c, i) => {
      const k = p3Keep(c);
      return `<div class="p3-clip${i === cur ? " cur" : ""}${c.star ? "" : " off"}" data-i="${i}"><span class="st">${c.star ? "★" : ""}</span><i class="dot ${p3Dot(c)}"></i><span class="t" title="${esc(c.name)}">${esc(c.name)}</span><span class="tm">${c.time}</span><span class="kp">${k == null ? "" : durTxt(k)}</span></div>`;
    }).join("") + `</div>`;
  };
  // Thu gọn / mở danh sách clip (P3.fold, nhớ khi đổi clip hoặc đổi bước). Cả giai đoạn: mặc định THU GỌN (chỉ hiện các bin con); bin: mặc định mở.
  const folded = (key, dflt) => (P3.fold[key] === undefined ? dflt : P3.fold[key]);
  const ar = (on, fold) => `<span class="p3-ar" data-ar="1" title="${on && !fold ? "Thu gọn danh sách clip" : "Mở danh sách clip"}">${on && !fold ? "▾" : "▸"}</span>`;
  let h = S.stages.map((s, i) => {
    const open = i === gStage;
    const fs = folded("s:" + i, true);
    let r = `<div class="pool-stage"><div class="pool-row${open && gSub === null ? " on" : ""}${open && gSub !== null ? " parent" : ""}" data-stage="${i}">${ar(open && gSub === null, fs)}${folder(s.color, 18)}<span class="t">${esc(s.bin)}</span>${cnt(s.uids)}</div>`;
    if (open) {
      r += `<div class="pool-subs">`;
      if (gSub === null && !fs) r += clipsHtml();
      const fn = folded("n:" + i, false);
      r += `<div class="sub-none${gSub === NONE ? " on" : ""}" data-stage="${i}">${ar(gSub === NONE, fn)}<span class="sq" style="background:var(--dim2);opacity:.5"></span><span class="t">Chưa xếp</span>${cnt(s.none)}</div>` + (gSub === NONE && !fn ? clipsHtml() : "");
      for (const bn of s.bins) {
        const fb = folded("b:" + i + ":" + bn.name, false);
        r += `<div class="sub${gSub === bn.name ? " on" : ""}" data-stage="${i}" data-bin="${esc(bn.name)}">${ar(gSub === bn.name, fb)}<span class="sq" style="background:${bn.color}"></span><span class="t">${esc(bn.name)}</span>${cnt(bn.uids)}</div>` + (gSub === bn.name && !fb ? clipsHtml() : "");
      }
      r += `</div>`;
    }
    return r + `</div>`;
  }).join("");
  if (S.outside) h += `<div class="pool-stage"><div class="pool-row${gStage === -1 ? " on" : ""}" data-stage="-1">${folder("#6A6A72", 18)}<span class="t" style="color:var(--dim)">Ngoài giai đoạn</span><span class="n">${S.outside}</span></div>${gStage === -1 ? `<div class="pool-subs">${clipsHtml()}</div>` : ""}</div>`;
  if (h !== P3.sig) {
    const box = $("p3List"), top = box.scrollTop;
    P3.sig = h; box.innerHTML = h; box.scrollTop = top;
  }
  p3SugPaint(); p3SumPaint();
  renderRules();
}
function p3View(si, sub) {
  if (si === gStage && sub === gSub) return;
  gStage = si; gSub = sub; $("onlyNew").checked = false; saveUi();
  renderPage2(true); renderPage3();
}
function p3FoldKey(si, sub) { return sub === null ? "s:" + si : sub === NONE ? "n:" + si : "b:" + si + ":" + sub; }
function p3RowClick(si, sub, onArrow) {                         // bấm dòng: XEM (không đổi nhãn clip). Bấm lại dòng đang chọn hoặc bấm mũi tên: thu gọn / mở danh sách clip
  const key = p3FoldKey(si, sub), dflt = sub === null;
  const selected = si === gStage && sub === gSub;
  if (!selected) {
    if (onArrow) P3.fold[key] = false;                          // bấm mũi tên dòng khác: chọn và mở luôn danh sách clip
    return p3View(si, sub);
  }
  P3.fold[key] = !(P3.fold[key] === undefined ? dflt : P3.fold[key]);
  P3.sig = ""; renderPage3();
}
$("p3List").addEventListener("click", (e) => {
  const cl = e.target.closest(".p3-clip"); if (cl) { moveCur(+cl.dataset.i); $("p3List").focus(); return; }
  const onAr = !!e.target.closest(".p3-ar");
  const sn = e.target.closest(".sub-none"); if (sn) return p3RowClick(+sn.dataset.stage, NONE, onAr);
  const sb = e.target.closest(".sub"); if (sb) return p3RowClick(+sb.dataset.stage, sb.dataset.bin, onAr);
  const pr = e.target.closest(".pool-row"); if (pr) return p3RowClick(+pr.dataset.stage, null, onAr);
});
$("p3OnlyStar").addEventListener("change", () => { P3.onlyStar = $("p3OnlyStar").checked; $("onlyStar").checked = P3.onlyStar; renderPage2(true); renderPage3(); });
$("p3Star").onclick = () => toggleStar();

/* ---- nút "Gợi ý In/Out cho clip sao" (chạy nền, hai mức, không tự ghi vào DaVinci) ---- */
function p3SugPaint() {
  const g = S && S.inout_sug, b = $("p3Sug"); if (!g || !b) return;
  if (g.pad != null && document.activeElement !== $("p3Pad")) $("p3Pad").value = g.pad;
  const run = g.running, n = g.starred;
  b.disabled = !!run;                                           // chỉ khoá khi đang chạy; không có clip sao thì bấm vẫn báo lý do (không im lặng)
  b.classList.toggle("run", !!run);
  b.classList.toggle("again", !run && g.done > 0);
  const pct = run && g.total ? g.n / g.total * 100 : (n ? Math.min(100, g.done / n * 100) : 0);
  $("p3SugBar").style.width = pct + "%";
  b.style.removeProperty("--pg");
  $("p3SugT").textContent = run ? `Đang chạy… ${g.n}/${g.total}` : `Tự phân loại In/Out · ${n} clip sao`;
  $("p3SugN").textContent = run ? `đã chạy ${g.n} / ${g.total}` : (n ? `đã chạy ${g.done} / ${n}` : "chưa có clip sao");
  b.querySelector(".gi").textContent = run ? "…" : (g.done > 0 ? "↻" : "▶");
  b.title = n ? "Chạy nền một lượt cho mọi clip có sao: gợi ý theo lời nói (nếu đã chép lời ở Bước 4), không thì theo quy tắc bin bên trên. Màu xanh, không tự ghi vào DaVinci."
    : "Chưa có clip sao. Gắn sao (J) ở Bước 2 trước.";
}
function p3SugMsg(text, kind) { const m = $("p3SugMsg"); m.textContent = text || ""; m.className = "p3-gymsg" + (kind ? " " + kind : ""); }
function p3SugSummary() {                                       // kết quả lần chạy, đọc từ chính trạng thái hiện có
  const st = S.clips.filter((c) => c.star && c.sug && c.sug.src !== "live");
  const sp = st.filter((c) => c.sug.src === "speech").length;
  return { total: st.length, speech: sp, rule: st.length - sp };
}
function p3SumPaint() {
  const el = $("p3Sum"), g = S && S.inout_sug; if (!el || !g) return;
  el.classList.toggle("hidden", page !== 3);
  const stages = new Set(S.clips.filter((c) => c.star && c.stage !== null && c.stage !== undefined).map((c) => c.stage)).size;
  el.textContent = `${g.starred} clip có sao trong ${stages} giai đoạn · gợi ý đã chạy ${g.done}/${g.starred} · đã nhận hoặc chỉnh ${g.accepted + g.adjusted}/${g.starred}`;
}
async function p3SugStart() {
  p3SugMsg("Đang bắt đầu…", "");
  let r;
  try { r = await api().inout_suggest_start($("p3KeepManual").checked); } catch (e) { r = { error: "Không gọi được Trợ lý: " + (e && e.message ? e.message : e) }; }
  if (!r || r.error) { const m = (r && r.error) || "Không chạy được gợi ý."; p3SugMsg("Không chạy: " + m, "err"); return status(m, "warn"); }
  P3.sugRun = true;
  if (S.inout_sug) { S.inout_sug.running = true; S.inout_sug.n = 0; S.inout_sug.total = r.total; }
  p3SugPaint(); p3SugMsg(`Đang chạy nền cho ${r.total} clip sao` + (r.kept ? `, giữ nguyên ${r.kept} clip bạn đã đặt tay` : "") + "…", ""); p3SugPoll();
}
async function p3SugFinish() {                                  // lần chạy vừa xong (sự kiện nền hoặc hỏi tiến độ): nạp lại trạng thái, báo kết quả
  if (!P3.sugRun) return;
  P3.sugRun = false;
  try { setState(await api().state()); } catch (e) { p3SugMsg("Chạy xong nhưng không nạp lại được trạng thái: " + e, "err"); return; }
  const x = p3SugSummary();
  const msg = `Đã gợi ý cho ${x.total} clip sao: ${x.speech} theo lời nói, ${x.rule} theo quy tắc bin. Màu xanh, chưa ghi gì vào DaVinci.`;
  p3SugMsg(msg, "ok");
  status(msg + " Bấm A để nhận từng clip.", "ok");
}
async function p3SugPoll() {                                    // hỏi tiến độ (dự phòng nếu sự kiện nền không tới)
  clearTimeout(P3.poll);
  let g; try { g = await api().inout_stats(); } catch (e) { p3SugMsg("Mất kết nối khi hỏi tiến độ: " + e, "err"); P3.sugRun = false; return; }
  if (S) S.inout_sug = g;
  p3SugPaint(); p3SumPaint();
  if (g.running) P3.poll = setTimeout(p3SugPoll, 600); else p3SugFinish();
}
$("p3Sug").onclick = p3SugStart;
function p3SugEvent(kind, d) {                                  // gọi từ onEvent
  if (kind === "inout_sug_progress" && S && S.inout_sug) { P3.sugRun = true; S.inout_sug.running = true; S.inout_sug.n = d.n; S.inout_sug.total = d.total; p3SugPaint(); return; }
  if (kind === "inout_sug_done") { P3.sugRun = true; p3SugFinish(); }
}

/* ---- phím A / nút "Nhận gợi ý": gợi ý xanh -> In/Out đặt tay (cam), rồi sang clip kế. Chỉ ở Bước 3; không nhận hàng loạt ---- */
function p3SeqNext() {                                          // clip kế trong bin; hết bin thì sang bin/giai đoạn kế có clip
  if (cur < items.length - 1) { moveCur(cur + 1); return true; }
  const star = new Set(S.clips.filter((c) => c.star).map((c) => c.uid)), only = $("onlyStar").checked;
  const n = (uids) => (only ? uids.filter((u) => star.has(u)).length : uids.length);
  const seq = [];
  S.stages.forEach((s, i) => {
    if (gSub === null) { seq.push([i, null, n(s.uids)]); return; }
    s.bins.forEach((b) => seq.push([i, b.name, n(b.uids)])); seq.push([i, NONE, n(s.none)]);
  });
  const at = seq.findIndex((x) => x[0] === gStage && x[1] === gSub);
  for (let k = at + 1; k < seq.length; k++) if (seq[k][2] > 0) { p3View(seq[k][0], seq[k][1]); moveCur(0); return true; }
  return false;
}
async function p3Accept() {
  const c = curClip(); if (!c) return;
  if (!c.sug) return status("Clip này chưa có gợi ý.", "warn");
  const r = await api().inout_accept(c.uid);
  if (r.error) return status(r.error, "warn");
  c.in_s = r.in_s; c.out_s = r.out_s; c.io_src = "manual";
  if (S.inout_sug) Object.assign(S.inout_sug, { accepted: r.stats.accepted, adjusted: r.stats.adjusted, by_src: r.stats.by_src });
  plRenderIo(c); renderPage3Cur(c); renderPage3();
  const moved = p3SeqNext();
  status(`Đã nhận gợi ý ${r.src === "speech" ? "theo lời nói" : "theo quy tắc bin"} cho ${c.name} (cam = đặt tay, chưa ghi vào DaVinci).` + (moved ? "" : " Hết clip có sao."), "ok");
}
$("p3Accept").onclick = p3Accept;
document.addEventListener("keydown", (e) => {                   // A chỉ có tác dụng ở Bước 3 (Bước 2: A = nhận gợi ý AI xếp bin); event.code, bỏ qua khi gõ chữ
  if (page !== 3 || e.code !== "KeyA" || e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || !$("modal").classList.contains("hidden")) return;
  e.preventDefault(); e.stopPropagation(); p3Accept();
}, true);

/* ---- khung chữ Whisper dưới sóng âm ---- */
const p3mmss = (t) => { t = Math.max(0, Math.floor(t || 0)); return String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0"); };
async function p3TxLoad(c) {
  if (!c) { P3.tx = { uid: null, data: null, now: -2 }; return p3TxPaint(); }
  if (P3.tx.uid === c.uid && P3.tx.data) return p3TxPaint();
  P3.tx = { uid: c.uid, data: null, now: -2 }; P3.anchor = null; p3TxPaint();
  let d; try { d = await api().speech_detail(c.uid); } catch (e) { d = { lines: [] }; }
  if (P3.tx.uid !== c.uid) return;
  P3.tx.data = d; p3TxPaint();
}
function p3TxPaint() {
  const c = curClip(), d = P3.tx.data, box = $("p3Tx"), list = $("p3TxList"), ctr = $("p3Center");
  if (!c || !$("page3") || $("page3").classList.contains("hidden")) return;
  const hasRow = !!(d && d.has_row), lines = (d && d.lines) || [];
  if (d && hasRow && !lines.length) { box.classList.add("hidden"); ctr.classList.add("notx"); return; }          // không có tiếng nói: ẩn khung chữ, kéo dài sóng âm
  box.classList.remove("hidden"); ctr.classList.remove("notx");
  const pill = $("p3TxPill");
  if (!d) { pill.textContent = ""; list.innerHTML = '<div class="p3-empty">Đang đọc chữ…</div>'; return; }
  if (!hasRow) {
    pill.textContent = ""; $("p3TxT").textContent = "Lời nói (Whisper)";
    list.innerHTML = '<div class="p3-none"><span>Chưa chép lời cho clip này. Chạy Whisper ở Bước 4 để chữ hiện ở đây.</span><button class="btn" id="p3TxGo" type="button">Mở Bước 4 · Lời nói</button><span class="dim12">Vẫn đặt In/Out được bằng sóng âm và hình.</span></div>';
    return;
  }
  $("p3TxT").textContent = "Lời nói (Whisper · " + (d.lang === "en" ? "tiếng Anh" : "tiếng Việt") + ")";
  pill.textContent = "Đã chép · " + lines.length + " câu";
  const a = c.in_s != null ? c.in_s : (c.sug ? c.sug.in_s : null), b = c.in_s != null ? c.out_s : (c.sug ? c.sug.out_s : null), manual = c.in_s != null;
  const e = 0.05;
  list.innerHTML = lines.map((l, i) => {
    const inside = a != null && l.t0 >= a - e && l.t1 <= b + e;
    return `<div class="p3-ln${inside ? (manual ? " in" : " in sg") : ""}" data-i="${i}"><span class="tc">${p3mmss(l.t0)}</span><span class="tt" title="${esc(l.text)}">${esc(l.text)}</span></div>`;
  }).join("");
  P3.tx.now = -2; p3TxNow();
}
function p3TxNow() {                                            // câu đang phát: viền + hai nút nhỏ "Đặt In / Out ở đây"
  const d = P3.tx.data; if (!d || !d.lines || !d.lines.length || !PL.vid) return;
  const t = PL.vid.currentTime; let idx = -1;
  d.lines.forEach((l, i) => { if (l.t0 <= t + 0.01) idx = i; });
  if (idx === P3.tx.now) return;
  P3.tx.now = idx;
  document.querySelectorAll("#p3TxList .p3-ln").forEach((el) => {
    const on = +el.dataset.i === idx;
    el.classList.toggle("now", on);
    const mini = el.querySelectorAll(".mini");
    if (on && !mini.length) { el.insertAdjacentHTML("beforeend", '<button class="mini" data-w="in" type="button">Đặt In ở đây</button><button class="mini" data-w="out" type="button">Đặt Out ở đây</button>'); el.scrollIntoView({ block: "nearest" }); }
    if (!on && mini.length) mini.forEach((m) => m.remove());
  });
}
$("p3TxList").addEventListener("click", async (e) => {
  if (e.target.id === "p3TxGo") return goPage(4);
  const row = e.target.closest(".p3-ln"), c = curClip(), d = P3.tx.data; if (!row || !c || !d) return;
  const i = +row.dataset.i, L = d.lines[i];
  PL.focus = true;
  const mini = e.target.closest(".mini");
  let a, b;
  if (mini) {                                                   // chỉ đổi MỘT đầu theo câu đang phát
    [a, b] = plCurRange();
    if (mini.dataset.w === "in") { a = L.t0; if (b <= a) b = Math.min(c.dur || L.t1, L.t1); } else { b = L.t1; if (a >= b) a = Math.max(0, L.t0); }
  } else if (e.shiftKey && P3.anchor != null && d.lines[P3.anchor]) {        // Shift + bấm câu khác: nối dài vùng từ câu đã bấm trước
    const A = d.lines[P3.anchor]; a = Math.min(A.t0, L.t0); b = Math.max(A.t1, L.t1);
  } else { P3.anchor = i; a = L.t0; b = L.t1; }
  await plSet(a, b);
  plSeek(a);
  p3TxPaint();
});
document.addEventListener("mousedown", (e) => { if (e.shiftKey && e.target.closest("#p3TxList")) e.preventDefault(); }, true);   // Shift + bấm: không bôi chọn chữ

/* ---- clip đang chọn: tiêu đề, hộp thông tin (nguồn gợi ý, đặt tay, giữ lại), sóng âm, chữ ---- */
const P3_SRC = { speech: "theo lời nói", rule: "theo quy tắc bin", live: "tức thời theo quy tắc bin (chưa chạy gợi ý)" };
function renderPage3Cur(c) {
  if (!$("page3")) return;
  if (!c) { $("p3Name").textContent = "Chọn một clip"; $("p3Meta").textContent = ""; $("p3Tag").textContent = ""; $("p3Cur").innerHTML = "<span>Chưa chọn clip.</span>"; waveReset(null); p3TxLoad(null); return; }
  $("p3Name").textContent = c.name;
  $("p3Meta").textContent = `${c.label || "Chưa xếp"} · ${c.time} · dài ${durTxt(c.dur)}`;
  $("p3Tag").textContent = c.label || "Chưa xếp";
  $("p3Star").textContent = c.star ? "★ Bỏ sao (J)" : "☆ Gắn sao (J)";
  $("p3Star").classList.toggle("active", !!c.star); $("p3Star").classList.toggle("btn-star", true);
  $("ioWriteStar").textContent = "Ghi clip sao (" + (S.n_starred || 0) + ")";
  $("p3Accept").disabled = !c.sug;
  const f = c.fps || 25, sug = c.sug, rg = (a, b) => `${fmtF(a, f)} → ${fmtF(b, f)}`;
  let h = "";
  h += `<div class="kv"><span>Gợi ý${sug ? " (" + (P3_SRC[sug.src] || "") + ")" : ""}</span><span class="sg">${sug ? rg(sug.in_s, sug.out_s) : "không gợi ý"}</span></div>`;
  const sameDv = c.in_s != null && c.dv && Math.abs(c.dv[0] - c.in_s) < 0.02 && Math.abs(c.dv[1] - c.out_s) < 0.02;
  if (c.in_s != null) h += `<div class="kv"><span>${c.io_src === "manual" && !sameDv ? "Bạn đặt tay" : "Đã có trong DaVinci"}</span><span>${rg(c.in_s, c.out_s)}</span></div>`;
  else h += `<div class="kv"><span>Bạn đặt tay</span><span>chưa</span></div>`;
  const keep = p3Keep(c); h += `<div class="kv"><span>Giữ lại</span><span>${keep == null ? "--" : fmtF(keep, f)}</span></div>`;
  h += `<div style="margin-top:6px">${c.io_src === "manual" && !sameDv ? "Đặt tay luôn thắng gợi ý. Chưa ghi vào DaVinci." : (sug ? "Bấm A để nhận gợi ý thành In/Out đặt tay." : "Clip quá ngắn nên không gợi ý.")}` +
    (sug && sug.stale ? `<br><span style="color:var(--link)">Quy tắc hoặc đệm đã đổi từ lần gợi ý: chạy lại "Tự phân loại In/Out".</span>` : "") + `</div>`;
  $("p3Cur").innerHTML = h;
  document.querySelectorAll("#p3List .p3-clip").forEach((el) => el.classList.toggle("cur", +el.dataset.i === cur));
  const el = document.querySelector(`#p3List .p3-clip[data-i="${cur}"]`); if (el) el.scrollIntoView({ block: "nearest" });
  if (page === 3) { waveLoad(c); p3TxLoad(c); }
}
$("p3Pad").addEventListener("change", async () => {
  const r = await api().inout_sug_pad($("p3Pad").value);
  if (r.error) { status(r.error, "warn"); $("p3Pad").value = (S && S.inout_sug ? S.inout_sug.pad : 0.3); return; }
  if (S && S.inout_sug) S.inout_sug.pad = r.pad;
  status(`Đệm gợi ý theo lời nói: ${r.pad} giây. Bấm "Tự phân loại In/Out" để chạy lại.`, "ok");
});

/* ---- sóng âm (api.wave làm nền từ proxy, chỉ đọc) ---- */
function waveReset(uid) { clearTimeout(WV.timer); WV.uid = uid; WV.peaks = null; WV.err = ""; waveDraw(); }
function waveLoad(c) {
  if (WV.uid === c.uid) return;
  waveReset(c.uid);
  wavePoll(c.uid, 0);
}
async function wavePoll(uid, n) {
  let r;
  try { r = await api().wave(uid); } catch (e) { r = { error: "Không làm được sóng âm" }; }
  if (WV.uid !== uid) return;
  if (r.peaks) { WV.peaks = r.peaks; WV.err = ""; }
  else if (r.pending && n < 130) { WV.timer = setTimeout(() => wavePoll(uid, n + 1), 700); waveDraw(); return; }
  else WV.err = r.error || "Không làm được sóng âm";
  waveDraw();
}
function waveDraw() {
  const cv = $("waveCv"); if (!cv || !$("page3") || $("page3").classList.contains("hidden")) return;
  const w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
  if (!w || !h) return;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
  const note = $("waveNote"), dur = PL.dur || (curClip() && curClip().dur) || 0;
  if (!WV.peaks) { note.textContent = WV.err ? (WV.err === "Chưa có proxy" ? "Chưa có proxy, chưa có sóng âm" : WV.err) : (WV.uid ? "Đang làm sóng âm..." : ""); return; }
  note.textContent = "";
  const n = WV.peaks.length, bw = w / n, rg = PL.range;
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n * dur, inside = rg && t >= rg[0] && t <= rg[1];
    g.fillStyle = inside ? (rg[2] === "sug" ? "#5B9BF5" : "#F2A33A") : "#6F7788";
    const bh = Math.max(2, WV.peaks[i] / 100 * (h - 8));
    g.fillRect(i * bw, (h - bh) / 2, Math.max(1, bw - 0.6), bh);
  }
}
window.addEventListener("resize", () => waveDraw());

/* ---- bảng quy tắc từng bin (api.set_bin_rule, reset_bin_rule, set_trad_trim) ---- */
const STYLE_NAME = { "": "chưa chọn kiểu quay", psc: "PSC", traditional: "Truyền thống" };
const num = (v) => (v == null ? "" : String(+(+v).toFixed(2)));
function renderRules() {
  if (!S || !S.rules) return;
  const R = S.rules, s = stageObj(), tbl = $("rulesTbl");
  const names = s ? s.bins.map((b) => ({ name: b.name, color: b.color })) : [];
  names.push({ name: "*", color: "#6A6A72" });
  const byName = new Map(R.bins.map((b) => [b.name, b]));
  const rows = names.map((x) => ({ ...x, r: byName.get(x.name) })).filter((x) => x.r);
  const trad = R.style === "traditional";
  const sig = JSON.stringify([rows.map((x) => [x.name, x.r]), R.style, R.trad_head, R.trad_tail, R.trad_bins]);
  if (sig === P3.rulesSig) return;
  if (tbl.contains(document.activeElement) || document.activeElement === $("tradHead") || document.activeElement === $("tradTail")) return;    // đang gõ: không dựng lại
  P3.rulesSig = sig;
  if (trad) {                                                   // Truyền thống: cắt ĐẦU / ĐUÔI riêng từng bin (ADR-0025); min/max bị ẩn
    tbl.className = "rt trad";
    tbl.innerHTML = '<tr><th>Bin</th><th>Cắt đầu (s)</th><th>Cắt đuôi (s)</th><th></th></tr>' + rows.filter((x) => x.name !== "*").map((x) => {
      const t = (R.trad_bins || {})[x.name] || { head: R.trad_head, tail: R.trad_tail, edited: false };
      return `<tr data-bin="${esc(x.name)}" data-trad="1"><td class="nm"><i style="background:${x.color}"></i>${esc(x.name)}</td>` +
        `<td><input class="num${t.edited ? " ed" : ""}" data-f="head" inputmode="decimal" value="${num(t.head)}" aria-label="Cắt đầu ${esc(x.name)}"></td>` +
        `<td><input class="num${t.edited ? " ed" : ""}" data-f="tail" inputmode="decimal" value="${num(t.tail)}" aria-label="Cắt đuôi ${esc(x.name)}"></td>` +
        `<td>${t.edited ? `<button class="btn-link" data-reset="1" title="Bin này quay về dùng cắt đầu / đuôi chung">chung</button>` : ""}</td></tr>`;
    }).join("");
  } else {
    tbl.className = "rt";
    tbl.innerHTML = '<tr><th>Bin</th><th>Tối thiểu (s)</th><th>Tối đa (s)</th><th>Trọn câu</th></tr>' + rows.map((x) =>
      `<tr data-bin="${esc(x.name)}"><td class="nm"><i style="background:${x.color}"></i>${x.name === "*" ? "Bin khác" : esc(x.name)}</td>` +
      `<td><input class="num${x.r.edited ? " ed" : ""}" data-f="min" inputmode="decimal" value="${num(x.r.min)}" aria-label="Tối thiểu ${esc(x.name)}"></td>` +
      `<td><input class="num${x.r.edited ? " ed" : ""}" data-f="max" inputmode="decimal" value="${x.r.whole ? "" : num(x.r.max)}" placeholder="—"${x.r.whole ? " disabled" : ""} aria-label="Tối đa ${esc(x.name)}"></td>` +
      `<td><input type="checkbox" data-f="whole"${x.r.whole ? " checked" : ""} aria-label="Giữ trọn câu ${esc(x.name)}"></td></tr>`).join("");
  }
  $("rulesStyle").textContent = STYLE_NAME[R.style] || R.style;
  $("trStyleName").textContent = "Kiểu quay: " + (STYLE_NAME[R.style] || R.style);
  $("trStyleText").textContent = R.style === "traditional" ? "Đang dùng Truyền thống: bảng bên trên là cắt ĐẦU / ĐUÔI riêng từng bin (giữ dài, bảng tối thiểu/tối đa bị bỏ qua). Ô bên dưới là mặc định cho bin chưa sửa."
    : R.style === "psc" ? "Đang dùng PSC: gợi ý theo bảng bên trên. Chọn Truyền thống ở thanh trên thì bảng chuyển sang cắt đầu / đuôi."
    : "Chưa chọn kiểu quay: gợi ý theo bảng bên trên, y như mặc định cũ. Chọn kiểu ở ô trên cùng.";
  $("tradHead").value = num(R.trad_head); $("tradTail").value = num(R.trad_tail);
  $("tradHead").classList.toggle("ed", Math.abs(R.trad_head - R.trad_default) > 1e-9);
  $("tradTail").classList.toggle("ed", Math.abs(R.trad_tail - (R.trad_default_tail == null ? R.trad_default : R.trad_default_tail)) > 1e-9);
  const anyEd = trad ? Object.values(R.trad_bins || {}).some((b) => b.edited) || $("tradHead").classList.contains("ed") || $("tradTail").classList.contains("ed") : R.bins.some((b) => b.edited);
  $("rulesNote").textContent = anyEd ? "Ô viền cam = bạn đã sửa." : "Chưa sửa gì: đang dùng số mặc định.";
}
async function rulesChanged(e) {
  const tr = e.target.closest("tr[data-bin]"); if (!tr) return;
  const v = (f) => tr.querySelector(`[data-f="${f}"]`);
  const val = (el) => String(el.value).trim().replace(",", ".");
  if (tr.dataset.trad) {                                        // Truyền thống: cắt đầu / đuôi của bin
    const st = await api().set_trad_bin(tr.dataset.bin, val(v("head")), val(v("tail")));
    P3.rulesSig = "";
    if (st && st.error) { status(st.error, "warn"); renderRules(); return; }
    setState(st);
    status(`Đã lưu cắt đầu / đuôi của bin ${tr.dataset.bin}. Chỉ đổi gợi ý màu xanh; bấm "Chạy lại" ở nút gợi ý để áp dụng cho clip sao.`, "ok");
    return;
  }
  const whole = v("whole").checked;
  const st = await api().set_bin_rule(tr.dataset.bin, val(v("min")), whole ? null : val(v("max")), whole);
  P3.rulesSig = "";
  if (st && st.error) { status(st.error, "warn"); renderRules(); return; }
  setState(st);
  status("Đã lưu quy tắc " + (tr.dataset.bin === "*" ? "Bin khác" : tr.dataset.bin) + ". Chỉ đổi gợi ý màu xanh.", "ok");
}
$("rulesTbl").addEventListener("click", async (e) => {          // nút "chung": bin quay về dùng cắt đầu / đuôi chung
  const b = e.target.closest("[data-reset]"), tr = e.target.closest("tr[data-bin]"); if (!b || !tr) return;
  const st = await api().reset_trad_bin(tr.dataset.bin);
  P3.rulesSig = "";
  if (st && st.error) return status(st.error, "warn");
  setState(st); status(`Bin ${tr.dataset.bin} dùng cắt đầu / đuôi chung.`, "ok");
});
$("rulesTbl").addEventListener("change", rulesChanged);
$("rulesTbl").addEventListener("keydown", (e) => { if (e.code === "Enter" && e.target.tagName === "INPUT") e.target.blur(); });
async function tradDefaultChanged() {
  const st = await api().set_trad_default(String($("tradHead").value).trim().replace(",", "."), String($("tradTail").value).trim().replace(",", "."));
  P3.rulesSig = "";
  if (st && st.error) { status(st.error, "warn"); renderRules(); return; }
  setState(st); status("Đã lưu cắt đầu / đuôi chung của Truyền thống (mặc định cho bin chưa sửa).", "ok");
}
$("tradHead").onchange = tradDefaultChanged;
$("tradTail").onchange = tradDefaultChanged;
for (const id of ["tradHead", "tradTail"]) $(id).addEventListener("keydown", (e) => { if (e.code === "Enter") e.target.blur(); });
$("rulesReset").onclick = async () => {
  const ok = await ask("Về mặc định?", "<p>Xóa mọi chỗ bạn đã sửa trong bảng quy tắc và số giây cắt đầu / đuôi của Truyền thống (chung và từng bin). In/Out bạn đã đặt tay không bị đụng.</p>", "Về mặc định");
  if (!ok) return;
  const st = await api().reset_bin_rule();
  P3.rulesSig = "";
  if (st && st.error) return status(st.error, "warn");
  setState(st); status("Bảng quy tắc đã về mặc định.", "ok");
};
