/* Bước 5: Thời lượng làm lại (ADR-0013; demo design/5_thoi_luong_moi). Mỗi giai đoạn MỘT hàng: gõ phút:giây, ổ khóa; số tự tính lại ngay,
   không còn nút cắt gọt. Chỉ vẽ và gọi Python (api().dur_*). "Đưa lên Timeline mới" chỉ tạo MỘT timeline mới sau hộp xác nhận. */
const D5 = { v: null, open: {}, seq: 0, timers: {}, hold: false, pending: false };
const d5mm = (s) => durTxt(s);
const d5LockSvg = (on) => on
  ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#F2B256" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>'
  : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/></svg>';
const d5ChevSvg = (open) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C4C4CC" stroke-width="2.4" aria-hidden="true"><path d="${open ? "M6 9l6 6 6-6" : "M9 6l6 6-6 6"}"/></svg>`;

/* "4:30" -> 270 giây; "1:02:03" ok; số trơn = giây (plain "sec") hoặc phút (plain "min"). Sai -> null */
function d5Parse(txt, plain) {
  const t = String(txt == null ? "" : txt).trim().replace(",", ".");
  if (!t) return null;
  if (t.includes(":")) {
    const p = t.split(":");
    if (p.length > 3 || p.some((x) => x === "" || !/^\d+(\.\d+)?$/.test(x))) return null;
    const n = p.map(Number);
    if (n.slice(1).some((x) => x >= 60)) return null;
    return p.length === 3 ? n[0] * 3600 + n[1] * 60 + n[2] : n[0] * 60 + n[1];
  }
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  return plain === "min" ? Number(t) * 60 : Number(t);
}
const d5Stable = (txt) => /^\d+:\d{2}$/.test(String(txt).trim());   // gõ dở ("4:3", "4") chưa tính lại, chỉ tính khi đã đủ phút:giây hoặc khi rời ô / Enter

async function renderPage5() {
  if (page !== 5) return;
  if (!S || !S.n) { D5.v = null; d5Paint(); return; }
  d5Run(() => api().dur_state());
}

/* chạy một lệnh sửa rồi vẽ lại; kết quả cũ đến muộn (gõ nhanh) bị bỏ */
async function d5Run(fn, okMsg) {
  const my = ++D5.seq;
  let v;
  try { v = await fn(); } catch (e) { return status("Lỗi: " + e, "warn"); }
  if (my !== D5.seq) return;
  if (v && v.error) { status(v.error, "warn"); v = await api().dur_state(); if (my !== D5.seq) return; }
  else if (okMsg) status(okMsg, "ok");
  D5.v = v; d5Paint();
}

function d5Short(v) { return v.delta_s < 0 ? -v.delta_s : 0; }

