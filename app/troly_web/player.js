/* player.js - Trình phát proxy + kéo chỉnh In/Out ở cột phải Bước 2 (ADR-0016).
   Chỉ vẽ và nhận thao tác; phát file qua máy chủ cục bộ 127.0.0.1 (troly_play.py), lưu In/Out đặt tay vào kế hoạch panel
   (api.set_inout), ghi vào DaVinci chỉ khi bấm nút + xác nhận. Phím đọc bằng event.code, bỏ qua khi đang gõ ô chữ. */
"use strict";

const PL = { uid: null, vid: null, fps: 25, dur: 0, ok: false, edge: null, focus: false, drag: null, tried: false };
const fmtF = (t, fps) => {                                   // giây -> mm:ss:ff theo frame của clip
  t = Math.max(0, t || 0); fps = Math.round(fps || 25);
  const f = Math.round(t * fps), ff = f % fps, s = Math.floor(f / fps);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0") + ":" + String(ff).padStart(2, "0");
};
const curClip = () => items[cur];
const plStep = () => 1 / (PL.fps || 25);

/* ---- vẽ thanh In/Out + đầu phát ---- */
function plRenderIo(c) {
  const dur = (c && c.dur) || 0, bar = $("ioBar");
  PL.dur = dur; PL.fps = (c && c.fps) || 25;
  if (!c || !(dur > 0)) {
    bar.innerHTML = '<div class="io-empty">' + (c ? "Chưa đặt In / Out" : "Chưa chọn clip") + "</div>";
    $("ioIn").textContent = "In --:--:--"; $("ioIn").className = "io-in";
    $("ioOut").textContent = "Out --:--:--"; $("ioOut").className = "io-in";
    $("ioDur").textContent = "Giữ --:--:--"; $("ioRule").textContent = "";
    return;
  }
  const pct = (x) => Math.max(0, Math.min(100, (x / dur) * 100)).toFixed(2);
  let a = null, b = null, cls = "", rule = "", tcls = "";
  if (c.in_s != null && c.out_s != null) {
    a = c.in_s; b = c.out_s;
    const sameDv = c.dv && Math.abs(c.dv[0] - a) < 0.02 && Math.abs(c.dv[1] - b) < 0.02;
    if (c.io_src === "manual" && !sameDv) { cls = "io-range man"; tcls = "active"; rule = "Đặt tay trong panel (chưa ghi vào DaVinci)"; }
    else { cls = "io-range"; tcls = "active"; rule = "Đã đặt trong DaVinci"; }
  } else if (c.sug) {
    a = c.sug.in_s; b = c.sug.out_s; cls = "io-sug"; tcls = "sug"; rule = "Gợi ý (" + c.sug.rule + ") - kéo mép hoặc bấm I / O để đặt tay";
  }
  let h = "";
  if (a != null) {
    h += `<div class="${cls}" style="left:${pct(a)}%;width:${(pct(b) - pct(a)).toFixed(2)}%">` +
      `<span class="h hin ${PL.edge === "in" ? "on" : ""}" data-h="in"></span><span class="h hout ${PL.edge === "out" ? "on" : ""}" data-h="out"></span></div>`;
    $("ioIn").textContent = "In " + fmtF(a, PL.fps); $("ioIn").className = "io-in " + tcls;
    $("ioOut").textContent = "Out " + fmtF(b, PL.fps); $("ioOut").className = "io-in " + tcls;
    $("ioDur").textContent = "Giữ " + fmtF(b - a, PL.fps);
  } else {
    h += '<div class="io-empty">Chưa đặt In / Out (bấm I / O khi đang xem)</div>';
    $("ioIn").textContent = "In --:--:--"; $("ioIn").className = "io-in";
    $("ioOut").textContent = "Out --:--:--"; $("ioOut").className = "io-in";
    $("ioDur").textContent = "Giữ --:--:--";
  }
  const t = PL.vid ? PL.vid.currentTime : 0;
  h += `<div class="io-head" id="ioHead" style="left:${pct(t)}%"></div>`;
  bar.innerHTML = h;
  $("ioRule").textContent = rule;
}
function plHead() {
  const hd = $("ioHead"); if (!hd || !PL.dur) return;
  hd.style.left = Math.max(0, Math.min(100, (PL.vid.currentTime / PL.dur) * 100)).toFixed(2) + "%";
}

