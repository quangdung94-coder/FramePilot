/* player.js - Trình phát proxy + kéo chỉnh In/Out ở cột phải Bước 2 (ADR-0016).
   Chỉ vẽ và nhận thao tác; phát file qua máy chủ cục bộ 127.0.0.1 (troly_play.py), lưu In/Out đặt tay vào kế hoạch panel
   (api.set_inout), ghi vào DaVinci chỉ khi bấm nút + xác nhận. Phím đọc bằng event.code, bỏ qua khi đang gõ ô chữ. */
"use strict";

const PL = { openMs: 0, t0: 0, range: null, uid: null, vid: null, el: null, open: null, kf: null, fps: 25, dur: 0, ok: false, edge: null, focus: false, drag: null, hoverT: null, jklRate: 0, jklTimer: 0 };
/* Việc 2 (ADR-0023): lướt mượt. Chỉ gửi lệnh nhảy khi lệnh trước xong (seeked), lệnh mới thay lệnh cũ chưa gửi; đang KÉO thì nhảy theo keyframe
   (giải mã 1 khung), THẢ ra thì nhảy chính xác. Dùng lại MỘT thẻ <video> cho mọi clip. Không tạo proxy mới. */
const SK = { want: null, fast: false, busy: false, drag: false, timer: 0, sent: 0, seeks: 0, dwell: 0 };
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
    a = c.sug.in_s; b = c.sug.out_s; cls = "io-sug"; tcls = "sug"; rule = "Gợi ý " + ({ speech: "theo lời nói", rule: "theo quy tắc bin", live: "tức thời theo quy tắc bin" }[c.sug.src] || "") + (c.sug.src === "speech" ? "" : " (" + c.sug.rule + ")") + " - bấm A để nhận, hoặc kéo mép / I, O để đặt tay";
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
  const x = Math.max(0, Math.min(100, (plCurT() / PL.dur) * 100)).toFixed(2) + "%";
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
function plMark(which) {                                       // phím I / O: đặt tại vị trí con trỏ chuột (hover) hoặc đầu phát
  const c = curClip(); if (!c || (!PL.vid && PL.hoverT == null)) return;
  const t = (PL.hoverT != null) ? PL.hoverT : PL.vid.currentTime, [a, b] = plCurRange();
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
  if (Math.abs(v.currentTime - tt) < 0.0005 && !v.seeking) { frRelease(); plHead(); plTime(); return; }
  SK.busy = true; SK.seeks++; SK.sent = performance.now();
  clearTimeout(SK.timer); SK.timer = setTimeout(() => { SK.busy = false; plPump(); }, 1500);        // phòng seeked không bao giờ tới
  v.currentTime = tt;
}
function plSeek(t, opt) {                                       // opt.fast: đang rê/kéo -> vẽ khung từ RAM (không đụng video), chưa có RAM thì nhảy keyframe; mặc định: chính xác
  if (!PL.vid) return;
  if (opt && opt.fast && frReady()) {
    const at = Math.max(0, Math.min(PL.dur || 0, t));
    SK.want = null; clearTimeout(SK.dwell); frScrub(at);
    SK.dwell = setTimeout(() => { if (PL.vid) { SK.fast = false; SK.want = at; plPump(); } }, FR_DWELL_MS);       // dừng tay chưa thả: nhảy chính xác
    return;
  }
  SK.want = Math.max(0, Math.min(PL.dur || 0, t)); SK.fast = !!(opt && opt.fast);
  clearTimeout(SK.dwell);
  if (SK.fast) {                                                // đang kéo mà dừng tay (chưa thả chuột) ~0,22 s: nhảy CHÍNH XÁC tới hình đó, khỏi chờ thả
    const at = SK.want;
    SK.dwell = setTimeout(() => { if (PL.vid) { SK.fast = false; SK.want = at; plPump(); } }, 220);
  }
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
  if (!h) { plDragScrub(ev, $("ioBar")); return; }
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
function lutInitGL(st, cv) {
  if (st.gl) return st.gl;
  const gl = cv.getContext("webgl2", { alpha: false, antialias: false, preserveDrawingBuffer: true });
  if (!gl) return null;
  const sh = (t, src) => { const x = gl.createShader(t); gl.shaderSource(x, src); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
  try {
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, LUT_VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, LUT_FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    st.vtex = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, st.vtex);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    gl.uniform1i(gl.getUniformLocation(pr, "uV"), 0); gl.uniform1i(gl.getUniformLocation(pr, "uL"), 1);
    st.prog = pr; st.cv = cv; st.gl = gl;
  } catch (e) { st.gl = null; return null; }
  return gl;
}
function lutGL() {
  if (LUT.gl) return LUT.gl;
  const cv = document.createElement("canvas"); cv.className = "pv-lut"; cv.style.display = "none";
  return lutInitGL(LUT, cv);
}
function lutUploadTo(st, d, gl) {
  if (!gl) return false;
  const bin = atob(d.b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const f32 = new Float32Array(u8.buffer);
  if (st.ltex) gl.deleteTexture(st.ltex);
  st.ltex = gl.createTexture(); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_3D, st.ltex);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_3D, k, v);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGB16F, d.size, d.size, d.size, 0, gl.RGB, gl.FLOAT, f32);
  if (gl.getError() !== gl.NO_ERROR) return false;
  gl.uniform3fv(gl.getUniformLocation(st.prog, "uMin"), d.dmin); gl.uniform3fv(gl.getUniformLocation(st.prog, "uMax"), d.dmax);
  gl.uniform1f(gl.getUniformLocation(st.prog, "uN"), d.size);
  return true;
}
function lutUpload(d) { return lutUploadTo(LUT, d, lutGL()); }
function lutDrawTo(st, host, on) {
  const v = st.vid, gl = st.gl, cv = st.cv; if (!st.ready || !v || !gl || !host || v.readyState < 2 || !v.videoWidth) return false;
  const w = host.clientWidth, h = host.clientHeight, dpr = window.devicePixelRatio || 1;
  if (w < 2 || h < 2) return false;
  const W = Math.max(2, Math.round(w * dpr)), H = Math.max(2, Math.round(h * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const va = v.videoWidth / v.videoHeight, ca = W / H;                  // khung đen hai bên giống object-fit: contain
  let vw = W, vh = H; if (va > ca) vh = Math.round(W / va); else vw = Math.round(H * va);
  gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.viewport(Math.round((W - vw) / 2), Math.round((H - vh) / 2), vw, vh);
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, st.vtex);
  try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, v); } catch (e) { return false; }
  gl.uniform1i(gl.getUniformLocation(st.prog, "uOn"), on ? 1 : 0);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  cv.style.display = "block"; st.last = performance.now();
  return true;
}
function lutDraw() { return lutDrawTo(LUT, $("preview"), LUT.on); }
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
const LUT_EL = new WeakMap();
function lutDetachEl(host) {
  const st = host && LUT_EL.get(host);
  if (!st) return;
  st.loopId++; st.ready = false; st.vid = null;
  if (st.cv) st.cv.style.display = "none";
}
async function lutAttachEl(c, v, host) {
  if (!host) return;
  let st = LUT_EL.get(host);
  if (!st) {
    const cv = document.createElement("canvas");
    cv.className = "pv-lut"; cv.style.cssText = "display:none;position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2";
    host.appendChild(cv);
    st = { cv, gl: null, prog: null, vtex: null, ltex: null, ready: false, loopId: 0, vid: null, loaded: null, last: 0 };
    LUT_EL.set(host, st);
  }
  lutDetachEl(host); st.vid = v;
  if (!c || !c.lut) return;
  let d = LUT.cache.get(c.lut);
  if (d === undefined) { const r = await api().lut_cube(c.uid); d = r && r.b64 ? r : { error: (r && r.error) || "none" }; LUT.cache.set(c.lut, d); }
  if (st.vid !== v || v.parentNode !== host) return;
  if (d.error) return;
  const gl = lutInitGL(st, st.cv); if (!gl) return;
  if (st.loaded !== c.lut) { if (!lutUploadTo(st, d, gl)) return; st.loaded = c.lut; }
  if (!st.cv.parentNode) host.appendChild(st.cv);
  st.ready = true;
  const id = ++st.loopId;
  const drawOnce = () => { if (id === st.loopId && st.vid === v && v.parentNode === host) lutDrawTo(st, host, true); };
  const tick = () => { if (id !== st.loopId || st.vid !== v || v.parentNode !== host) return; lutDrawTo(st, host, true); schedule(); };
  const schedule = () => { if (id !== st.loopId || st.vid !== v || v.parentNode !== host) return; if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(tick); else requestAnimationFrame(tick); };
  v.addEventListener("loadeddata", drawOnce);
  v.addEventListener("seeked", drawOnce);
  tick();
}
document.addEventListener("click", (e) => {
  if (e.target.id !== "plLut" || e.target.disabled) return;
  LUT.on = !LUT.on; lutUi(); lutDraw();
});
window.addEventListener("resize", () => { if (LUT.ready) lutDraw(); });

