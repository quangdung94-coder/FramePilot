/* Bước 5: Thời lượng, bản THANH KÉO (ADR-0013; demo design/5_thoi_luong_keo). Mỗi giai đoạn MỘT hàng: thanh có độ dài cố định, đầu phải = toàn bộ
   clip sao của giai đoạn (Có), phần màu = số giây LẤY, kết thúc ở chấm tròn kéo được (pointer events: chuột + cảm ứng) hoặc gõ phút:giây.
   Không kéo/gõ vượt Có. Số tự tính lại ngay (không còn nút cắt gọt). Chỉ vẽ và gọi Python (api().dur_*); "Đưa lên Timeline mới" chỉ tạo
   MỘT timeline mới sau hộp xác nhận. */
const D5 = { v: null, open: {}, adv: {}, seq: 0, timers: {}, hold: false, pending: false, drag: null };
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

/* chạy một lệnh sửa rồi vẽ lại; kết quả cũ đến muộn (gõ/kéo nhanh) bị bỏ */
async function d5Run(fn, okMsg) {
  const my = ++D5.seq;
  let v;
  try { v = await fn(); } catch (e) { return status("Lỗi: " + e, "warn"); }
  if (my !== D5.seq) return;
  if (v && v.error) { status(v.error, "warn"); v = await api().dur_state(); if (my !== D5.seq) return; }
  else if (okMsg) status(okMsg, "ok");
  D5.v = v; d5Paint();
}

/* Giá trị đang hiện của một giai đoạn / bin: nếu đang kéo đúng thanh đó thì theo chuột, không thì theo Python */
const d5StageKey = (i) => "s:" + i;
const d5BinKey = (i, b) => "b:" + i + ":" + b;
function d5Take(key, dflt) { return D5.drag && D5.drag.key === key ? D5.drag.v : dflt; }

function d5Track(key, have, avail, take, color, dis) {
  const f = have > 0 ? Math.max(0, Math.min(1, take / have)) * 100 : 0;
  return `<div class="d5-tr" data-track="${esc(key)}"><i style="width:${f.toFixed(2)}%;background:${color}"></i>` +
    `<b class="d5-knob" role="slider" tabindex="${dis ? -1 : 0}" data-knob="${esc(key)}" data-have="${have}" data-avail="${avail}" aria-valuemin="0" aria-valuemax="${Math.round(avail)}" aria-valuenow="${Math.round(take)}" aria-valuetext="${d5mm(take)}" aria-label="Kéo để chọn số giây lấy" style="left:${f.toFixed(2)}%;border-color:${color}${dis ? ";opacity:.4;cursor:default" : ""}"></b></div>`;
}

