/* measure_seek.js - đo độ mượt khi RÊ trong panel (chạy bởi tools/panel_do_luot.py trong cửa sổ pywebview thật).
   Mô phỏng rê bằng sự kiện giả (60 lần/giây, 3 giây, từ đầu tới cuối clip) trên 3 chỗ:
     bar   = thanh lướt video (#plSeek: mousedown, input..., change, mouseup)
     wave  = bấm-quét trên sóng âm (#waveBox: mousedown liên tiếp)
     iobar = kéo mép In của thanh In/Out (.h hin: mousedown, mousemove trên document, mouseup)
   Đo: thời gian xử lý của mỗi sự kiện (ms), số lần gọi Python (pywebview api) và fetch trong lúc rê, longtask, số hình thật sự hiện ra (requestVideoFrameCallback),
   độ trễ từ sự kiện tới hình kế tiếp, lần đứng hình lâu nhất, khung rớt. Chỉ đọc; không gọi hàm ghi In/Out. */
const _sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const _pct = (a, p) => { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); return +s[Math.min(s.length - 1, Math.floor(p * s.length))].toFixed(1); };
async function _gpu() {
  const o = { cores: navigator.hardwareConcurrency, ua: navigator.userAgent.replace(/.*(Edg\/[\d.]+).*/, "$1") };
  try { const c = document.createElement("canvas"), gl = c.getContext("webgl2"), e = gl && gl.getExtension("WEBGL_debug_renderer_info"); o.webgl = e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : (gl ? "webgl2" : "không có webgl2"); } catch (e) { o.webgl = "lỗi " + e; }
  try { const d = await navigator.mediaCapabilities.decodingInfo({ type: "file", video: { contentType: 'video/mp4; codecs="avc1.640032"', width: 1920, height: 1080, bitrate: 40e6, framerate: 50 } }); o.h264 = { supported: d.supported, smooth: d.smooth, powerEfficient: d.powerEfficient }; } catch (e) { o.h264 = "lỗi " + e; }
  return o;
}
function _instrument() {                                          // đếm gọi Python và fetch
  const calls = {}; let fetches = 0;
  const api = window.pywebview && window.pywebview.api, orig = {};
  if (api) for (const k of Object.keys(api)) if (typeof api[k] === "function") { orig[k] = api[k]; api[k] = (...a) => { calls[k] = (calls[k] || 0) + 1; return orig[k](...a); }; }
  const of = window.fetch; window.fetch = (...a) => { fetches++; return of.apply(window, a); };
  return { calls, get fetches() { return fetches; }, restore() { if (api) for (const k in orig) api[k] = orig[k]; window.fetch = of; } };
}
async function _scenario(name, drive) {
  const v = PL.vid; if (!v || !PL.ok) return { name, error: "chưa mở clip" };
  try { v.pause(); } catch (e) { /* bỏ qua */ }
  v.currentTime = 0; await _sleep(500);
  const ins = _instrument(), hand = [], longs = [], frames = [];
  let po = null; try { po = new PerformanceObserver((l) => { for (const e of l.getEntries()) longs.push(Math.round(e.duration)); }); po.observe({ entryTypes: ["longtask"] }); } catch (e) { /* không hỗ trợ */ }
  let rv = 0; const onF = (now, md) => { frames.push([now, md.mediaTime]); rv = v.requestVideoFrameCallback(onF); }; rv = v.requestVideoFrameCallback(onF);
  if (typeof FR !== "undefined") FR.drawHook = (i) => frames.push([performance.now(), i / (FR.fps || 25)]);      // khung vẽ từ RAM cũng tính là một hình hiện ra
  const q0 = v.getVideoPlaybackQuality(), sends = [], steps = 180;
  const t0 = performance.now();
  await drive({ steps, v, mark: (fn) => { const a = performance.now(); sends.push(a); fn(); hand.push(performance.now() - a); } });
  const tEnd = performance.now();
  let settle = 0; { const a = performance.now(); for (let k = 0; k < 300; k++) { if (!(typeof FR !== "undefined" && FR.active) && !v.seeking && !(typeof SK !== "undefined" && (SK.busy || SK.want != null))) break; await _sleep(10); } settle = Math.round(performance.now() - a); }
  await _sleep(400);
  if (typeof FR !== "undefined") FR.drawHook = null;
  v.cancelVideoFrameCallback(rv); if (po) po.disconnect(); ins.restore();
  const q1 = v.getVideoPlaybackQuality(), secs = (tEnd - t0) / 1000;
  const during = frames.filter((f) => f[0] >= t0 && f[0] <= tEnd + 50);
  const lat = []; let j = 0;                                         // độ trễ: từ mỗi sự kiện tới hình đầu tiên hiện SAU nó
  for (const s of sends) { while (j < frames.length && frames[j][0] < s) j++; if (j < frames.length) lat.push(frames[j][0] - s); }
  const gaps = []; for (let i = 1; i < during.length; i++) gaps.push(during[i][0] - during[i - 1][0]);
  return { name, su_kien: sends.length, xu_ly_su_kien_ms: { tb: hand.length ? +(hand.reduce((x, y) => x + y, 0) / hand.length).toFixed(2) : null, p95: _pct(hand, 0.95), max: _pct(hand, 1) },
    goi_python: ins.calls, goi_fetch: ins.fetches, longtask_ms: longs, hinh_hien: during.length, hinh_moi_giay: +(during.length / secs).toFixed(1),
    tre_den_hinh_ms: { tb: lat.length ? +(lat.reduce((x, y) => x + y, 0) / lat.length).toFixed(1) : null, p50: _pct(lat, 0.5), p95: _pct(lat, 0.95), max: _pct(lat, 1) },
    dung_hinh_ms: { tb: gaps.length ? +(gaps.reduce((x, y) => x + y, 0) / gaps.length).toFixed(1) : null, max: _pct(gaps, 1) }, khung_rot: (q1.droppedVideoFrames || 0) - (q0.droppedVideoFrames || 0), cho_hinh_chinh_xac_ms: settle };
}
function _ev(type, target, props) { const e = new MouseEvent(type, Object.assign({ bubbles: true, cancelable: true, view: window }, props || {})); target.dispatchEvent(e); return e; }
async function measureAll() {
  const mode = window.MEASURE_MODE || "";
  if (mode.indexOf("lut_off") >= 0 && typeof LUT !== "undefined") { LUT.on = false; if (LUT.cv) LUT.cv.style.display = "none"; }
  if (typeof FR !== "undefined" && mode.indexOf("no_ram") < 0) { for (let k = 0; k < 600 && !(FR.done || FR.err); k++) await _sleep(100); }          // chờ kho khung nạp xong (đo riêng thời gian nạp ở ram.kho.load_s)
  if (mode.indexOf("no_ram") >= 0 && typeof FR !== "undefined") { FR.err = "tắt khi đo"; }
  if (mode.indexOf("preoff") >= 0 && typeof PL !== "undefined" && PL.pre) { PL.preOn = false; PL.pre.removeAttribute("src"); PL.pre.load(); }          // G1(b): tắt bộ giải mã thứ hai (tải trước clip kế)
  if (mode.indexOf("nodwell") >= 0) { const st0 = window.setTimeout; window.setTimeout = (f, ms, ...a) => (ms === 220 || ms === 250 ? 0 : st0(f, ms, ...a)); }  // G1(a): bỏ nhảy chính xác sau khi dừng tay
  const out = { mode, gpu: await _gpu(), clip: curClip() && curClip().name, dur: PL.dur, kf: PL.kf ? PL.kf.length : null, mo_clip_ms: PL.openMs, lut: !!(typeof LUT !== "undefined" && LUT.ready), kq: [] };
  const bar = $("plSeek"), dur = PL.dur;
  out.kq.push(await _scenario("bar", async (c) => {
    c.mark(() => _ev("mousedown", bar));
    for (let i = 0; i <= c.steps; i++) { c.mark(() => { bar.value = Math.round(i / c.steps * 1000); bar.dispatchEvent(new Event("input", { bubbles: true })); }); await _sleep(1000 / 60); }
    c.mark(() => { bar.dispatchEvent(new Event("change", { bubbles: true })); _ev("mouseup", document); });
  }));
  await _sleep(800);
  const wb = $("waveBox"), wr = wb.getBoundingClientRect();
  out.kq.push(await _scenario("wave", async (c) => {
    for (let i = 0; i <= c.steps; i++) { c.mark(() => _ev("mousedown", wb, { clientX: wr.left + 2 + (wr.width - 4) * i / c.steps, clientY: wr.top + 10 })); await _sleep(1000 / 60); }
  }));
  await _sleep(800);
  const ib = $("ioBar"), h = ib.querySelector(".h.hin");
  if (h) {
    const ir = ib.getBoundingClientRect(); const x0 = h.getBoundingClientRect().left + 2;
    out.kq.push(await _scenario("iobar", async (c) => {
      c.mark(() => _ev("mousedown", h, { clientX: x0, clientY: ir.top + 5 }));
      for (let i = 0; i <= c.steps; i++) { c.mark(() => _ev("mousemove", document, { clientX: ir.left + 2 + (ir.width - 4) * i / c.steps * 0.9, clientY: ir.top + 5 })); await _sleep(1000 / 60); }
      c.mark(() => _ev("mouseup", document));
    }));
  } else out.kq.push({ name: "iobar", error: "clip chưa có thanh In/Out để kéo" });
  // đối chứng: gán thẳng currentTime (cách trình duyệt thô nhất)
  out.kq.push(await _scenario("cu_gan_thang", async (c) => { for (let i = 0; i <= c.steps; i++) { c.mark(() => { PL.vid.currentTime = dur * i / c.steps; }); await _sleep(1000 / 60); } }));
  out.ram = await _ram();
  out.mau = await _colorCheck();
  return out;
}
async function _ram() {
  const o = {};
  if (typeof FR === "undefined") return { kho: "không có" };
  o.kho = { n: FR.n, total: FR.total, done: FR.done, err: FR.err, load_s: FR.loadS, ram_python_MB: +(FR.bytes / 1048576).toFixed(1), bitmap_trong_js: FR.bmp.size };
  try { o.python = await window.pywebview.api.frames_stats(); } catch (e) { o.python = String(e); }
  if (performance.memory) o.js_heap_MB = +(performance.memory.usedJSHeapSize / 1048576).toFixed(1);
  return o;
}
function _mean(src, w, h) {                                       // trung bình RGB của một nguồn (canvas/video) thu về lưới 64x36
  const c = document.createElement("canvas"); c.width = 64; c.height = 36; const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(src, 0, 0, 64, 36);
  const d = g.getImageData(0, 0, 64, 36).data, m = [0, 0, 0]; for (let i = 0; i < d.length; i += 4) { m[0] += d[i]; m[1] += d[i + 1]; m[2] += d[i + 2]; } const n = d.length / 4; return m.map((x) => x / n);
}
async function _colorCheck() {                                    // G3: màu khung RAM so với khung video chính xác ở cùng thời điểm (cùng LUT)
  if (typeof FR === "undefined" || !frReady()) return { error: "chưa có kho khung" };
  const v = PL.vid, res = [], pts = [0.15, 0.35, 0.55, 0.75, 0.9];
  for (const f of pts) {
    const t = PL.dur * f; v.currentTime = t; await new Promise((r) => { const h = () => { v.removeEventListener("seeked", h); r(); }; v.addEventListener("seeked", h); setTimeout(r, 3000); }); await _sleep(250);
    const vid = (typeof LUT !== "undefined" && LUT.ready && LUT.on && LUT.cv && LUT.cv.style.display !== "none") ? LUT.cv : v;
    let a;
    try { a = _mean(vid, 0, 0); } catch (e) { return { error: "không đọc được pixel video: " + e }; }
    const idx = Math.max(0, Math.min(FR.n - 1, Math.round(t * FR.fps))), bm = await createImageBitmap(await (await fetch(FR.url + "/" + idx)).blob());
    const b = _mean(bm, 0, 0); bm.close();
    res.push({ t: +t.toFixed(1), video: a.map((x) => +x.toFixed(1)), ram: b.map((x) => +x.toFixed(1)), lech_tb: +((Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2])) / 3).toFixed(2) });
  }
  return { nguon_so_sanh: (typeof LUT !== "undefined" && LUT.ready) ? "canvas WebGL LUT" : "thẻ video", diem: res, lech_tb_max: Math.max(...res.map((x) => x.lech_tb)) };
}