function d5Paint() {
  if (D5.hold) { D5.pending = true; return; }          // đang giữ chuột: vẽ lại bây giờ sẽ làm mất cú bấm (nút bị thay giữa lúc nhấn và thả)
  D5.pending = false;
  const v = D5.v;
  const ae = document.activeElement;
  const keep = ae && ae.dataset && ae.dataset.k ? { k: ae.dataset.k, val: ae.value, a: ae.selectionStart, b: ae.selectionEnd } : null;
  const tgtFocus = ae === $("durTarget");
  if (!v) {
    $("d5Res").innerHTML = ""; $("d5Seg").innerHTML = ""; $("d5Pv").innerHTML = ""; $("d5Warn").classList.add("hidden");
    $("d5Stages").innerHTML = '<div class="d5-card" style="padding:18px"><span class="dim13">Bấm "Đọc clip" ở bước 1 trước.</span></div>';
    $("d5RTitle").textContent = "Chưa có dữ liệu"; $("d5RTag").textContent = ""; $("d5Why").innerHTML = "";
    for (const id of ["d5SugA", "d5SugB", "d5SugC", "d5SugH"]) $(id).classList.add("hidden");
    $("d5Create").disabled = true; $("d5FootL").textContent = "Chưa có clip"; $("d5CreateHint").textContent = "";
    return;
  }
  const adv = v.advice, st = v.state;
  if (!tgtFocus) $("durTarget").value = d5mm(v.target_s);
  // thanh trên cùng: tổng + dải chia theo giai đoạn
  const short = d5Short(v);
  const tag = st === "ok" ? '<span class="d5-tag ok">đạt</span>' : st === "short" ? `<span class="d5-tag">thiếu ${d5mm(short)}</span>`
    : st === "over" ? `<span class="d5-tag">dư ${d5mm(v.delta_s)}</span>` : '<span class="d5-tag">chưa có clip sao</span>';
  $("d5Res").innerHTML = `<span>Đang giữ</span><b>${d5mm(v.total_s)}</b>${tag}`;
  $("d5Seg").innerHTML = v.stages.map((s, i) => {
    const ref = Math.max(s.budget_s, s.total_s, 1);
    const gap = s.short_kind === "no_clips" ? Math.max(0, s.budget_s - s.total_s) / ref * 100 : 0;
    return `<div class="d5-sg" style="flex:${Math.max(ref, 1)} 1 0" title="${esc(s.name)}"><div class="d5-sgb"><i style="width:${(s.total_s / ref * 100).toFixed(1)}%;background:${s.color || "#888"}"></i>${gap > 0 ? `<span class="gap" style="width:${gap.toFixed(1)}%"></span>` : ""}</div><div class="d5-sgc"><b>${String(i + 1).padStart(2, "0")}_${esc(s.name)}</b><span>${gap > 0 ? d5mm(s.total_s) + " / " + d5mm(s.budget_s) : d5mm(s.total_s)}</span></div></div>`;
  }).join("");
  // mỗi giai đoạn một hàng
  $("d5Stages").innerHTML = v.stages.map((s, i) => d5StageHtml(v, s, i)).join("");
  // xem trước timeline (chỉ hình)
  const color = {};
  v.stages.forEach((s, i) => s.bins.forEach((b) => { color[i + "|" + b.name] = b.color; }));
  const pv = v.stages.map((s, i) => {
    const its = v.items.filter((x) => x.stage === i);
    if (!its.length) return "";
    let last = null, alt = false;
    const blocks = its.map((x) => {
      alt = x.bin === last ? !alt : false; last = x.bin;
      return `<i title="${esc(x.bin)} · ${d5mm(x.dur)}" style="flex:${Math.max(x.dur, 0.5)} 1 0;background:${color[i + "|" + x.bin] || "#888"}${alt ? ";opacity:.8" : ""}"></i>`;
    }).join("");
    return `<div style="flex:${its.reduce((a, x) => a + x.dur, 0)} 1 0" title="${esc(s.name)}">${blocks}</div>`;
  }).join("");
  $("d5Pv").innerHTML = pv || '<i class="none">Chưa có clip nào được giữ</i>';
  $("d5PvT").textContent = "XEM TRƯỚC TIMELINE MỚI · " + d5mm(v.total_s);
  // cảnh báo còn lại (thiếu tổng đã có ở cột phải)
  const ws = v.warnings.filter((x) => x.kind !== "target_short" && x.kind !== "no_star");
  const w = $("d5Warn");
  if (ws.length) { w.innerHTML = ws.map((x) => `<span>⚠ ${esc(x.text)}</span>`).join(""); w.classList.remove("hidden"); } else w.classList.add("hidden");
  // cột phải
  $("d5RTitle").textContent = adv.title;
  $("d5RTag").className = "d5-tag" + (st === "ok" ? " ok" : ""); $("d5RTag").innerHTML = "";
  $("d5RTag").textContent = st === "ok" ? "đạt" : st === "short" ? "thiếu " + d5mm(short) : st === "over" ? "dư " + d5mm(v.delta_s) : "";
  $("d5RTag").classList.toggle("hidden", st === "no_star");
  const head = st === "short" ? `Vì sao chưa đủ ${d5mm(v.target_s)}?` : st === "over" ? "Vì sao đang dài hơn?" : st === "ok" ? "Đã đạt" : "Chưa có clip sao";
  const why = $("d5Why");
  why.className = "d5-box " + (st === "ok" ? "okc" : st === "no_star" ? "" : "warn");
  why.innerHTML = `<b>${esc(head)}</b>` + adv.reasons.map((t) => `<div>${esc(t)}</div>`).join("");
  const sug = (id, o) => { const b = $(id); b.classList.toggle("hidden", !o); if (o) { b.querySelector("b").textContent = o.title; b.querySelector("span").textContent = o.text; } };
  sug("d5SugA", adv.rebalance); sug("d5SugB", adv.lower); sug("d5SugC", adv.step3);
  $("d5SugH").classList.toggle("hidden", !(adv.rebalance || adv.lower || adv.step3));
  $("d5Reset").classList.toggle("hidden", !(v.edited.target || v.edited.stages || v.edited.bins));
  $("d5Create").disabled = !v.items.length;
  $("d5CreateHint").innerHTML = `Tạo một timeline MỚI tên “Rough Cut sao ${esc(v.project || "")} &lt;ngày giờ&gt;”, có hộp xác nhận. Không sửa timeline đang có. Không còn nút “Cắt gọt cho vừa”.`;
  const nst = v.stages.filter((s) => s.n_starred).length;
  $("d5FootL").textContent = `${v.n_starred} clip sao trong ${nst} giai đoạn · giữ ${d5mm(v.total_s)} / mục tiêu ${d5mm(v.target_s)}` + (st === "short" ? ` (thiếu ${d5mm(short)})` : "") + " · tự cắt gọt khi sửa";
  // trả lại ô đang gõ (không đổi chữ anh đang gõ, không mất con trỏ)
  if (keep) {
    const el = $("d5Stages").querySelector(`[data-k="${CSS.escape(keep.k)}"]`);
    if (el) { el.value = keep.val; el.focus(); try { el.setSelectionRange(keep.a, keep.b); } catch (e) { /* ô số */ } }
  }
}

