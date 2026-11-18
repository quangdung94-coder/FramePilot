/* step3.js - Trang Bước 3 · In / Out (ADR-0019; bố cục theo design/3_inout).
   Cột trái: clip theo bin. Giữa: trình phát (player.js) + sóng âm + thanh In/Out kéo tay. Phải: bảng quy tắc gợi ý từng bin.
   Chỉ vẽ và gọi Python (api.wave, set_bin_rule, reset_bin_rule, set_trad_trim). Gợi ý màu xanh không bao giờ tự ghi vào DaVinci. */
"use strict";

const WV = { uid: null, peaks: null, err: "", timer: null };
const P3 = { sig: "", rulesSig: "" };

/* Khối xem clip (hình + nút phát) nằm ở Bước 2 hoặc Bước 3: chuyển chỗ khi đổi bước, rồi trình phát tự mở lại */
function placeStage() {
  const box = $("stageBox"); if (!box) return;
  const host = page === 3 ? $("stageHost3") : $("stageHost2");
  if (box.parentNode !== host) { plStop(); PL.uid = null; host.appendChild(box); }
}

/* ---- cột trái ---- */
function p3Dot(c) {
  if (c.in_s != null) {
    const sameDv = c.dv && Math.abs(c.dv[0] - c.in_s) < 0.02 && Math.abs(c.dv[1] - c.out_s) < 0.02;
    return c.io_src === "manual" && !sameDv ? "man" : "dv";
  }
  return c.sug ? "sug" : "";
}
function renderPage3() {
  if (!S) return;
  const opts = S.stages.map((s, i) => `<option value="${i}">${esc(s.name)} (${s.count} clip)</option>`);
  if (S.outside) opts.push(`<option value="-1">Ngoài mọi giai đoạn (${S.outside} clip)</option>`);
  const sel3 = $("p3Stage"), want = String(gStage === null ? "" : gStage);
  const optHtml = opts.join("");
  if (sel3.innerHTML !== optHtml) sel3.innerHTML = optHtml;
  if (gStage === null && S.stages.length) { gStage = 0; gSub = null; renderPage2(true); return; }
  if (sel3.value !== want && document.activeElement !== sel3) sel3.value = want;
  const sig = items.map((c) => [c.uid, c.label, p3Dot(c), c.star ? 1 : 0].join("~")).join("|") + "#" + gStage;
  if (sig !== P3.sig) {
    P3.sig = sig;
    const s = stageObj(), order = [];
    if (s) s.bins.forEach((b) => order.push({ name: b.name, color: b.color }));
    order.push({ name: "", color: "#6A6A72" });
    let h = "";
    for (const g of order) {
      const rows = items.map((c, i) => [c, i]).filter(([c]) => (c.label || "") === g.name);
      if (!rows.length) continue;
      h += `<div class="p3-grp"><i style="background:${g.color}"></i>${esc(g.name || "Chưa xếp")}<span class="n">${rows.length}</span></div>` +
        rows.map(([c, i]) => `<div class="p3-clip${i === cur ? " cur" : ""}" data-i="${i}"><i class="dot ${p3Dot(c)}"></i><span class="t">${esc(c.name)}</span><span class="st">${c.star ? "★" : ""}</span><span class="tm">${c.time}</span></div>`).join("");
    }
    $("p3List").innerHTML = h || `<div class="dim12">${S.n ? "Không có clip trong giai đoạn này." : 'Bấm "Đọc clip" ở bước 1 trước.'}</div>`;
  }
  renderRules();
}
$("p3List").addEventListener("click", (e) => { const r = e.target.closest(".p3-clip"); if (r) { moveCur(+r.dataset.i); $("p3List").focus(); } });
$("p3Stage").onchange = (e) => { gStage = +e.target.value; gSub = null; saveUi(); renderPage2(true); renderPage3(); };
$("p3Star").onclick = () => toggleStar();