/* ---- Kho khung nhỏ trong RAM (ADR-0016 bản 2, G2-G5): RÊ chuột/kéo thanh thì vẽ khung từ RAM lên canvas NGAY, không đụng thẻ video (nhảy video trong WebView2
   thật mất cả trăm ms đến hơn 1 giây). Khung do Python (ffmpeg ưu tiên thấp, chỉ đọc proxy, giữ trong RAM, không ghi đĩa) giải mã sẵn và phát qua
   máy chủ cục bộ. Thả chuột hoặc dừng ~0,25 s: thẻ video nhảy CHÍNH XÁC tới hình đó rồi canvas ẩn đi. Chưa nạp tới / lỗi: tự về cách cũ (nhảy keyframe). ---- */
const FR = { uid: null, url: "", n: 0, total: 0, fps: 25, done: false, err: "", cv: null, active: false, t: 0, bmp: new Map(), want: -1, pend: 0, poll: 0, drawHook: null, drawn: -1, loadS: 0, bytes: 0, warmed: null };
const FR_KEEP = 160;                                            // số ImageBitmap giữ trong JS (mỗi cái ~0,9 MB ở 640x360)
const FR_DWELL_MS = 250;
function frReady() { return !!(FR.url && FR.n > 0 && !FR.err); }
function frCanvas() {
  if (FR.cv) return FR.cv;
  const c = document.createElement("canvas"); c.id = "plFrame"; c.className = "pv-frame"; c.style.display = "none";
  FR.cv = c; return c;
}
function frReset() {
  clearTimeout(FR.poll); FR.uid = null; FR.url = ""; FR.n = 0; FR.total = 0; FR.done = false; FR.err = ""; FR.active = false; FR.want = -1; FR.drawn = -1; FR.warmed = null;
  for (const b of FR.bmp.values()) { try { b.close(); } catch (e) { /* bỏ qua */ } }
  FR.bmp.clear(); if (FR.cv) FR.cv.style.display = "none";
}
function frNote() {                                             // "Đang nạp khung xem nhanh x%" trong ghi chú trình phát; xong thì xóa
  const n = $("plNote"); if (!n) return;
  if (!FR.done && !FR.err && FR.total) { n.dataset.fr = "1"; n.textContent = "Đang nạp khung xem nhanh " + Math.min(99, Math.round(FR.n / FR.total * 100)) + "%"; }
  else if (n.dataset.fr === "1") { n.dataset.fr = ""; n.textContent = ""; }
}
async function frOpen(c) {                                       // gọi từ plOpen (clip mới)
  frReset(); if (!c) return;
  const uid = c.uid; FR.uid = uid;
  let r; try { r = await api().frames_open(uid, false, true); } catch (e) { r = { error: String(e) }; }
  if (FR.uid !== uid) return;
  if (!r || r.error) { FR.err = (r && r.error) || "không có kho khung"; return; }
  FR.url = r.url; FR.fps = r.fps || 25; FR.total = r.total || 0; FR.n = r.n || 0; FR.done = !!r.done;
  frPoll(uid);
}
async function frPoll(uid) {
  if (FR.uid !== uid || !FR.url) return;
  try { const d = await (await fetch(FR.url + "/info", { cache: "no-store" })).json(); if (FR.uid !== uid) return; if (d.error) FR.err = d.error; FR.n = d.n || 0; FR.done = !!d.done; FR.total = d.total || FR.total; FR.loadS = d.load_s || 0; FR.bytes = d.bytes || 0; }
  catch (e) { FR.err = "mất kết nối kho khung"; }
  frNote();
  if (FR.n > 0 && !FR.err) frWarm(uid);
  if (FR.err || FR.done) { frNote(); frPrefetch(uid); return; }
  FR.poll = setTimeout(() => frPoll(uid), 350);
}
function frPrefetch(uid) {                                      // nạp xong clip đang xem và đang rảnh: nạp trước clip kế + clip cùng giờ của máy quay khác (tối đa 3)
  if (FR.uid !== uid) return;
  const c = curClip(); if (!c) return;
  const want = [], nx = items[cur + 1]; if (nx) want.push(nx.uid);
  for (const o of items) { if (want.length >= 3) break; if (o.uid !== c.uid && o.camera && c.camera && o.camera !== c.camera && Math.abs((o.m0 || 0) - (c.m0 || 0)) < 0.5 && !want.includes(o.uid)) want.push(o.uid); }
  (async () => { for (const u of want) { if (FR.uid !== uid || SK.drag || FR.active) return; try { await api().frames_open(u, true); } catch (e) { return; } await new Promise((r) => setTimeout(r, 2500)); } })();
}
async function frWarm(uid) {                                    // khởi động sẵn: tạo canvas, nạp vài khung đầu thành ImageBitmap để lần rê ĐẦU TIÊN không phải chờ
  if (FR.warmed === uid) return; FR.warmed = uid;
  try {
    const host = $("preview"), cv = frCanvas(); if (host && cv.parentNode !== host) host.appendChild(cv);
    for (let k = 0; k < Math.min(6, FR.n); k++) { if (FR.uid !== uid) return; if (FR.bmp.has(k)) continue; const r = await fetch(FR.url + "/" + k, { cache: "no-store" }); if (!r.ok) return; const bm = await createImageBitmap(await r.blob()); if (FR.uid !== uid) { bm.close(); return; } frKeep(k, bm); }
    const g = cv.getContext("2d"); g.fillStyle = "#000"; g.fillRect(0, 0, 2, 2);
  } catch (e) { /* bỏ qua: chỉ là khởi động */ }
}
function frKeep(i, bm) {
  FR.bmp.set(i, bm);
  while (FR.bmp.size > FR_KEEP) { const k = FR.bmp.keys().next().value; try { FR.bmp.get(k).close(); } catch (e) { /* bỏ qua */ } FR.bmp.delete(k); }
}
function frDraw(bm, i) {
  const host = $("preview"), cv = frCanvas(); if (!host) return;
  if (cv.parentNode !== host) host.appendChild(cv);
  const w = host.clientWidth, h = host.clientHeight, dpr = window.devicePixelRatio || 1, W = Math.max(2, Math.round(w * dpr)), H = Math.max(2, Math.round(h * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const g = cv.getContext("2d"); g.fillStyle = "#000"; g.fillRect(0, 0, W, H);
  const s = Math.min(W / bm.width, H / bm.height), dw = bm.width * s, dh = bm.height * s;
  g.drawImage(bm, (W - dw) / 2, (H - dh) / 2, dw, dh);
  cv.style.display = "block"; FR.drawn = i;
  if (FR.drawHook) FR.drawHook(i);
}
async function frFetch() {                                      // lấy khung đang cần (chỉ giữ yêu cầu MỚI NHẤT); trong lúc chờ canvas giữ khung gần nhất đang hiện
  if (FR.pend) return; FR.pend = 1; const uid = FR.uid;
  try {
    for (let guard = 0; guard < 400; guard++) {
      const k = FR.want; if (k < 0 || FR.uid !== uid || !FR.active) break;
      let bm = FR.bmp.get(k);
      if (!bm) { const r = await fetch(FR.url + "/" + k, { cache: "no-store" }); if (!r.ok) break; bm = await createImageBitmap(await r.blob()); if (FR.uid !== uid) { bm.close(); break; } frKeep(k, bm); }
      if (FR.active) frDraw(bm, k);
      if (FR.want === k) break;
    }
  } catch (e) { /* khung hỏng: giữ khung đang hiện */ } finally { FR.pend = 0; }
}
function frScrub(t) {
  if (PL.vid && !PL.vid.paused) { try { PL.vid.pause(); } catch (e) { /* bỏ qua */ } }
  FR.active = true; FR.t = t;
  FR.want = Math.max(0, Math.min(FR.n - 1, Math.round(t * FR.fps)));
  const bm = FR.bmp.get(FR.want);
  if (bm) frDraw(bm, FR.want); else frFetch();
  plHead(); plTime();
}
function frRelease() {                                          // video đã nhảy chính xác xong: ẩn canvas
  if (!FR.active) return;
  FR.active = false; if (FR.cv) FR.cv.style.display = "none";
}
function plCurT() { return FR.active ? FR.t : (PL.vid ? PL.vid.currentTime : 0); }

/* ---- trình phát ---- */
function plTime() {
  if (!PL.vid && !FR.active) return;
  $("plTime").textContent = fmtF(plCurT(), PL.fps) + " / " + (PL.dur > 0 ? fmtF(PL.dur, PL.fps) : "chưa rõ độ dài");
  if (!SK.drag) $("plSeek").value = PL.dur ? Math.round(plCurT() / PL.dur * 1000) : 0;
  if (typeof p3TxNow === "function" && page === 3) p3TxNow();
}
function plToggle() {
  if (!PL.vid || !PL.ok) {                                       // Space không được im lặng: nói rõ vì sao chưa phát (chưa có proxy / proxy không giải mã được / đang mở)
    const c = curClip(), n = $("plNote").textContent;
    status(!c ? "Chưa chọn clip để phát." : /^Chưa có proxy/.test(n) ? "Chưa có proxy nên Space không phát được, chỉ xem hình tĩnh. Tạo proxy trong DaVinci rồi mở lại clip." : (n && /proxy/i.test(n)) ? n : "Clip này chưa sẵn sàng để phát (đang mở proxy), thử lại sau một lát.", "warn");
    return;
  }
  if (PL.vid.paused) PL.vid.play(); else PL.vid.pause();
}
function plStop() {
  const v = PL.el;
  if (v) { try { v.pause(); } catch (e) { /* bỏ qua */ } v.style.opacity = "0"; v.removeAttribute("src"); v.load(); }       // giữ thẻ, chỉ bỏ nguồn
  PL.vid = null; PL.ok = false; PL.edge = null; PL.kf = null; SK.want = null; SK.busy = false; SK.drag = false; clearTimeout(SK.dwell); frReset(); lutDetach();
  $("player").classList.add("hidden");
}
function plEl() {                                               // MỘT thẻ <video> dùng cho mọi clip; sự kiện gắn một lần
  if (PL.el) return PL.el;
  const v = document.createElement("video");
  v.className = "pv"; v.preload = "auto"; v.playsInline = true; v.crossOrigin = "anonymous"; v.controls = false; v.muted = false; v.style.opacity = "0";
  const noPlay = () => {                                        // WebView2 không giải mã được hình: chỉ báo rõ, KHÔNG tạo file nào (ADR-0029)
    const o = PL.open;
    if (!o || PL.uid !== o.uid) return;
    const c = curClip(), ten = c ? (c.name || c.rel || "này") : "này";
    $("plNote").textContent = "Không phát được proxy của clip " + ten + " (WebView2 không giải mã được định dạng, thường là HEVC hoặc ProRes). Nên tạo lại proxy H.264 trong DaVinci; tạm thời chỉ xem hình tĩnh.";
    plStop(); PL.uid = o.uid; $("player").classList.remove("hidden"); $("plCtl").classList.add("hidden");
  };
  v.addEventListener("loadedmetadata", () => {
    // Đo 18/11/2026: proxy HEVC (hvc1) trong WebView2 KHÔNG báo lỗi, chỉ ra tiếng mà không có hình (videoWidth = 0).
    if (PL.vid !== v) return;
    if (!v.videoWidth) return noPlay();
    PL.ok = true; if (v.duration) PL.dur = v.duration; plTime(); plRenderIo(curClip());
  });
  v.addEventListener("timeupdate", () => { plHead(); plTime(); });
  v.addEventListener("play", () => { $("plPlay").textContent = "❚❚"; });
  v.addEventListener("pause", () => { $("plPlay").textContent = "▶"; });
  v.addEventListener("seeked", () => { SK.busy = false; clearTimeout(SK.timer); lutDraw(); plPump(); if (SK.want == null && !SK.busy) frRelease(); });
  v.addEventListener("loadeddata", () => { if (PL.vid === v) { v.style.opacity = "1"; if (PL.t0) { PL.openMs = Math.round(performance.now() - PL.t0); PL.t0 = 0; } } lutDraw(); });
  v.addEventListener("error", () => { if (v.getAttribute("src")) noPlay(); });          // WebView2 không phát được định dạng này -> báo rõ
  PL.el = v; return v;
}
async function plOpen(c) {                                    // gọi từ showCur khi đổi clip
  plStop(); PL.uid = c ? c.uid : null;
  if (!c) return;
  const uid = c.uid, r = await api().play_info(uid);
  if (curClip() == null || curClip().uid !== uid) return;     // đã chuyển clip khác
  if (r.error) {                                              // không có proxy: nạp kho khung RAM từ file gốc (chỉ đọc) để vẫn lướt chuột mượt
    PL.fps = c.fps || PL.fps || 25; PL.dur = c.dur || 0;
    $("plNote").textContent = r.error === "Chưa có proxy" ? "Chưa có proxy (rê chuột để lướt nhanh)" : r.error;
    $("player").classList.remove("hidden"); $("plCtl").classList.add("hidden");
    if (r.error === "Chưa có proxy") frOpen(c);
    return;
  }
  $("plCtl").classList.remove("hidden"); $("plNote").textContent = "";
  PL.fps = r.fps || PL.fps; PL.dur = r.dur || 0;         // clip thiếu độ dài: KHÔNG mượn độ dài clip trước (hiện "chưa rõ độ dài" tới khi video báo)
  const v = plEl();
  if (v.parentNode !== $("preview")) $("preview").appendChild(v);
  if (lutGL() && LUT.cv.parentNode !== $("preview")) $("preview").appendChild(LUT.cv);
  SK.want = null; SK.busy = false; SK.drag = false; PL.kf = null; PL.open = { uid };
  v.style.opacity = "0"; PL.vid = v; PL.ok = false;
  PL.t0 = performance.now();                                    // đo thời gian từ lúc mở tới có hình (nút Đo lướt báo lại)
  v.src = r.url;
  $("player").classList.remove("hidden");
  lutAttach(c, v);
  frOpen(c); api().keyframes(uid).then((k) => { if (PL.uid === uid && k && k.kf) PL.kf = k.kf; });
}
$("plPlay").onclick = plToggle;
$("preview").addEventListener("click", () => { PL.focus = true; plToggle(); });
function plDragScrub(ev, box) {                                   // bấm vào sóng âm / thanh In/Out rồi rê: vẽ từ RAM theo chuột; thả chuột: nhảy chính xác
  const c = curClip(); if (!c || !(c.dur > 0)) return;
  PL.focus = true; const r = box.getBoundingClientRect(), dur = PL.dur || c.dur;
  const tAt = (x) => Math.max(0, Math.min(dur, (x - r.left) / r.width * dur));
  plSeek(tAt(ev.clientX), { fast: true });
  let last = tAt(ev.clientX), pend = false, lx = ev.clientX;
  const flush = () => { pend = false; last = tAt(lx); plSeek(last, { fast: true }); };
  const move = (m) => { lx = m.clientX; if (!pend) { pend = true; requestAnimationFrame(flush); } };        // gộp theo khung hình, mỗi khung vẽ một lần
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); plSeek(last); };
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
}
$("waveBox").addEventListener("mousedown", (ev) => plDragScrub(ev, $("waveBox")));
/* Live Hover Scrub chuẩn DaVinci: rê chuột ngang qua sóng âm hoặc thanh In/Out là lướt hình, KHÔNG cần giữ chuột trái */
function plAttachHoverScrub(box) {
  if (!box) return;
  let pend = false, lx = 0;
  const tAt = (x) => {
    const c = curClip(), dur = PL.dur || (c && c.dur) || 0, r = box.getBoundingClientRect();
    return dur > 0 && r.width > 0 ? Math.max(0, Math.min(dur, (x - r.left) / r.width * dur)) : null;
  };
  const flush = () => {
    pend = false;
    const t = tAt(lx);
    if (t == null) return;
    PL.hoverT = t;
    if (PL.vid) plSeek(t, { fast: true });
    else if (FR.url) frScrub(t);
  };
  box.addEventListener("mousemove", (e) => {
    if (e.buttons) return;
    lx = e.clientX;
    if (!pend) { pend = true; requestAnimationFrame(flush); }
  });
  box.addEventListener("mouseleave", () => {
    PL.hoverT = null;
    if (PL.vid && !PL.vid.paused) return;
  });
}
plAttachHoverScrub($("waveBox"));
plAttachHoverScrub($("ioBar"));
plAttachHoverScrub($("preview"));
plAttachHoverScrub($("plSeek"));

