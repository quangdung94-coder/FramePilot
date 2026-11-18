/* player.js - Trình phát proxy + kéo chỉnh In/Out ở cột phải Bước 2 (ADR-0016).
   Chỉ vẽ và nhận thao tác; phát file qua máy chủ cục bộ 127.0.0.1 (troly_play.py), lưu In/Out đặt tay vào kế hoạch panel
   (api.set_inout), ghi vào DaVinci chỉ khi bấm nút + xác nhận. Phím đọc bằng event.code, bỏ qua khi đang gõ ô chữ. */
"use strict";

const PL = { range: null, uid: null, vid: null, el: null, open: null, kf: null, fps: 25, dur: 0, ok: false, edge: null, focus: false, drag: null, tried: false };
/* Việc 2 (ADR-0023): lướt mượt. Chỉ gửi lệnh nhảy khi lệnh trước xong (seeked), lệnh mới thay lệnh cũ chưa gửi; đang KÉO thì nhảy theo keyframe
   (giải mã 1 khung), THẢ ra thì nhảy chính xác. Dùng lại MỘT thẻ <video> cho mọi clip. Không tạo proxy mới. */
const SK = { want: null, fast: false, busy: false, drag: false, timer: 0, sent: 0, seeks: 0 };
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
    PL.range = null; if (typeof waveDraw === "function") waveDraw();
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
  PL.range = a != null ? [a, b, cls === "io-sug" ? "sug" : "man"] : null;
  if (typeof waveDraw === "function") waveDraw();
  const t = PL.vid ? PL.vid.currentTime : 0;
  h += `<div class="io-head" id="ioHead" style="left:${pct(t)}%"></div>`;
  bar.innerHTML = h;
  $("ioRule").textContent = rule;
}
function plHead() {
  const hd = $("ioHead"); if (!hd || !PL.dur || !PL.vid) return;
  const x = Math.max(0, Math.min(100, (PL.vid.currentTime / PL.dur) * 100)).toFixed(2) + "%";
  hd.style.left = x;
  const wh = $("waveHead"); if (wh) wh.style.left = x;
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
function kfBefore(t) {                                          // keyframe gần nhất ở hoặc trước t (không có danh sách thì giữ nguyên t)
  const k = PL.kf; if (!k || !k.length) return t;
  let lo = 0, hi = k.length - 1, ans = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (k[m] <= t + 1e-6) { ans = m; lo = m + 1; } else hi = m - 1; }
  return ans < 0 ? 0 : k[ans];
}
function plPump() {                                             // gửi lệnh nhảy kế tiếp nếu lệnh trước đã xong
  const v = PL.vid; if (!v || SK.want == null || SK.busy) return;
  const t = SK.want; SK.want = null;
  const tt = SK.fast ? kfBefore(t) : t;
  if (Math.abs(v.currentTime - tt) < 0.0005 && !v.seeking) { plHead(); plTime(); return; }
  SK.busy = true; SK.seeks++; SK.sent = performance.now();
  clearTimeout(SK.timer); SK.timer = setTimeout(() => { SK.busy = false; plPump(); }, 1500);        // phòng seeked không bao giờ tới
  v.currentTime = tt;
}
function plSeek(t, opt) {                                       // opt.fast: đang kéo -> nhảy theo keyframe; mặc định: chính xác
  if (!PL.vid) return;
  SK.want = Math.max(0, Math.min(PL.dur || 0, t)); SK.fast = !!(opt && opt.fast);
  plPump();
}
function plNudge(frames) {                                     // mũi tên: chỉnh từng frame
  const c = curClip(); if (!c || !PL.vid) return;
  const d = frames * plStep();
  if (PL.edge && c.in_s != null) {
    let [a, b] = [c.in_s, c.out_s];
    if (PL.edge === "in") a = Math.min(a + d, b - plStep()); else b = Math.max(b + d, a + plStep());
    c.in_s = a; c.out_s = b; c.io_src = "manual"; plRenderIo(c);      // cập nhật ngay (giữ phím không mất frame), rồi lưu
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
    plSeek(which === "in" ? a : b, { fast: true });
  };
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); plSet(a, b); plSeek(which === "in" ? a : b); };
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
});