function d5Paint() {
  if (D5.hold) { D5.pending = true; return; }          // đang giữ chuột: vẽ lại bây giờ sẽ làm mất cú bấm (nút bị thay giữa lúc nhấn và thả)
  D5.pending = false;
  const v = D5.v;
  const ae = document.activeElement;
  const keep = ae && ae.dataset && (ae.dataset.k || ae.dataset.knob) ? { k: ae.dataset.k, knob: ae.dataset.knob, val: ae.value, a: ae.selectionStart, b: ae.selectionEnd } : null;
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
  // thanh trên cùng: tổng "Hiện Tại" + dải các giai đoạn theo số giây lấy + đoạn nét đứt "thiếu" nếu đã kéo hết cỡ mà chưa đạt
  const short = v.short_s || 0;
  const tag = st === "ok" ? '<span class="d5-tag ok">đạt</span>' : st === "short" ? `<span class="d5-tag">thiếu ${d5mm(short)}</span>`
    : st === "over" ? `<span class="d5-tag">dư ${d5mm(v.delta_s)}</span>` : '<span class="d5-tag">chưa có clip sao</span>';
  $("d5Res").innerHTML = `<span>Hiện Tại</span><b>${d5mm(v.total_s)}</b>${tag}`;
  $("d5Seg").innerHTML = v.stages.map((s, i) => {
    const take = d5Take(d5StageKey(i), s.pinned ? s.budget_s : s.total_s);
    return `<div class="d5-sg" style="flex:${Math.max(take, 1)} 1 0" title="${esc(s.name)}"><div class="d5-sgb"><i style="width:100%;background:${s.color || "#888"}"></i></div><div class="d5-sgc"><b>${String(i + 1).padStart(2, "0")}_${esc(s.name)}</b><span>${d5mm(take)}${s.maxed && st === "short" ? " (hết sao)" : ""}</span></div></div>`;
  }).join("") + (st === "short" && short > 0 ? `<div class="d5-sg" style="flex:${Math.max(short, 1)} 1 0" title="Thiếu ${d5mm(short)} so với mục tiêu"><div class="d5-sgb"><span class="gap" style="width:100%"></span></div><div class="d5-sgc"><b style="color:#F2B256">thiếu</b><span>${d5mm(short)}</span></div></div>` : "");
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
  const ws = v.warnings.filter((x) => x.kind !== "target_short" && x.kind !== "no_star");
  const w = $("d5Warn");
  if (ws.length) { w.innerHTML = ws.map((x) => `<span>⚠ ${esc(x.text)}</span>`).join(""); w.classList.remove("hidden"); } else w.classList.add("hidden");
  // cột phải
  $("d5RTitle").textContent = adv.title;
  $("d5RTag").className = "d5-tag" + (st === "ok" ? " ok" : "");
  $("d5RTag").textContent = st === "ok" ? "đạt" : st === "short" ? "thiếu " + d5mm(short) : st === "over" ? "dư " + d5mm(v.delta_s) : "";
  $("d5RTag").classList.toggle("hidden", st === "no_star");
  const head = st === "short" ? `Vì sao chưa đủ ${d5mm(v.target_s)}?` : st === "over" ? "Vì sao đang dài hơn?" : st === "ok" ? "Đã đạt" : "Chưa có clip sao";
  const why = $("d5Why");
  why.className = "d5-box " + (st === "ok" ? "okc" : st === "no_star" ? "" : "warn");
  why.innerHTML = `<b>${esc(head)}</b>` + adv.reasons.map((t) => `<div>${esc(t)}</div>`).join("");
  const sug = (id, o) => { const b = $(id); b.classList.toggle("hidden", !o); if (o) { b.querySelector("b").textContent = o.title; b.querySelector("span").textContent = o.text; } };
  sug("d5SugA", adv.rebalance); sug("d5SugB", adv.lower); sug("d5SugC", adv.step3);
  $("d5SugH").classList.toggle("hidden", !(adv.rebalance || adv.lower || adv.step3));
  $("d5Reset").classList.toggle("hidden", !(v.edited.target || v.edited.stages || v.edited.bins || v.edited.bin_s));
  $("d5Create").disabled = !v.items.length;
  $("d5CreateHint").innerHTML = `Tạo một timeline MỚI tên “Rough Cut sao ${esc(v.project || "")} &lt;ngày giờ&gt;”, có hộp xác nhận. Không sửa timeline đang có. Không còn nút “Cắt gọt cho vừa”.`;
  const nst = v.stages.filter((s) => s.n_starred).length;
  $("d5FootL").textContent = `${v.n_starred} clip sao trong ${nst} giai đoạn · giữ ${d5mm(v.total_s)} / mục tiêu ${d5mm(v.target_s)}` + (st === "short" ? ` (thiếu ${d5mm(short)})` : "") + " · tự cắt gọt khi sửa";
  // trả lại ô/chấm đang dùng (không đổi chữ anh đang gõ, không mất con trỏ)
  if (keep) {
    const sel = keep.k ? `[data-k="${CSS.escape(keep.k)}"]` : `[data-knob="${CSS.escape(keep.knob)}"]`;
    const el = $("d5Stages").querySelector(sel);
    if (el) { if (keep.k) el.value = keep.val; el.focus(); try { if (keep.k) el.setSelectionRange(keep.a, keep.b); } catch (e) { /* ô số */ } }
  }
}