/* Hover Scrub ngay trên lưới thumbnail Page 2 (giống DaVinci Media Pool): rê ngang qua ảnh là lướt clip không cần nhấn Space */
(function initGridHoverScrub() {
  const grid = $("grid");
  if (!grid) return;
  let hoverTimer = 0, pend = false, lx = 0, curThumb = null, curCard = null;
  let line = document.createElement("div");
  line.className = "thumb-scrub";
  const flush = () => {
    pend = false;
    if (!curThumb || !curCard) return;
    const i = +curCard.dataset.i, c = items[i];
    if (!c || !(c.dur > 0)) return;
    const r = curThumb.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (lx - r.left) / Math.max(1, r.width)));
    if (line.parentNode !== curThumb) curThumb.appendChild(line);
    line.style.left = (pct * 100).toFixed(2) + "%";
    line.style.display = "block";
    const t = pct * c.dur;
    if (i === cur) {
      PL.hoverT = t;
      if (PL.vid) plSeek(t, { fast: true });
      else if (FR.url) frScrub(t);
    }
  };
  grid.addEventListener("mousemove", (e) => {
    if (page !== 2 || e.buttons) return;
    const th = e.target.closest(".thumb"), card = e.target.closest(".card");
    if (!th || !card) { line.style.display = "none"; return; }
    if (curCard !== card) {
      clearTimeout(hoverTimer);
      curCard = card; curThumb = th;
      const idx = +card.dataset.i;
      if (idx !== cur) {
        hoverTimer = setTimeout(() => {
          if (curCard === card && typeof moveCur === "function") { moveCur(idx); flush(); }
        }, 120);
      }
    }
    lx = e.clientX;
    if (!pend) { pend = true; requestAnimationFrame(flush); }
  });
  grid.addEventListener("mouseleave", () => {
    clearTimeout(hoverTimer);
    curCard = null; curThumb = null; PL.hoverT = null;
    line.style.display = "none";
  });
})();