/* ---- đặt / lưu In/Out đặt tay ---- */
async function plSet(a, b) {
  const c = curClip(); if (!c) return;
  const r = await api().set_inout(c.uid, a, b);
  if (r.error) return status(r.error, "warn");
  c.in_s = r.in_s; c.out_s = r.out_s; c.io_src = r.in_s == null ? null : "manual";
  plRenderIo(c);
}
function plCurRange() {
  const c = curClip(); if (!c) return null;
  if (c.in_s != null) return [c.in_s, c.out_s];
  return [0, c.dur || 0];
}
function plMark(which) {                                       // phím I / O: đặt tại vị trí đang xem
  const c = curClip(); if (!c || !PL.vid) return;
  const t = PL.vid.currentTime, [a, b] = plCurRange();
  PL.edge = which;
  if (which === "in") plSet(t, Math.max(b, t + plStep()));
  else plSet(Math.min(a, t - plStep()), t);
}
function plSeek(t) {
  if (!PL.vid) return;
  PL.vid.currentTime = Math.max(0, Math.min(PL.dur || 0, t));
  plHead(); plTime();
}
function plNudge(frames) {                                     // mũi tên: chỉnh từng frame
  const c = curClip(); if (!c || !PL.vid) return;
  const d = frames * plStep();
  if (PL.edge && c.in_s != null) {
    let [a, b] = [c.in_s, c.out_s];
    if (PL.edge === "in") a = Math.min(a + d, b - plStep()); else b = Math.max(b + d, a + plStep());
    plSet(a, b); plSeek(PL.edge === "in" ? a : b);
  } else plSeek(PL.vid.currentTime + d);
}

/* ---- kéo hai mép bằng chuột; bấm vào thanh để lướt tới đó ---- */
$("ioBar").addEventListener("mousedown", (ev) => {
  const c = curClip(); if (!c || !(c.dur > 0)) return;
  PL.focus = true;
  const rect = $("ioBar").getBoundingClientRect(), dur = c.dur;
  const tAt = (x) => Math.max(0, Math.min(dur, (x - rect.left) / rect.width * dur));
  const h = ev.target.closest(".h");
  if (!h) { plSeek(tAt(ev.clientX)); return; }
  ev.preventDefault();
  const which = h.dataset.h; PL.edge = which;
  let a = c.in_s != null ? c.in_s : (c.sug ? c.sug.in_s : 0), b = c.out_s != null ? c.out_s : (c.sug ? c.sug.out_s : dur);
  const move = (m) => {
    const t = tAt(m.clientX), s = plStep();
    if (which === "in") a = Math.min(t, b - s); else b = Math.max(t, a + s);
    c.in_s = a; c.out_s = b; c.io_src = "manual"; plRenderIo(c);
    plSeek(which === "in" ? a : b);
  };
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); plSet(a, b); };
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
});

/* ---- trình phát ---- */
function plTime() {
  if (!PL.vid) return;
  $("plTime").textContent = fmtF(PL.vid.currentTime, PL.fps) + " / " + fmtF(PL.dur, PL.fps);
  $("plSeek").value = PL.dur ? Math.round(PL.vid.currentTime / PL.dur * 1000) : 0;
}
function plToggle() {
  if (!PL.vid || !PL.ok) return;
  if (PL.vid.paused) PL.vid.play(); else PL.vid.pause();
}
function plStop() {
  if (PL.vid) { try { PL.vid.pause(); } catch (e) { /* bỏ qua */ } PL.vid.removeAttribute("src"); PL.vid.load(); }
  PL.vid = null; PL.ok = false; PL.edge = null; PL.tried = false;
  $("player").classList.add("hidden");
}
async function plOpen(c, transcode) {                         // gọi từ showCur khi đổi clip
  if (!transcode) { plStop(); PL.uid = c ? c.uid : null; }
  if (!c) return;
  const uid = c.uid, r = await api().play_info(uid, !!transcode);
  if (curClip() == null || curClip().uid !== uid) return;     // đã chuyển clip khác
  if (r.error) {                                              // không có proxy / chưa cấu hình: giữ thumbnail
    $("plNote").textContent = r.error === "Chưa có proxy" ? "Chưa có proxy - chỉ xem hình tĩnh" : r.error;
    $("player").classList.remove("hidden"); $("plCtl").classList.add("hidden"); return;
  }
  $("plCtl").classList.remove("hidden"); $("plNote").textContent = transcode ? "Bản xem nhẹ (ffmpeg)" : "";
  PL.fps = r.fps || PL.fps; PL.dur = r.dur || PL.dur;
  const v = document.createElement("video");
  v.muted = false; v.preload = "auto"; v.playsInline = true; v.src = r.url; v.controls = false;
  const fallback = () => {                                    // dùng bản xem nhẹ ffmpeg (H.264) khi WebView2 không giải mã được hình
    if (PL.uid !== uid || transcode) { $("plNote").textContent = "Không phát được proxy này"; return; }
    $("plNote").textContent = "Đang tạo bản xem nhẹ..."; PL.tried = true;
    plOpen(curClip(), true);
  };
  v.addEventListener("loadedmetadata", () => {
    // Đo 18/11/2026: proxy HEVC (hvc1) trong WebView2 KHÔNG báo lỗi, chỉ ra tiếng mà không có hình (videoWidth = 0).
    if (!v.videoWidth) return fallback();
    PL.ok = true; if (v.duration) PL.dur = v.duration; plTime(); plRenderIo(curClip());
  });
  v.addEventListener("timeupdate", () => { plHead(); plTime(); });
  v.addEventListener("play", () => { $("plPlay").textContent = "❚❚"; });
  v.addEventListener("pause", () => { $("plPlay").textContent = "▶"; });
  v.addEventListener("error", fallback);                      // WebView2 không phát được định dạng này -> bản xem nhẹ
  v.className = "pv"; v.style.opacity = "0"; v.addEventListener("loadeddata", () => { v.style.opacity = "1"; });
  const old = $("preview").querySelector("video"); if (old) { old.pause(); old.remove(); }
  $("preview").appendChild(v);
  PL.vid = v; $("player").classList.remove("hidden");
}
$("plPlay").onclick = plToggle;
$("preview").addEventListener("click", () => { PL.focus = true; plToggle(); });
$("plSeek").addEventListener("input", () => { if (PL.vid) plSeek($("plSeek").value / 1000 * PL.dur); });
$("plRate").addEventListener("change", () => { if (PL.vid) PL.vid.playbackRate = +$("plRate").value; });
document.addEventListener("mousedown", (e) => {               // bấm ra ngoài cột phải: mũi tên lại đi chuyển clip
  if (!e.target.closest(".col-right")) { PL.focus = false; PL.edge = null; }
  else if (!e.target.closest(".h")) { /* giữ PL.edge để mũi tên vẫn chỉnh mép đang chọn */ }
}, true);