function d5StageHtml(v, s, i) {
  const open = D5.open[s.name] === undefined ? i === 0 : D5.open[s.name];
  const dragging = D5.drag && D5.drag.key === d5StageKey(i);
  const take = d5Take(d5StageKey(i), s.pinned ? s.budget_s : s.total_s);
  const dropped = Math.max(0, s.natural_s - take);
  let l2;
  if (!s.n_starred) l2 = '<span class="dim12">Chưa có clip sao ★ trong giai đoạn này</span>';
  else if (dropped >= 0.5 && !dragging) l2 = s.dropped_n ? `Bỏ <b>${d5mm(dropped)}</b> (${s.dropped_n} clip ít ưu tiên nhất)` : `Bỏ <b>${d5mm(dropped)}</b> (rút ngắn clip)`;
  else if (dropped >= 0.5) l2 = `Bỏ <b>${d5mm(dropped)}</b>`;
  else if (v.state === "short") l2 = '<span class="w">Kéo hết cỡ rồi</span> · muốn dài hơn phải gắn thêm sao';
  else l2 = "Lấy hết clip sao";
  const head = `<div class="d5-phh">
    <button class="d5-chev" data-chev="${i}" aria-label="${open ? "Thu gọn" : "Mở"} ${esc(s.name)}" aria-expanded="${open}">${d5ChevSvg(open)}</button>
    <div class="d5-nm"><span><i class="d5-dot" style="background:${s.color || "#888"}"></i><span title="${esc(s.name)}">${String(i + 1).padStart(2, "0")}_${esc(s.name)}</span></span><span>${s.n_bins} bin con · ${s.n_starred} clip sao</span></div>
    <button class="d5-lk${s.locked ? " on" : ""}" data-lock="${i}" aria-label="${s.locked ? "Mở khóa" : "Khóa"} giai đoạn ${esc(s.name)}" aria-pressed="${s.locked}" title="${s.locked ? "Đang khóa: giai đoạn khác co giãn quanh số này. Bấm để mở khóa." : "Khóa số này lại: giai đoạn khác tự co giãn"}">${d5LockSvg(s.locked)}</button>
    <input class="d5-inp${s.pinned ? " pin" : ""}" data-k="stage:${i}" data-stage="${i}" type="text" inputmode="numeric" value="${d5mm(take)}" autocomplete="off" aria-label="Thời lượng lấy của ${esc(s.name)}, phút:giây" title="Kéo chấm trên thanh hoặc gõ phút:giây (ví dụ 4:30). Không vượt thanh đầy. Gõ rỗng để bỏ chốt.">
    ${d5Track(d5StageKey(i), s.natural_s, s.avail_s, take, s.color || "#888", !s.n_starred)}
    <div class="d5-sx">Thanh đầy = <b>${d5mm(s.natural_s)}</b> clip sao · lấy <b>${d5mm(take)}</b><br>${l2}</div>
  </div>`;
  let drop = "";
  if (s.dropped_n && !dragging) {
    const chips = s.dropped_clips.slice(0, 6).map((c) => `<span class="d5-chip">${esc(c.name)} · ${d5mm(c.len)}</span>`).join("");
    drop = `<div class="d5-drop"><span>Sẽ bỏ ${s.dropped_n} clip ít ưu tiên nhất:</span>${chips}${s.dropped_n > 6 ? `<span class="d5-chip">+${s.dropped_n - 6} clip</span>` : ""}</div>`;
  }
  let sub = "";
  if (open) {
    const bins = s.bins.filter((b) => b.n_starred > 0 || b.edited);
    const rows = bins.map((b) => {
      const key = d5BinKey(i, b.name), bt = d5Take(key, b.pin != null ? b.pin : b.total_s);
      return `<div class="d5-tb"><span class="d5-c1"><i class="d5-dot" style="background:${b.color}"></i><span title="${esc(b.name)}">${esc(b.name)}</span></span>
      <span class="d5-c2">${d5mm(b.natural_s)} · ${b.n_starred} clip</span>
      <span class="d5-c5">${d5Track(key, b.natural_s, b.avail_s, bt, b.color, !b.n_starred)}</span>
      <span class="d5-c3"><input class="d5-inp sm${b.pin != null ? " pin" : ""}" data-k="take:${i}:${esc(b.name)}" data-bin="${esc(b.name)}" data-stage="${i}" data-w="take" type="text" value="${d5mm(bt)}" autocomplete="off" aria-label="${esc(b.name)} lấy"></span>
      <span class="d5-c4">${d5mm(Math.max(0, b.natural_s - bt))}</span></div>`;
    }).join("");
    const adv = D5.adv[s.name];
    const advRows = adv ? bins.map((b) => `<div class="d5-tb"><span class="d5-c1"><i class="d5-dot" style="background:${b.color}"></i><span>${esc(b.name)}</span></span>
      <span class="d5-c5"><input class="d5-inp sm${b.edited ? " pin" : ""}" data-k="min:${i}:${esc(b.name)}" data-bin="${esc(b.name)}" data-stage="${i}" data-w="min" type="text" value="${d5mm(b.edited ? b.min : 0)}" autocomplete="off" aria-label="${esc(b.name)} tối thiểu"> – <input class="d5-inp sm${b.edited ? " pin" : ""}" data-k="max:${i}:${esc(b.name)}" data-bin="${esc(b.name)}" data-stage="${i}" data-w="max" type="text" value="${d5mm(b.edited ? b.max : b.natural_s)}" autocomplete="off" aria-label="${esc(b.name)} tối đa"></span></div>`).join("") : "";
    const note = "Mặc định bin lấy theo tỉ lệ, không bị giới hạn Max. Ai muốn đặt Min – Max thì mở “Giới hạn nâng cao”. " + (v.style === "traditional"
      ? "Truyền thống chỉ bỏ nguyên clip nên số Lấy có thể lệch vài giây."
      : "Chưa chọn Truyền thống: clip có thể được rút ngắn theo bảng quy tắc Bước 3.");
    sub = `<div class="d5-sub"><div class="d5-th"><span class="d5-c1">BIN CON</span><span class="d5-c2">CÓ (thanh đầy)</span><span class="d5-c5">KÉO CHẤM ĐỂ CHỌN</span><span class="d5-c3">LẤY</span><span class="d5-c4">BỎ</span></div>${rows || '<div class="d5-note">Chưa có bin con nào có clip sao.</div>'}
      <div class="d5-note">${note}</div>
      <button class="d5-advb" data-adv="${i}" aria-expanded="${!!adv}">${adv ? "▾" : "▸"} Giới hạn nâng cao (Min – Max tổng bin, chỉ có tác dụng khi anh tự đặt)</button>
      ${adv ? `<div class="d5-adv"><div class="d5-th"><span class="d5-c1">BIN CON</span><span class="d5-c5">MIN – MAX (giây tổng bin)</span></div>${advRows}</div>` : ""}</div>`;
  }
  return `<div class="d5-card d5-ph${s.maxed && v.state === "short" ? " short" : ""}">${head}${drop}${sub}</div>`;
}