function plJkl(action) {                                         // Cụm phím J - K - L chuẩn DaVinci
  const v = PL.vid; if (!v) return;
  clearInterval(PL.jklTimer); PL.jklTimer = 0;
  if (action === "k") {
    PL.jklRate = 0;
    if (!v.paused) v.pause();
    return;
  }
  if (action === "l") {
    PL.jklRate = PL.jklRate <= 0 ? 1 : Math.min(4, PL.jklRate * 2);
    v.playbackRate = PL.jklRate;
    if (v.paused) v.play().catch(() => {});
    return;
  }
  if (action === "j") {
    PL.jklRate = PL.jklRate >= 0 ? -1 : Math.max(-4, PL.jklRate * 2);
    if (!v.paused) v.pause();
    PL.jklTimer = setInterval(() => {
      if (!PL.vid || PL.jklRate >= 0) { clearInterval(PL.jklTimer); PL.jklTimer = 0; return; }
      const next = Math.max(0, PL.vid.currentTime + PL.jklRate * 0.08);
      plSeek(next, { fast: true });
      if (next <= 0) { PL.jklRate = 0; clearInterval(PL.jklTimer); PL.jklTimer = 0; }
    }, 80);
  }
}
$("plSeek").addEventListener("mousedown", () => { SK.drag = true; });
$("plSeek").addEventListener("input", () => { if (PL.vid) plSeek($("plSeek").value / 1000 * PL.dur, { fast: SK.drag }); });
const plSeekRelease = () => { if (!SK.drag) return; SK.drag = false; if (PL.vid) plSeek($("plSeek").value / 1000 * PL.dur); };     // thả: nhảy chính xác
$("plSeek").addEventListener("change", plSeekRelease);
document.addEventListener("mouseup", plSeekRelease);
$("plRate").addEventListener("change", () => { if (PL.vid) PL.vid.playbackRate = +$("plRate").value; });
document.addEventListener("mousedown", (e) => {               // bấm ra ngoài khung phát / sóng âm: 4 phím mũi tên lại di chuyển giữa các clip
  if (!e.target.closest(".col-right, #stageHost3, #waveBox, #ioBar")) { PL.focus = false; PL.edge = null; }
  else if (!e.target.closest(".h")) { /* giữ PL.edge để mũi tên vẫn chỉnh mép đang chọn */ }
}, true);