/* ---- Việc 1 (ADR-0023): khung xem trước ĐÚNG MÀU LUT. Áp file .cube bằng WebGL2 lên từng khung hình của proxy (không tạo file mới,
   không đụng proxy). Dữ liệu LUT do api().lut_cube(uid) đọc từ file .cube gốc (chỉ đọc). Không có LUT / WebGL lỗi: hiện hình gốc. ---- */
const LUT = { cv: null, gl: null, prog: null, vtex: null, ltex: null, cache: new Map(), name: "", on: true, ready: false, loopId: 0, vid: null, last: null, loaded: null };
const LUT_VS = "#version 300 es\nin vec2 p; out vec2 uv; void main(){ uv = p*0.5+0.5; gl_Position = vec4(p,0.,1.); }";
const LUT_FS = "#version 300 es\nprecision highp float; precision highp sampler3D;\nuniform sampler2D uV; uniform sampler3D uL; uniform vec3 uMin; uniform vec3 uMax; uniform float uN; uniform int uOn;\n" +
  "in vec2 uv; out vec4 o;\nvoid main(){ vec3 c = texture(uV, vec2(uv.x, 1.0-uv.y)).rgb; if (uOn == 1) { vec3 q = clamp((c-uMin)/(uMax-uMin), 0.0, 1.0); q = q*((uN-1.0)/uN) + 0.5/uN; c = texture(uL, q).rgb; } o = vec4(c, 1.0); }";
function lutGL() {
  if (LUT.gl) return LUT.gl;
  const cv = document.createElement("canvas"); cv.id = "plLut"; cv.className = "pv-lut"; cv.style.display = "none";
  const gl = cv.getContext("webgl2", { alpha: false, antialias: false, preserveDrawingBuffer: true });
  if (!gl) return null;
  const sh = (t, src) => { const x = gl.createShader(t); gl.shaderSource(x, src); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
  try {
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, LUT_VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, LUT_FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    LUT.vtex = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, LUT.vtex);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    gl.uniform1i(gl.getUniformLocation(pr, "uV"), 0); gl.uniform1i(gl.getUniformLocation(pr, "uL"), 1);
    LUT.prog = pr; LUT.cv = cv; LUT.gl = gl;
  } catch (e) { LUT.gl = null; return null; }
  return gl;
}
function lutUpload(d) {                                         // d = {size, dmin, dmax, b64}
  const gl = lutGL(); if (!gl) return false;
  const bin = atob(d.b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const f32 = new Float32Array(u8.buffer);
  if (LUT.ltex) gl.deleteTexture(LUT.ltex);
  LUT.ltex = gl.createTexture(); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_3D, LUT.ltex);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_3D, k, v);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGB16F, d.size, d.size, d.size, 0, gl.RGB, gl.FLOAT, f32);
  if (gl.getError() !== gl.NO_ERROR) return false;
  gl.uniform3fv(gl.getUniformLocation(LUT.prog, "uMin"), d.dmin); gl.uniform3fv(gl.getUniformLocation(LUT.prog, "uMax"), d.dmax);
  gl.uniform1f(gl.getUniformLocation(LUT.prog, "uN"), d.size);
  return true;
}
function lutDraw() {
  const v = LUT.vid, gl = LUT.gl, cv = LUT.cv; if (!LUT.ready || !v || !gl || v.readyState < 2 || !v.videoWidth) return false;
  const host = $("preview"), w = host.clientWidth, h = host.clientHeight, dpr = window.devicePixelRatio || 1;
  const W = Math.max(2, Math.round(w * dpr)), H = Math.max(2, Math.round(h * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const va = v.videoWidth / v.videoHeight, ca = W / H;                  // khung đen hai bên giống object-fit: contain
  let vw = W, vh = H; if (va > ca) vh = Math.round(W / va); else vw = Math.round(H * va);
  gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.viewport(Math.round((W - vw) / 2), Math.round((H - vh) / 2), vw, vh);
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, LUT.vtex);
  try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, v); } catch (e) { return false; }
  gl.uniform1i(gl.getUniformLocation(LUT.prog, "uOn"), LUT.on ? 1 : 0);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  cv.style.display = "block"; LUT.last = performance.now();
  return true;
}
function lutLoop() {                                            // vẽ lại mỗi khung hình mới của video (requestVideoFrameCallback), dự phòng rAF
  const v = LUT.vid; if (!v || !LUT.ready) return;
  const id = ++LUT.loopId;
  const tick = () => { if (id !== LUT.loopId) return; lutDraw(); schedule(); };
  const schedule = () => { if (id !== LUT.loopId || LUT.vid !== v) return; if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(tick); else requestAnimationFrame(tick); };
  tick();
}
function lutUi() {
  const b = $("plLut"); if (!b) return;
  const has = LUT.ready;
  b.disabled = !has; b.setAttribute("aria-pressed", has && LUT.on ? "true" : "false");
  b.title = has ? "Bật/tắt LUT trên khung xem (chỉ khung xem, không đổi gì trong DaVinci): " + LUT.name : "Clip này không gắn LUT (hoặc không đọc được file LUT): đang hiện màu gốc của proxy";
}
async function lutAttach(c, v) {                                // gọi từ plOpen sau khi tạo video
  lutDetach(); LUT.vid = v;
  if (!c || !c.lut) { lutUi(); return; }
  let d = LUT.cache.get(c.lut);
  if (d === undefined) { const r = await api().lut_cube(c.uid); d = r && r.b64 ? r : { error: (r && r.error) || "none" }; LUT.cache.set(c.lut, d); }
  if (LUT.vid !== v) return;                                    // đã đổi clip trong lúc chờ
  if (d.error) { $("plNote").textContent = (d.error === "none" ? "" : "LUT: " + d.error + " - hiện màu gốc"); lutUi(); return; }
  if (LUT.loaded !== c.lut) { if (!lutUpload(d)) { $("plNote").textContent = "WebGL không nạp được LUT - hiện màu gốc"; lutUi(); return; } LUT.loaded = c.lut; }
  LUT.name = d.title; LUT.ready = true; lutUi();
  const note = $("plNote"); if (!note.textContent) note.textContent = "Màu theo LUT " + d.title;
  lutLoop();
}
function lutDetach() {
  LUT.loopId++; LUT.ready = false; LUT.vid = null;
  if (LUT.cv) LUT.cv.style.display = "none";
  lutUi();
}
document.addEventListener("click", (e) => {
  if (e.target.id !== "plLut" || e.target.disabled) return;
  LUT.on = !LUT.on; lutUi(); lutDraw();
});
window.addEventListener("resize", () => { if (LUT.ready) lutDraw(); });