/* ---- phím: Space, I, O, mũi tên (chỉ khi con trỏ ở cột phải / vừa chọn mép) - capture để chạy trước phím lưới ---- */
document.addEventListener("keydown", (e) => {
  if (page !== 2 && page !== 3) return;
  if (!$("modal").classList.contains("hidden")) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== "range" || e.target.isContentEditable) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.code === "Space") { e.preventDefault(); e.stopPropagation(); plToggle(); return; }
  if (e.code === "KeyI") { e.preventDefault(); e.stopPropagation(); plMark("in"); return; }
  if (e.code === "KeyO") { e.preventDefault(); e.stopPropagation(); plMark("out"); return; }
  if ((e.code === "ArrowLeft" || e.code === "ArrowRight") && PL.focus && PL.vid) {
    e.preventDefault(); e.stopPropagation(); plNudge((e.code === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
  }
}, true);

/* ---- nút Ghi In/Out vào DaVinci + Hoàn tác (hộp xác nhận nói rõ số clip) ---- */
async function plWrite(scope, uids) {
  const pv = await api().inout_write_preview(scope, uids || []);
  if (!pv.n) return status(pv.pool ? "Không clip nào trong số " + pv.pool + " có In/Out ĐẶT TAY để ghi (gợi ý tự động không được ghi)." : "Chưa có clip nào " + (scope === "starred" ? "gắn sao." : "được chọn."), "warn");
  const ok = await ask("Ghi In/Out vào DaVinci?",
    `<p>Sẽ ghi In/Out của <b>${pv.n} clip</b> vào Media Pool` + (pv.skip ? ` (bỏ qua ${pv.skip} clip chưa đặt tay)` : "") +
    `.</p><p>Trợ lý <b>sao lưu In/Out cũ</b> của từng clip trước khi ghi, rồi đọc lại đối chiếu. Có nút <b>Hoàn tác In/Out</b>. Không xóa clip, không đụng timeline hay file.</p>`, "Ghi " + pv.n + " clip");
  if (!ok) return;
  const r = await api().inout_write(scope, uids || []);
  if (r.error) status(r.error, "warn");
}
$("ioWriteStar").onclick = () => plWrite("starred");
$("ioWriteSel").onclick = () => plWrite("selected", [...sel].map((i) => items[i] && items[i].uid).filter(Boolean));
$("ioUndo").onclick = async () => {
  const ok = await ask("Hoàn tác In/Out?", "<p>Khôi phục In/Out của các clip về đúng bản sao lưu lần ghi gần nhất (clip trước đó chưa có In/Out thì xóa In/Out).</p>", "Hoàn tác");
  if (!ok) return;
  const r = await api().inout_undo();
  if (r.error) status(r.error, "warn");
};