/* ---- phím: Space, I, O, mũi tên (chỉ khi con trỏ ở cột phải / vừa chọn mép) - capture để chạy trước phím lưới ---- */
document.addEventListener("keydown", (e) => {
  if (page !== 2 && page !== 3) return;
  if (e.target && e.target.closest && e.target.closest("#p3List")) PL.focus = false;
  if (!$("modal").classList.contains("hidden")) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== "range" || e.target.isContentEditable) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.code === "Space") { e.preventDefault(); e.stopPropagation(); plJkl("k"); plToggle(); return; }
  if (e.code === "KeyJ") { e.preventDefault(); e.stopPropagation(); plJkl("j"); return; }
  if (e.code === "KeyK") { e.preventDefault(); e.stopPropagation(); plJkl("k"); return; }
  if (e.code === "KeyL") { e.preventDefault(); e.stopPropagation(); plJkl("l"); return; }
  if (e.code === "KeyI") { e.preventDefault(); e.stopPropagation(); plMark("in"); return; }
  if (e.code === "KeyO") { e.preventDefault(); e.stopPropagation(); plMark("out"); return; }
  if ((e.code === "ArrowLeft" || e.code === "ArrowRight") && PL.focus && PL.vid) {
    e.preventDefault(); e.stopPropagation(); plNudge((e.code === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
  }
}, true);