/* ---- kéo chấm (pointer events: chuột + cảm ứng; lắng nghe trên window nên vẫn chạy khi thanh bị vẽ lại giữa chừng) ---- */
function d5SendDrag() {
  const dg = D5.drag; if (!dg) return Promise.resolve();
  const k = dg.key.split(":");
  const fn = k[0] === "s" ? () => api().dur_set_stage(+k[1], dg.v) : () => api().dur_set_bin_take(+k[1], k.slice(2).join(":"), dg.v);
  return d5Run(fn);
}
$("d5Stages").addEventListener("pointerdown", (e) => {
  const kn = e.target.closest(".d5-knob"); if (!kn || kn.getAttribute("tabindex") === "-1") return;
  e.preventDefault();
  const tr = kn.parentElement, r = tr.getBoundingClientRect();
  const have = +kn.dataset.have, avail = +kn.dataset.avail;
  D5.drag = { key: kn.dataset.knob, have, avail, v: Math.round(+kn.getAttribute("aria-valuenow")), lastX: e.clientX, pid: e.pointerId, tr, timer: null };
  D5.hold = true;
  window.addEventListener("pointermove", d5Move);
  window.addEventListener("pointerup", d5Up);
  window.addEventListener("pointercancel", d5Up);
});
function d5Move(e) {
  const dg = D5.drag; if (!dg || e.pointerId !== dg.pid) return;
  const el = document.querySelector(`[data-track="${CSS.escape(dg.key)}"]`) || dg.tr;
  const r = el.getBoundingClientRect(); dg.tr = el;
  let v;
  if (e.shiftKey) v = dg.v + (e.clientX - dg.lastX) / r.width * dg.have * 0.2;      // giữ Shift: tinh chỉnh (chậm 5 lần, bước 0,1 giây)
  else v = (e.clientX - r.left) / r.width * dg.have;
  dg.lastX = e.clientX;
  v = Math.max(0, Math.min(dg.avail, v));                                          // chặn ở cuối thanh (không vượt Có)
  dg.v = e.shiftKey ? Math.round(v * 10) / 10 : Math.round(v);                     // bám mốc 1 giây
  // cập nhật tại chỗ cho mượt (chấm, phần màu, ô số), rồi gửi Python (giãn cách ~90 ms) để các số khác tính lại
  const f = dg.have > 0 ? dg.v / dg.have * 100 : 0;
  const fill = el.querySelector("i"), kn = el.querySelector(".d5-knob");
  if (fill) fill.style.width = f + "%";
  if (kn) { kn.style.left = f + "%"; kn.setAttribute("aria-valuenow", Math.round(dg.v)); kn.setAttribute("aria-valuetext", d5mm(dg.v)); }
  const k = dg.key.split(":");
  const inp = $("d5Stages").querySelector(k[0] === "s" ? `[data-k="stage:${k[1]}"]` : `[data-k="take:${k[1]}:${CSS.escape(k.slice(2).join(":"))}"]`);
  if (inp) inp.value = d5mm(dg.v);
  if (!dg.timer) dg.timer = setTimeout(() => { dg.timer = null; if (D5.drag === dg) { D5.hold = false; d5SendDrag().then(() => { if (D5.drag === dg) D5.hold = true; }); } }, 90);
}
async function d5Up(e) {
  const dg = D5.drag; if (!dg || (e && e.pointerId !== dg.pid)) return;
  window.removeEventListener("pointermove", d5Move); window.removeEventListener("pointerup", d5Up); window.removeEventListener("pointercancel", d5Up);
  clearTimeout(dg.timer);
  D5.hold = false;
  await d5SendDrag();
  D5.drag = null; d5Paint();
}
/* bàn phím trên chấm: ← → ±1 giây, Shift ±10 giây (đọc event.code); Enter trong ô số thì chốt */
$("d5Stages").addEventListener("keydown", (e) => {
  const kn = e.target.closest && e.target.closest(".d5-knob");
  if (kn && (e.code === "ArrowLeft" || e.code === "ArrowRight")) {
    e.preventDefault();
    const cur = +kn.getAttribute("aria-valuenow"), d = (e.code === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 10 : 1);
    const v = Math.max(0, Math.min(+kn.dataset.avail, cur + d)), k = kn.dataset.knob.split(":");
    d5Run(k[0] === "s" ? () => api().dur_set_stage(+k[1], v) : () => api().dur_set_bin_take(+k[1], k.slice(2).join(":"), v));
    return;
  }
  if ((e.code === "Enter" || e.code === "NumpadEnter") && e.target.dataset && e.target.dataset.k) e.target.blur();
});

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
  if (Math.abs((cur.pinned ? cur.budget_s : cur.total_s) - sec) < 0.5) { if (final) d5Paint(); return; }
  d5Run(() => api().dur_set_stage(i, sec));
}
function d5CommitTake(el, final) {                      // số giây LẤY của một bin con
  if (!D5.v) return;
  const txt = el.value;
  if (txt.trim() === "") { if (final) d5Run(() => api().dur_set_bin_take(+el.dataset.stage, el.dataset.bin, "")); return; }
  if (!final && !d5Stable(txt)) return;
  const sec = d5Parse(txt, "sec");
  if (sec === null) { if (final) { status("Gõ phút:giây, ví dụ 0:50.", "warn"); d5Paint(); } return; }
  d5Run(() => api().dur_set_bin_take(+el.dataset.stage, el.dataset.bin, sec));
}
function d5CommitBin(el, final) {                       // Giới hạn nâng cao: Min – Max tổng bin
  const row = el.closest(".d5-tb"); if (!row || !D5.v) return;
  const mn = row.querySelector('[data-w="min"]'), mx = row.querySelector('[data-w="max"]');
  if (!final && !(d5Stable(mn.value) && d5Stable(mx.value))) return;
  const a = d5Parse(mn.value, "sec"), b = d5Parse(mx.value, "sec");
  if (a === null || b === null) { if (final) { status("Gõ phút:giây cho Min và Max, ví dụ 0:40.", "warn"); d5Paint(); } return; }
  d5Run(() => api().dur_set_bin(+el.dataset.stage, el.dataset.bin, a, b));
}
const d5Commit = (el, final) => (el.dataset.w === "take" ? d5CommitTake(el, final) : el.dataset.w ? d5CommitBin(el, final) : d5CommitStage(el, final));
$("d5Stages").addEventListener("input", (e) => {
  const el = e.target; if (!el.dataset || !el.dataset.k) return;
  d5Schedule(el.dataset.k, () => d5Commit(el, false), 700);
});
$("d5Stages").addEventListener("change", (e) => {
  const el = e.target; if (!el.dataset || !el.dataset.k) return;
  d5Clear(el.dataset.k);
  d5Commit(el, true);
});
$("d5Stages").addEventListener("click", (e) => {
  const lk = e.target.closest("[data-lock]");
  if (lk) return d5Run(() => api().dur_toggle_lock(+lk.dataset.lock));
  const ch = e.target.closest("[data-chev]");
  if (ch && D5.v) {
    const s = D5.v.stages[+ch.dataset.chev], cur = D5.open[s.name] === undefined ? +ch.dataset.chev === 0 : D5.open[s.name];
    D5.open[s.name] = !cur; d5Paint(); return;
  }
  const ad = e.target.closest("[data-adv]");
  if (ad && D5.v) { const s = D5.v.stages[+ad.dataset.adv]; D5.adv[s.name] = !D5.adv[s.name]; d5Paint(); }
});

/* ---- cột phải: ba gợi ý một chạm ---- */
$("d5SugA").addEventListener("click", () => d5Run(() => api().dur_rebalance(), "Đã tự kéo thêm cho đủ mục tiêu. Chưa tạo gì trong DaVinci."));
$("d5SugB").addEventListener("click", () => d5Run(() => api().dur_lower_target(), "Đã hạ mục tiêu xuống số Hiện Tại."));
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
  const short = v.short_s || 0;
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
const d5Release = () => { D5.hold = !!D5.drag; if (!D5.hold && D5.pending) d5Paint(); };
$("page5").addEventListener("mousedown", () => { D5.hold = true; setTimeout(d5Release, 1500); });     // 1,5 giây là chốt an toàn nếu thả chuột ngoài cửa sổ
document.addEventListener("mouseup", () => setTimeout(d5Release, 0));
window.addEventListener("resize", () => { if (page === 5) d5Paint(); });