/* ---- clip đang chọn: tiêu đề, hộp thông tin, sóng âm ---- */
function renderPage3Cur(c) {
  if (!$("page3")) return;
  if (!c) { $("p3Name").textContent = "Chọn một clip"; $("p3Meta").textContent = ""; $("p3Cur").innerHTML = "<b>Clip đang chọn</b><span>Chưa chọn clip.</span>"; waveReset(null); return; }
  $("p3Name").textContent = c.name;
  $("p3Meta").textContent = `${c.label || "Chưa xếp"} · ${c.time} · dài ${durTxt(c.dur)}`;
  $("p3Star").textContent = c.star ? "★ Bỏ sao (J)" : "☆ Gắn sao (J)";
  $("p3Star").classList.toggle("active", !!c.star);
  const f = c.fps || 25, sug = c.sug;
  let h = `<b>Clip đang chọn · ${esc(c.label || "Chưa xếp")}</b>`;
  h += sug ? `Gợi ý: vào ${fmtF(sug.in_s, f)}, ra ${fmtF(sug.out_s, f)}, giữ ${fmtF(sug.dur, f)}<br><span class="dim12">${esc(sug.rule)}</span>` : "Gợi ý: clip quá ngắn, không gợi ý.";
  if (c.in_s != null) {
    const sameDv = c.dv && Math.abs(c.dv[0] - c.in_s) < 0.02 && Math.abs(c.dv[1] - c.out_s) < 0.02;
    h += c.io_src === "manual" && !sameDv ? `<br>Anh đặt tay: vào ${fmtF(c.in_s, f)}, ra ${fmtF(c.out_s, f)}${sug ? " (thắng gợi ý)" : ""}, chưa ghi vào DaVinci`
      : `<br>Đã có trong DaVinci: vào ${fmtF(c.in_s, f)}, ra ${fmtF(c.out_s, f)}`;
  }
  $("p3Cur").innerHTML = h;
  document.querySelectorAll("#p3List .p3-clip").forEach((el) => el.classList.toggle("cur", +el.dataset.i === cur));
  const el = document.querySelector(`#p3List .p3-clip[data-i="${cur}"]`); if (el) el.scrollIntoView({ block: "nearest" });
  if (page === 3) waveLoad(c);
}

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
  const sig = JSON.stringify([rows.map((x) => [x.name, x.r]), R.style, R.trad_trim]);
  if (sig === P3.rulesSig) return;
  if (tbl.contains(document.activeElement) || document.activeElement === $("tradTrim")) return;    // đang gõ: không dựng lại
  P3.rulesSig = sig;
  tbl.className = "rt" + (R.style === "traditional" ? " off" : "");
  tbl.innerHTML = '<tr><th>Bin</th><th>Tối thiểu (s)</th><th>Tối đa (s)</th><th>Trọn câu</th></tr>' + rows.map((x) =>
    `<tr data-bin="${esc(x.name)}"><td class="nm"><i style="background:${x.color}"></i>${x.name === "*" ? "Bin khác" : esc(x.name)}</td>` +
    `<td><input class="num${x.r.edited ? " ed" : ""}" data-f="min" inputmode="decimal" value="${num(x.r.min)}" aria-label="Tối thiểu ${esc(x.name)}"></td>` +
    `<td><input class="num${x.r.edited ? " ed" : ""}" data-f="max" inputmode="decimal" value="${x.r.whole ? "" : num(x.r.max)}" placeholder="—"${x.r.whole ? " disabled" : ""} aria-label="Tối đa ${esc(x.name)}"></td>` +
    `<td><input type="checkbox" data-f="whole"${x.r.whole ? " checked" : ""} aria-label="Giữ trọn câu ${esc(x.name)}"></td></tr>`).join("");
  $("rulesStyle").textContent = STYLE_NAME[R.style] || R.style;
  $("trStyleName").textContent = "Kiểu quay: " + (STYLE_NAME[R.style] || R.style);
  $("trStyleText").textContent = R.style === "traditional" ? "Đang dùng Truyền thống: bảng bên trên chưa áp dụng, chỉ cắt đầu/đuôi mỗi clip."
    : R.style === "psc" ? "Đang dùng PSC: gợi ý theo bảng bên trên. Chọn Truyền thống ở thanh trên thì bảng bị bỏ qua."
    : "Chưa chọn kiểu quay: gợi ý theo bảng bên trên, y như mặc định cũ. Chọn kiểu ở ô trên cùng.";
  $("tradTrim").value = num(R.trad_trim);
  $("tradTrim").classList.toggle("ed", Math.abs(R.trad_trim - R.trad_default) > 1e-9);
  $("rulesNote").textContent = R.bins.some((b) => b.edited) ? "Ô viền cam = anh đã sửa." : "Chưa sửa gì: đang dùng số mặc định.";
}
async function rulesChanged(e) {
  const tr = e.target.closest("tr[data-bin]"); if (!tr) return;
  const v = (f) => tr.querySelector(`[data-f="${f}"]`);
  const whole = v("whole").checked, val = (el) => String(el.value).trim().replace(",", ".");
  const st = await api().set_bin_rule(tr.dataset.bin, val(v("min")), whole ? null : val(v("max")), whole);
  P3.rulesSig = "";
  if (st && st.error) { status(st.error, "warn"); renderRules(); return; }
  setState(st);
  status("Đã lưu quy tắc " + (tr.dataset.bin === "*" ? "Bin khác" : tr.dataset.bin) + ". Chỉ đổi gợi ý màu xanh.", "ok");
}
$("rulesTbl").addEventListener("change", rulesChanged);
$("rulesTbl").addEventListener("keydown", (e) => { if (e.code === "Enter" && e.target.tagName === "INPUT") e.target.blur(); });
$("tradTrim").onchange = async () => {
  const st = await api().set_trad_trim(String($("tradTrim").value).trim().replace(",", "."));
  P3.rulesSig = "";
  if (st && st.error) { status(st.error, "warn"); renderRules(); return; }
  setState(st); status("Đã lưu số giây cắt của Truyền thống.", "ok");
};
$("tradTrim").addEventListener("keydown", (e) => { if (e.code === "Enter") e.target.blur(); });
$("rulesReset").onclick = async () => {
  const ok = await ask("Về mặc định?", "<p>Xóa mọi chỗ anh đã sửa trong bảng quy tắc và số giây cắt của Truyền thống. In/Out anh đã đặt tay không bị đụng.</p>", "Về mặc định");
  if (!ok) return;
  const st = await api().reset_bin_rule();
  P3.rulesSig = "";
  if (st && st.error) return status(st.error, "warn");
  setState(st); status("Bảng quy tắc đã về mặc định.", "ok");
};