document.addEventListener("keyup", (e) => {                     // nút đang có tiêu điểm (vd "Tự phân loại") sẽ bị Space bấm lại lúc nhả phím: chặn, Space ở Bước 2/3 chỉ để phát/dừng
  if (page !== 2 && page !== 3 || e.code !== "Space" || e.ctrlKey || e.altKey || e.metaKey) return;
  if (!$("modal").classList.contains("hidden")) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== "range" || e.target.isContentEditable) return;
  e.preventDefault(); e.stopPropagation();
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


/* ---- Đêm #2: nút "Đo lướt" (chỉ khi panel chạy --debug). Mô phỏng KÉO từ đầu tới cuối clip bằng sự kiện giả 60 lần/giây, đo: số hình thật sự hiện ra
   trong lúc kéo (mỗi "seeked" là một hình), độ trễ mỗi lần nhảy, lần đứng hình lâu nhất, số khung rớt, thời gian chờ hình chính xác sau khi thả. Ba cách: "cu" (mỗi sự kiện gán thẳng
   currentTime, như trước khi sửa), "keyframe" (hàng đợi một lệnh, nhảy theo keyframe, thả mới chính xác), "chinhxac" (hàng đợi một lệnh nhưng luôn chính xác).
   Chỉ ĐỌC; kết quả hiện ở ghi chú trình phát, console và lưu <data_root>	roly\debug. ---- */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function plWaitSeeked(v, ms) { return new Promise((res) => { let done = false; const f = () => { if (done) return; done = true; v.removeEventListener("seeked", f); res(); }; v.addEventListener("seeked", f); setTimeout(f, ms || 4000); }); }
async function plSweep(mode, ms) {
  const v = PL.vid, dur = PL.dur; if (!v || !PL.ok || !(dur > 1)) return { mode, error: "Chưa mở clip phát được" };
  v.pause(); SK.want = null; SK.busy = false;
  v.currentTime = 0; await plWaitSeeked(v, 4000); await sleep(150);
  const steps = Math.round(ms / (1000 / 60)), q0 = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : { droppedVideoFrames: 0, totalVideoFrames: 0 };
  let wanted = 0, seeked = 0, latSum = 0, latMax = 0, sentAt = 0, lastEv = 0, gapMax = 0, gapSum = 0;
  const onSeeked = () => {                                      // mỗi "seeked" = MỘT hình mới thật sự hiện ra (currentTime báo ngay vị trí đích nên không đo lệch bằng nó được)
    const now = performance.now(), lat = now - sentAt; seeked++; latSum += lat; latMax = Math.max(latMax, lat);
    if (lastEv) { const g = now - lastEv; gapSum += g; gapMax = Math.max(gapMax, g); }
    lastEv = now;
  };
  v.addEventListener("seeked", onSeeked);
  const t0 = performance.now();
  for (let i = 0; i <= steps; i++) {
    wanted = dur * i / steps; sentAt = performance.now();
    if (mode === "cu") v.currentTime = wanted; else plSeek(wanted, { fast: mode === "keyframe" });
    await sleep(1000 / 60);
  }
  const tEnd = performance.now(), rel = performance.now();
  if (mode === "keyframe") { SK.drag = false; plSeek(wanted); }                   // thả chuột: nhảy chính xác
  for (let k = 0; k < 400; k++) { if (!v.seeking && !SK.busy && SK.want == null) break; await sleep(10); }
  await sleep(120);
  const settle = Math.round(performance.now() - rel), err = Math.abs(v.currentTime - wanted);
  v.removeEventListener("seeked", onSeeked);
  const q1 = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : q0, secs = (tEnd - t0) / 1000;
  return { mode, ms, su_kien_keo: steps + 1, hinh_hien: seeked, hinh_hien_moi_giay: +(seeked / secs).toFixed(1), tre_moi_lan_tb_ms: seeked ? Math.round(latSum / seeked) : null, tre_cham_nhat_ms: Math.round(latMax),
    dung_hinh_tb_ms: seeked > 1 ? Math.round(gapSum / (seeked - 1)) : null, dung_hinh_lau_nhat_ms: Math.round(gapMax), khung_rot: (q1.droppedVideoFrames || 0) - (q0.droppedVideoFrames || 0), cho_hinh_chinh_xac_ms: settle, sai_so_cuoi_giay: +err.toFixed(3) };
}
async function plGpuInfo() {                                    // E5: card đồ họa WebView2 đang dùng và có giải mã H.264 bằng phần cứng không (chỉ ghi lại, không ép gì)
  const out = { hardwareConcurrency: navigator.hardwareConcurrency };
  try { const c = document.createElement("canvas"), gl = c.getContext("webgl2"), e = gl && gl.getExtension("WEBGL_debug_renderer_info"); out.webgl = e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : (gl ? "webgl2 (không đọc được tên card)" : "không có webgl2"); } catch (e) { out.webgl = "lỗi: " + e; }
  try {
    const d = await navigator.mediaCapabilities.decodingInfo({ type: "file", video: { contentType: 'video/mp4; codecs="avc1.640032"', width: 1920, height: 1080, bitrate: 40e6, framerate: 50 } });
    out.h264_1080p50 = { supported: d.supported, smooth: d.smooth, powerEfficient: d.powerEfficient };       // powerEfficient=true thường nghĩa là giải mã bằng phần cứng
  } catch (e) { out.h264_1080p50 = "lỗi: " + e; }
  return out;
}
async function plMeasure() {
  const note = $("plNote"), old = note.textContent;
  if (!PL.vid || !PL.ok) { note.textContent = "Đo lướt: mở một clip có proxy phát được trước"; return null; }
  const res = { clip: curClip() && curClip().name, dur: PL.dur, fps: PL.fps, nhan_keyframe: PL.kf ? PL.kf.length : 0, mo_clip_ms: PL.openMs, gpu: await plGpuInfo(), lan_do: [] };
  for (const mode of ["cu", "keyframe", "chinhxac"]) { note.textContent = "Đo lướt: " + mode + "…"; res.lan_do.push(await plSweep(mode, 3000)); await sleep(300); }
  note.textContent = old;
  console.log("DO_LUOT", JSON.stringify(res));
  try { await api().debug_save("do_luot_" + new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14), res); } catch (e) { /* bỏ qua */ }
  return res;
}
window.plMeasure = plMeasure;
window.addEventListener("pywebviewready", async () => { try { if (await api().debug_on()) $("plMeasure").classList.remove("hidden"); } catch (e) { /* bỏ qua */ } });
$("plMeasure").onclick = async () => { const r = await plMeasure(); if (r) $("plNote").textContent = r.lan_do.map((x) => x.mode + ": " + x.hinh_hien_moi_giay + " hình/s, đứng lâu nhất " + x.dung_hinh_lau_nhat_ms + " ms").join(" | "); };