function d5StageHtml(v, s, i) {
  const open = D5.open[s.name] === undefined ? i === 0 : D5.open[s.name];
  const ref = Math.max(s.natural_s, s.budget_s, s.total_s, 1);
  const solid = s.total_s / ref * 100, cutw = Math.max(0, s.natural_s - s.total_s) / ref * 100, gapw = s.short_kind === "no_clips" ? Math.max(0, s.budget_s - s.total_s) / ref * 100 : 0;
  let l2;
  if (!s.n_starred) l2 = '<span class="dim12">Chưa có clip sao ★ trong giai đoạn này</span>';
  else if (s.short_kind === "no_clips") l2 = `<span class="w">Thiếu ${d5mm(s.short_s)}</span> · giữ hết ${s.n_used} clip${s.dropped_n ? `, bỏ ${s.dropped_n}` : ", không bỏ clip nào"}`;
  else if (s.dropped_s >= 0.5) l2 = s.dropped_n ? `Phải bỏ <b>${d5mm(s.dropped_s)}</b> (${s.dropped_n} clip ít ưu tiên nhất)` : `Phải rút bớt <b>${d5mm(s.dropped_s)}</b> (rút ngắn clip)`;
  else l2 = `Giữ hết ${s.n_used} clip`;
  if (s.short_kind === "round") l2 += ` · lệch <b>${d5mm(s.short_s)}</b> so với số chia (chỉ bỏ nguyên clip)`;
  const head = `<div class="d5-phh">
    <button class="d5-chev" data-chev="${i}" aria-label="${open ? "Thu gọn" : "Mở"} ${esc(s.name)}" aria-expanded="${open}">${d5ChevSvg(open)}</button>
    <div class="d5-nm"><span><i class="d5-dot" style="background:${s.color || "#888"}"></i><span title="${esc(s.name)}">${String(i + 1).padStart(2, "0")}_${esc(s.name)}</span></span><span>${s.n_bins} bin con · ${s.n_starred} clip sao</span></div>
    <button class="d5-lk${s.locked ? " on" : ""}" data-lock="${i}" aria-label="${s.locked ? "Mở khóa" : "Khóa"} giai đoạn ${esc(s.name)}" aria-pressed="${s.locked}" title="${s.locked ? "Đang khóa: giai đoạn khác co giãn quanh số này. Bấm để mở khóa." : "Khóa số này lại: giai đoạn khác tự co giãn"}">${d5LockSvg(s.locked)}</button>
    <input class="d5-inp${s.pinned ? " pin" : ""}" data-k="stage:${i}" data-stage="${i}" type="text" inputmode="numeric" value="${d5mm(s.budget_s)}" autocomplete="off" aria-label="Thời lượng ${esc(s.name)}, phút:giây" title="Gõ phút:giây (ví dụ 4:30). Gõ rỗng để bỏ chốt.">
    <div class="d5-tr"><i style="width:${solid.toFixed(1)}%;background:${s.color || "#888"}"></i>${cutw > 0 ? `<span class="cut" style="left:${solid.toFixed(1)}%;width:${cutw.toFixed(1)}%"></span>` : ""}${gapw > 0 ? `<span class="gp" style="right:auto;left:${solid.toFixed(1)}%;width:${gapw.toFixed(1)}%"></span>` : ""}</div>
    <div class="d5-sx">Có <b>${d5mm(s.natural_s)}</b> clip sao · được chia <b>${d5mm(s.budget_s)}</b><br>${l2}</div>
  </div>`;
  let drop = "";
  if (s.dropped_n) {
    const chips = s.dropped_clips.slice(0, 6).map((c) => `<span class="d5-chip">${esc(c.name)} · ${d5mm(c.len)}</span>`).join("");
    drop = `<div class="d5-drop"><span>Sẽ bỏ ${s.dropped_n} clip ít ưu tiên nhất:</span>${chips}${s.dropped_n > 6 ? `<span class="d5-chip">+${s.dropped_n - 6} clip</span>` : ""}</div>`;
  }
  let sub = "";
  if (open) {
    const bins = s.bins.filter((b) => b.n_starred > 0 || b.edited);
    const rows = bins.map((b) => `<div class="d5-tb"><span class="d5-c1"><i class="d5-dot" style="background:${b.color}"></i><span title="${esc(b.name)}">${esc(b.name)}</span></span>
      <span class="d5-c2">${d5mm(b.natural_s)} · ${b.n_starred} clip</span><span class="d5-c3">${d5mm(b.total_s)}</span><span class="d5-c4">${d5mm(Math.max(0, b.natural_s - b.total_s))}</span>
      <span class="d5-c5"><input class="d5-inp sm${b.edited ? " pin" : ""}" data-k="min:${i}:${esc(b.name)}" data-bin="${esc(b.name)}" data-stage="${i}" data-w="min" type="text" value="${d5mm(b.min)}" autocomplete="off" aria-label="${esc(b.name)} tối thiểu"> – <input class="d5-inp sm${b.edited ? " pin" : ""}" data-k="max:${i}:${esc(b.name)}" data-bin="${esc(b.name)}" data-stage="${i}" data-w="max" type="text" value="${d5mm(b.max)}" autocomplete="off" aria-label="${esc(b.name)} tối đa"></span></div>`).join("");
    const note = "Min – Max mặc định không cần đụng. Là TỔNG của cả bin (khác độ dài từng clip ở Bước 3). " + (v.style === "traditional"
      ? "Truyền thống không rút ngắn clip, chỉ bỏ nguyên clip nên số Giữ có thể lệch vài giây so với số chia."
      : "Chưa chọn kiểu Truyền thống: clip có thể được rút ngắn theo bảng quy tắc Bước 3 cho vừa số chia.");
    sub = `<div class="d5-sub"><div class="d5-th"><span class="d5-c1">BIN CON</span><span class="d5-c2">CÓ</span><span class="d5-c3">GIỮ</span><span class="d5-c4">BỎ</span><span class="d5-c5">MIN – MAX (tổng bin)</span></div>${rows || '<div class="d5-note">Chưa có bin con nào có clip sao.</div>'}<div class="d5-note">${note}</div></div>`;
  }
  return `<div class="d5-card d5-ph${s.short_kind === "no_clips" ? " short" : ""}">${head}${drop}${sub}</div>`;
}