/* ---- trình phát ---- */
function plTime() {
  if (!PL.vid) return;
  $("plTime").textContent = fmtF(PL.vid.currentTime, PL.fps) + " / " + fmtF(PL.dur, PL.fps);
  if (!SK.drag) $("plSeek").value = PL.dur ? Math.round(PL.vid.currentTime / PL.dur * 1000) : 0;
}
function plToggle() {
  if (!PL.vid || !PL.ok) return;
  if (PL.vid.paused) PL.vid.play(); else PL.vid.pause();
}
function plStop() {
  const v = PL.el;
  if (v) { try { v.pause(); } catch (e) { /* bỏ qua */ } v.style.opacity = "0"; v.removeAttribute("src"); v.load(); }       // giữ thẻ, chỉ bỏ nguồn
  PL.vid = null; PL.ok = false; PL.edge = null; PL.tried = false; PL.kf = null; SK.want = null; SK.busy = false; SK.drag = false; lutDetach();
  $("player").classList.add("hidden");
}
function plEl() {                                               // MỘT thẻ <video> dùng cho mọi clip; sự kiện gắn một lần
  if (PL.el) return PL.el;
  const v = document.createElement("video");
  v.className = "pv"; v.preload = "auto"; v.playsInline = true; v.crossOrigin = "anonymous"; v.controls = false; v.muted = false; v.style.opacity = "0";
  const fallback = () => {                                      // dùng bản xem nhẹ ffmpeg (H.264) khi WebView2 không giải mã được hình
    const o = PL.open;
    if (!o || PL.uid !== o.uid || o.transcode) { $("plNote").textContent = "Không phát được proxy này"; return; }
    $("plNote").textContent = "Đang tạo bản xem nhẹ..."; PL.tried = true;
    plOpen(curClip(), true);
  };
  v.addEventListener("loadedmetadata", () => {
    // Đo 18/11/2026: proxy HEVC (hvc1) trong WebView2 KHÔNG báo lỗi, chỉ ra tiếng mà không có hình (videoWidth = 0).
    if (PL.vid !== v) return;
    if (!v.videoWidth) return fallback();
    PL.ok = true; if (v.duration) PL.dur = v.duration; plTime(); plRenderIo(curClip());
  });
  v.addEventListener("timeupdate", () => { plHead(); plTime(); });
  v.addEventListener("play", () => { $("plPlay").textContent = "❚❚"; });
  v.addEventListener("pause", () => { $("plPlay").textContent = "▶"; });
  v.addEventListener("seeked", () => { SK.busy = false; clearTimeout(SK.timer); lutDraw(); plPump(); });
  v.addEventListener("loadeddata", () => { if (PL.vid === v) v.style.opacity = "1"; lutDraw(); });
  v.addEventListener("error", () => { if (v.getAttribute("src")) fallback(); });          // WebView2 không phát được định dạng này -> bản xem nhẹ
  PL.el = v; return v;
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
  const v = plEl();
  if (v.parentNode !== $("preview")) $("preview").appendChild(v);
  if (lutGL() && LUT.cv.parentNode !== $("preview")) $("preview").appendChild(LUT.cv);
  SK.want = null; SK.busy = false; SK.drag = false; PL.kf = null; PL.open = { uid, transcode: !!transcode };
  v.style.opacity = "0"; PL.vid = v; PL.ok = false;
  v.src = r.url;
  $("player").classList.remove("hidden");
  lutAttach(c, v);
  if (!transcode) api().keyframes(uid).then((k) => { if (PL.uid === uid && k && k.kf) PL.kf = k.kf; });
}
$("plPlay").onclick = plToggle;
$("preview").addEventListener("click", () => { PL.focus = true; plToggle(); });
$("waveBox").addEventListener("mousedown", (ev) => {              // bấm vào sóng âm: lướt tới chỗ đó
  const c = curClip(); if (!c || !(c.dur > 0)) return;
  PL.focus = true; const r = $("waveBox").getBoundingClientRect();
  plSeek(Math.max(0, Math.min(c.dur, (ev.clientX - r.left) / r.width * c.dur)));
});
$("plSeek").addEventListener("mousedown", () => { SK.drag = true; });
$("plSeek").addEventListener("input", () => { if (PL.vid) plSeek($("plSeek").value / 1000 * PL.dur, { fast: SK.drag }); });
const plSeekRelease = () => { if (!SK.drag) return; SK.drag = false; if (PL.vid) plSeek($("plSeek").value / 1000 * PL.dur); };     // thả: nhảy chính xác
$("plSeek").addEventListener("change", plSeekRelease);
document.addEventListener("mouseup", plSeekRelease);
$("plRate").addEventListener("change", () => { if (PL.vid) PL.vid.playbackRate = +$("plRate").value; });
document.addEventListener("mousedown", (e) => {               // bấm ra ngoài cột phải: mũi tên lại đi chuyển clip
  if (!e.target.closest(".col-right, .p3-center")) { PL.focus = false; PL.edge = null; }
  else if (!e.target.closest(".h")) { /* giữ PL.edge để mũi tên vẫn chỉnh mép đang chọn */ }
}, true);

/* ---- phím: Space, I, O, mũi tên (chỉ khi con trỏ ở cột phải / vừa chọn mép) - capture để chạy trước phím lưới ---- */
document.addEventListener("keydown", (e) => {
  if (page !== 2 && page !== 3) return;
  if (page === 3 && !PL.focus && PL.vid && !e.target.closest(".p3-right")) PL.focus = true;      // Bước 3: ←/→ luôn chỉnh frame
  if (!$("modal").classList.contains("hidden")) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== "range" || e.target.isContentEditable) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.code === "Space") { e.preventDefault(); e.stopPropagation(); plToggle(); return; }
  if (page !== 3 && (e.code === "KeyI" || e.code === "KeyO")) return;                               // I/O chỉ ở Bước 3
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