/* ---- gõ phút:giây ---- */
function d5Schedule(key, fn, delay) { clearTimeout(D5.timers[key]); D5.timers[key] = setTimeout(fn, delay); }
function d5Clear(key) { clearTimeout(D5.timers[key]); }

function d5CommitTarget(final) {
  const el = $("durTarget"), txt = el.value;
  if (!final && !d5Stable(txt)) return;
  const sec = d5Parse(txt, "min");
  if (sec === null) { if (final) { status("Gõ phút:giây cho mục tiêu, ví dụ 12:00.", "warn"); d5Paint(); } return; }
  if (!D5.v || Math.abs(sec - D5.v.target_s) < 0.5) { if (final) d5Paint(); return; }
  d5Run(() => api().dur_set_target(sec / 60));
}
$("durTarget").addEventListener("input", () => { if (page === 5) d5Schedule("target", () => d5CommitTarget(false), 600); });
$("durTarget").addEventListener("change", () => { d5Clear("target"); if (page === 5) d5CommitTarget(true); });
$("durTarget").addEventListener("keydown", (e) => { if (e.code === "Enter" || e.code === "NumpadEnter") e.target.blur(); });

function d5CommitStage(el, final) {
  const i = +el.dataset.stage, txt = el.value;
  if (!D5.v) return;
  if (txt.trim() === "") { if (final) d5Run(() => api().dur_set_stage(i, "")); return; }
  if (!final && !d5Stable(txt)) return;
  const sec = d5Parse(txt, "sec");
  if (sec === null) { if (final) { status("Gõ phút:giây, ví dụ 4:30.", "warn"); d5Paint(); } return; }
  const cur = D5.v.stages[i];
  if (cur.pinned && Math.abs(cur.budget_s - sec) < 0.5) { if (final) d5Paint(); return; }
  d5Run(() => api().dur_set_stage(i, sec));
}
function d5CommitBin(el, final) {
  const row = el.closest(".d5-tb"); if (!row || !D5.v) return;
  const mn = row.querySelector('[data-w="min"]'), mx = row.querySelector('[data-w="max"]');
  if (!final && !(d5Stable(mn.value) && d5Stable(mx.value))) return;
  const a = d5Parse(mn.value, "sec"), b = d5Parse(mx.value, "sec");
  if (a === null || b === null) { if (final) { status("Gõ phút:giây cho Min và Max, ví dụ 0:40.", "warn"); d5Paint(); } return; }
  d5Run(() => api().dur_set_bin(+el.dataset.stage, el.dataset.bin, a, b));
}
$("d5Stages").addEventListener("input", (e) => {
  const el = e.target; if (!el.dataset || !el.dataset.k) return;
  d5Schedule(el.dataset.k, () => (el.dataset.w ? d5CommitBin(el, false) : d5CommitStage(el, false)), 700);
});
$("d5Stages").addEventListener("change", (e) => {
  const el = e.target; if (!el.dataset || !el.dataset.k) return;
  d5Clear(el.dataset.k);
  if (el.dataset.w) d5CommitBin(el, true); else d5CommitStage(el, true);
});
$("d5Stages").addEventListener("keydown", (e) => { if ((e.code === "Enter" || e.code === "NumpadEnter") && e.target.dataset && e.target.dataset.k) e.target.blur(); });
$("d5Stages").addEventListener("click", (e) => {
  const lk = e.target.closest("[data-lock]");
  if (lk) return d5Run(() => api().dur_toggle_lock(+lk.dataset.lock));
  const ch = e.target.closest("[data-chev]");
  if (ch && D5.v) {
    const s = D5.v.stages[+ch.dataset.chev], cur = D5.open[s.name] === undefined ? +ch.dataset.chev === 0 : D5.open[s.name];
    D5.open[s.name] = !cur; d5Paint();
  }
});

/* ---- cột phải: ba gợi ý một chạm ---- */
$("d5SugA").addEventListener("click", () => d5Run(() => api().dur_rebalance(), "Đã chia lại cho đủ mục tiêu. Chưa tạo gì trong DaVinci."));
$("d5SugB").addEventListener("click", () => d5Run(() => api().dur_lower_target(), "Đã hạ mục tiêu xuống số đang giữ."));
$("d5SugC").addEventListener("click", () => {
  const a = D5.v && D5.v.advice.step3; if (!a) return;
  P3.onlyStar = false;                                           // cần thấy cả clip CHƯA sao để chọn thêm
  goPage(3);
  p3View(a.stage, a.bin === "(chưa xếp bin)" ? NONE : a.bin);
  status(`Bước 3: đang xem ${a.bin} của giai đoạn ${S.stages[a.stage] ? S.stages[a.stage].bin : ""}. Bấm J để gắn sao clip muốn dùng.`, "info");
});
$("d5Reset").addEventListener("click", (e) => { e.preventDefault(); d5Run(() => api().dur_reset(), "Đã đặt lại về số đề xuất."); });

/* ---- Đưa lên Timeline mới (luôn bấm được khi có clip; đang thiếu thì hộp xác nhận nói rõ số thiếu) ---- */
$("d5Create").addEventListener("click", async () => {
  const v = D5.v; if (!v || !v.items.length) return status("Chưa có clip sao ★ nào để đưa lên.", "warn");
  const short = d5Short(v);
  const warn = v.state === "short" ? `<br><br><b>Đang thiếu ${d5mm(short)}</b> so với mục tiêu ${d5mm(v.target_s)}: chưa đủ clip sao. Vẫn tạo được; Trợ lý không tự thêm clip.`
    : v.state === "over" ? `<br><br><b>Đang dài hơn mục tiêu ${d5mm(v.delta_s)}.</b>` : "";
  const ok = await ask("Tạo timeline mới?",
    `<div>Tên: <b>Rough Cut sao ${esc(v.project || "")} &lt;ngày giờ lúc bấm&gt;</b></div><div>Độ dài: <b>${d5mm(v.total_s)}</b> (mục tiêu ${d5mm(v.target_s)})</div>` +
    `<div>Số clip: <b>${v.n_used} / ${v.n_starred}</b> clip sao</div><div>Thứ tự: giai đoạn, rồi giờ quay thật</div>` + warn +
    `<br>Chỉ tạo <b>MỘT timeline MỚI</b>. Không sửa hay xóa timeline đang có, không ghi In/Out lên clip gốc. Trợ lý ghi nhật ký trước khi tạo và kiểm lại số timeline sau khi tạo.`,
    "Tạo timeline mới");
  if (!ok) return status("Đã hủy, chưa tạo gì trong DaVinci.", "info");
  const r = await api().dur_create_timeline();
  if (r.error) return status(r.error, "warn");
  status(`Đang tạo timeline “${r.name}”...`, "info");
});
const d5Release = () => { D5.hold = false; if (D5.pending) d5Paint(); };
$("page5").addEventListener("mousedown", () => { D5.hold = true; setTimeout(d5Release, 1500); });     // 1,5 giây là chốt an toàn nếu thả chuột ngoài cửa sổ
document.addEventListener("mouseup", () => setTimeout(d5Release, 0));
window.addEventListener("resize", () => { if (page === 5) d5Paint(); });
