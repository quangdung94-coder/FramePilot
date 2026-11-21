/* Bước 5 bản 3: TIMELINE KÉO THẢ (ADR-0013; demo design/5_timeline_keo_tha/project/Timeline.dc.html).
   Thước thời gian ngang 0:00 -> mục tiêu, hàng V2 (chồng), V1 (cụm mẹ có tiêu đề + khối con bên trong, chiều dài tỉ lệ RA TIMELINE), A1/A2 vẽ tiếng
   từng khối (vạch chéo = tắt). Kéo (pointer events: chuột + cảm ứng): thân khối mẹ = dời cả cụm; thân khối con = đổi thứ tự / sang cụm khác / lên V2;
   mép phải = đổi thời lượng (không vượt Có). Bảng thứ tự của cụm đang chọn đồng bộ hai chiều. Chỉ vẽ và gọi Python (api().dur_*, dur_tl_*);
   "Đưa lên Timeline mới" chỉ tạo MỘT timeline mới sau hộp xác nhận. */
const D5 = { v: null, sel: null, seq: 0, timers: {}, drag: null, menu: null, T: 60 };
const d5mm = (s) => durTxt(s);
const d5Pct = (p) => (p == null ? "" : String(Math.round(p * 10) / 10).replace(".", ",") + "%");
const SVG_GRIP = '<svg width="12" height="12" viewBox="0 0 24 24" fill="#C4C4CC" aria-hidden="true"><circle cx="8" cy="6" r="2"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/><circle cx="16" cy="18" r="2"/></svg>';
const SVG_SPK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/></svg>';
const SVG_SPK_OFF = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>';
const SVG_LOCK = (on) => on
  ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F2B256" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>'
  : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/></svg>';

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
const d5Stable = (txt) => /^\d+:\d{2}$/.test(String(txt).trim());   // gõ dở ("4:3") chưa tính lại, chỉ tính khi đủ phút:giây hoặc khi rời ô / Enter

async function renderPage5() {
  if (page !== 5) return;
  if (!S || !S.n) { D5.v = null; d5Paint(); return; }
  d5Run(() => api().dur_state());
}

/* chạy một lệnh sửa rồi vẽ lại; kết quả cũ đến muộn bị bỏ */
async function d5Run(fn, okMsg) {
  const my = ++D5.seq;
  let v;
  try { v = await fn(); } catch (e) { status("Lỗi: " + e, "warn"); return null; }
  if (my !== D5.seq) return null;
  if (v && v.error) { status(v.error, "warn"); v = await api().dur_state(); if (my !== D5.seq) return null; }
  else if (okMsg) status(okMsg, "ok");
  D5.v = v; d5Paint();
  return v;
}

/* ------------------------------------------------------------------ vẽ */
function d5Ticks(T) {
  const steps = [5, 10, 15, 30, 60, 120, 180, 300, 600, 900, 1800];
  const st = steps.find((s) => T / s <= 14) || 1800;
  const out = [];
  for (let t = 0; t <= T + 0.01; t += st) out.push(t);
  return out;
}
const pc = (s) => (s / D5.T * 100).toFixed(3);

function d5Frames(v) {
  const L = v.tl, T = D5.T;
  let h = "";
  for (const c of L.clusters) {
    if (!c.v1.length) continue;
    const sel = c.stage === D5.sel;
    const v2 = c.v2.reduce((a, k) => a + L.blocks[k].dur, 0);
    const kids = c.v1.map((k) => {
      const b = L.blocks[k];
      const sp = b.speed.mode === "100" ? "" : ` · ${b.speed.mode === "mixed" ? "nhiều mức" : d5Pct(b.speed.pct)}`;
      return `<div class="tl-cb${b.key === D5.hl ? " hl" : ""}" data-blk="${esc(k)}" style="left:${((b.start - c.start) / c.dur * 100).toFixed(3)}%;width:${(b.dur / c.dur * 100).toFixed(3)}%;background:${b.color}" title="${esc(b.bin)} · ${d5mm(b.dur)}${sp}"><b>${esc(b.bin)}</b><span>${d5mm(b.dur)}${sp}</span><i class="tl-re" data-resize="b:${esc(k)}" title="Kéo mép phải để đổi thời lượng"></i></div>`;
    }).join("");
    const stI = v.stages[c.i];
    h += `<div class="tl-fr${sel ? " cur" : ""}" data-cl="${esc(c.stage)}" style="left:${pc(c.start)}%;width:${pc(c.dur)}%;border-color:${c.color || "#888"}">
      <div class="tl-fh" data-grab="${esc(c.stage)}">${SVG_GRIP}<span class="tl-nm">${String(c.i + 1).padStart(2, "0")}_${esc(c.stage)}</span><span class="tl-sub">${d5mm(c.dur)}${v2 > 0 ? ` + ${d5mm(v2)} V2` : ""}</span>${stI && stI.locked ? '<span class="tl-lk">🔒</span>' : ""}
        <span class="tl-ctl"><span class="tl-cs${c.mute === "mixed" ? " mx" : (c.mute ? " off" : "")}" data-mute="cl:${esc(c.stage)}" role="button" tabindex="0" aria-label="Tiếng của cụm ${esc(c.stage)}" title="Bật/tắt tiếng cả cụm (khối con đặt riêng thì thắng)">${c.mute === true ? SVG_SPK_OFF : SVG_SPK}</span><span class="tl-cp${c.speed.mode === "mixed" ? " mx" : (c.speed.mode !== "100" ? " sl" : "")}" data-speed="cl:${esc(c.stage)}" role="button" tabindex="0" aria-label="Tốc độ của cụm ${esc(c.stage)}" title="Tốc độ cả cụm (khối con đặt riêng thì thắng)">${c.speed.mode === "mixed" ? "nhiều mức" : (c.speed.mode === "100" ? "100%" : d5Pct(c.speed.pct))}</span></span></div>
      <div class="tl-fb">${kids}</div><i class="tl-re" data-resize="s:${c.i}" title="Kéo mép phải để đổi thời lượng cả cụm"></i></div>`;
  }
  return h;
}

function d5Paint() {
  if (D5.drag && D5.drag.moved) { D5.pending = true; return; }
  D5.pending = false;
  const v = D5.v;
  const ae = document.activeElement;
  const keep = ae && ae.dataset && ae.dataset.k ? { k: ae.dataset.k, val: ae.value, a: ae.selectionStart, b: ae.selectionEnd } : null;
  const tgtFocus = ae === $("durTarget");
  if (!v) {
    $("d5Res").innerHTML = ""; for (const id of ["d5Ruler", "d5V2", "d5A1", "d5A2"]) $(id).innerHTML = "";
    $("d5V1").innerHTML = '<div class="dim13" style="padding:14px">Bấm "Đọc clip" ở bước 1 trước.</div>'; $("d5Order").innerHTML = ""; $("d5Warn").classList.add("hidden");
    $("d5RTitle").textContent = "Chưa có dữ liệu"; $("d5RTag").textContent = ""; $("d5Why").innerHTML = "";
    for (const id of ["d5SugA", "d5SugB", "d5SugC", "d5SugD", "d5SugE", "d5SugH"]) $(id).classList.add("hidden");
    $("d5Create").disabled = true; $("d5FootL").textContent = "Chưa có clip"; $("d5CreateHint").textContent = "";
    return;
  }
  const L = v.tl, st = v.state, adv = v.advice;
  const clusters = L.clusters;
  if (!D5.sel || !clusters.some((c) => c.stage === D5.sel)) D5.sel = (clusters.find((c) => c.kids.length) || clusters[0] || {}).stage || null;
  D5.T = Math.max(v.target_s, L.v1_end, L.v2_end, 30) * 1.0;
  if (!tgtFocus) $("durTarget").value = d5mm(v.target_s);
  const short = v.short_s || 0, over = st === "over" ? v.delta_s : 0;
  const tag = st === "ok" ? '<span class="tl-tag ok">đạt</span>' : st === "short" ? `<span class="tl-tag">thiếu ${d5mm(short)}</span>`
    : st === "over" ? `<span class="tl-tag">dư ${d5mm(over)}</span>` : '<span class="tl-tag">chưa có clip sao</span>';
  $("d5Res").innerHTML = `<span>Hiện Tại</span><b>${d5mm(v.total_s)}</b>${tag}`;
  $("d5Reset").classList.toggle("on", !!v.tl_manual);
  // thước + vạch lưới
  const T = D5.T, ticks = d5Ticks(T);
  const grid = ticks.slice(1).map((t) => `<i class="tl-gl" style="left:${pc(t)}%"></i>`).join("");
  const goalX = pc(v.target_s);
  $("d5Ruler").innerHTML = ticks.map((t) => `<span class="tl-tk" style="left:${pc(t)}%;transform:${t === 0 ? "none" : "translateX(-50%)"}">${d5mm(t)}</span>`).join("");
  const goal = `<i class="tl-goal" style="left:${goalX}%"><em>${over ? "mục tiêu " : "mục tiêu "}${d5mm(v.target_s)}</em></i>`;
  // V2
  const v2 = Object.values(L.blocks).filter((b) => b.track === "V2").map((b) => {
    const sp = b.speed.mode === "100" ? "" : ` ${b.speed.mode === "mixed" ? "nhiều mức" : d5Pct(b.speed.pct)}`;
    return `<div class="tl-cb v2${b.key === D5.hl ? " hl" : ""}" data-blk="${esc(b.key)}" style="left:${pc(b.start)}%;width:${pc(b.dur)}%;background:${b.color}" title="${esc(b.bin)} chồng trên V2"><b>${esc(b.bin)}${esc(sp)}</b><span>${d5mm(b.dur)} · chồng</span><i class="tl-re" data-resize="b:${esc(b.key)}"></i></div>`;
  }).join("");
  $("d5V2").innerHTML = grid + v2 + (L.v2_end > v.target_s ? "" : "") + goal;
  // V1 + đoạn thiếu
  const gap = st === "short" && short > 0 ? `<div class="tl-gap" style="left:${pc(L.v1_end)}%;width:${pc(short)}%">thiếu ${d5mm(short)}</div>` : "";
  $("d5V1").innerHTML = grid + d5Frames(v) + gap + goal;
  // A1, A2
  const ab = (b) => `<div class="tl-ab${b.mute ? " mute" : ""}" style="left:${pc(b.start)}%;width:${pc(b.dur)}%">${b.mute ? "tắt" : ""}</div>`;
  const bl = Object.values(L.blocks);
  const a1m = bl.filter((b) => b.track === "V1"), a2m = bl.filter((b) => b.track === "V2");
  $("d5A1").innerHTML = grid + a1m.map(ab).join("");
  $("d5A2").innerHTML = grid + a2m.map(ab).join("");
  $("d5A1Lab").className = "tl-lab a" + (a1m.length && a1m.every((b) => b.mute) ? " off" : "");
  $("d5A2Lab").className = "tl-lab a" + (a2m.length && a2m.every((b) => b.mute) ? " off" : "");
  d5PaintOrder(v);
  // cột phải
  $("d5RTitle").textContent = adv.title;
  $("d5RTag").className = "tl-tag" + (st === "ok" ? " ok" : "");
  $("d5RTag").textContent = st === "ok" ? "đạt" : st === "short" ? "thiếu " + d5mm(short) : st === "over" ? "dư " + d5mm(over) : "";
  $("d5RTag").classList.toggle("hidden", st === "no_star");
  const why = $("d5Why");
  why.className = "tl-box " + (st === "ok" ? "okc" : st === "no_star" ? "plain" : "warn");
  const slowTxt = v.tl_summary.slow.length ? ` ${v.tl_summary.slow.join(", ")} đang Slow nên dài hơn trên timeline.` : "";
  const v2Txt = v.v2_s > 0 ? ` ${v.tl_summary.v2.join(", ")} chạy chồng trên V2 nên <b>không cộng</b> vào độ dài.` : "";
  why.innerHTML = `Timeline đang dài <b>${d5mm(v.total_s)}</b> (V1).${esc(slowTxt)}${v2Txt}` + (adv.reasons.length ? "<br>" + adv.reasons.map(esc).join("<br>") : "");
  const sug = (id, o) => { const b = $(id); b.classList.toggle("hidden", !o); if (o) { b.querySelector("b").textContent = o.title; b.querySelector("span").textContent = o.text; } };
  sug("d5SugA", adv.rebalance); sug("d5SugB", adv.lower); sug("d5SugC", adv.unslow); sug("d5SugD", adv.fit); sug("d5SugE", adv.step3);
  $("d5SugH").classList.toggle("hidden", !(adv.rebalance || adv.lower || adv.unslow || adv.fit || adv.step3));
  const ws = v.warnings.filter((x) => x.kind !== "target_short" && x.kind !== "no_star");
  const w = $("d5Warn");
  if (ws.length) { w.innerHTML = ws.map((x) => `<span>⚠ ${esc(x.text)}</span>`).join(""); w.classList.remove("hidden"); } else w.classList.add("hidden");
  $("d5Create").disabled = !v.items.length;
  $("d5CreateHint").innerHTML = `Timeline mới có 2 track hình V1, V2 đúng như trên màn hình, tên “Rough Cut sao ${esc(v.project || "")} &lt;ngày giờ&gt;”. Không sửa timeline đang có.`;
  $("d5FootL").textContent = `${v.n_starred} clip sao · V1 ${d5mm(v.total_s)}${v.v2_s > 0 ? ` · V2 chồng ${d5mm(v.v2_s)}` : ""} · mục tiêu ${d5mm(v.target_s)}`;
  if (keep) {
    const el = document.querySelector(`[data-k="${CSS.escape(keep.k)}"]`);
    if (el) { el.value = keep.val; el.focus(); try { el.setSelectionRange(keep.a, keep.b); } catch (e) { /* ô số */ } }
  }
}

/* bảng thứ tự của cụm đang chọn */
function d5PaintOrder(v) {
  const L = v.tl, c = L.clusters.find((x) => x.stage === D5.sel);
  if (!c) { $("d5Order").innerHTML = '<div class="dim13">Chưa có cụm nào có clip sao.</div>'; return; }
  const stI = v.stages[c.i];
  const rows = c.kids.map((k, idx) => {
    const b = L.blocks[k];
    const spTxt = b.speed.mode === "mixed" ? "nhiều mức" : b.speed.mode === "auto" ? `Slow ${d5Pct(b.speed.pct)}` : b.speed.mode === "custom" ? d5Pct(b.speed.pct) : "100%";
    const slow = b.speed.mode !== "100";
    const own = b.speed.own ? "" : (c.speed_own || (D5.v.tl.clusters.find((x) => x.stage === b.cluster) || {}).speed_own ? "" : "");
    const raTxt = Math.abs(b.take_src - b.dur) >= 0.5 ? `<span class="tl-ra">→ ${d5mm(b.dur)}</span>` : "";
    return `<div class="tl-tb${b.key === D5.hl ? " hl" : ""}${b.cluster !== b.stage ? " foreign" : ""}" data-row="${esc(k)}" data-idx="${idx}">
      <span class="tl-c0">${idx + 1}</span><span class="tl-cg tl-grip" data-rowgrab="${esc(k)}" title="Kéo để đổi thứ tự">${SVG_GRIP}</span>
      <span class="tl-c1"><i class="tl-dot" style="background:${b.color}"></i><span title="${esc(b.bin)}">${esc(b.bin)}${b.cluster !== b.stage ? ` <em>(từ ${esc(b.stage)})</em>` : ""}</span></span>
      <span class="tl-c2">${d5mm(b.have * (b.take_src > 0 && b.dur > 0 ? b.take_src / b.dur : 1))} · ${b.n_starred} clip</span>
      <span class="tl-c3"><input class="tl-inp sm${b.pin != null ? " pin" : ""}" data-k="take:${esc(k)}" data-key="${esc(k)}" type="text" value="${d5mm(b.take_src)}" autocomplete="off" aria-label="${esc(b.bin)} lấy (gốc)">${raTxt}</span>
      <span class="tl-c4"><button class="tl-trk${b.track === "V2" ? " v2" : ""}" data-track="${esc(k)}" title="Bấm để chuyển V1 / V2">${b.track === "V2" ? "V2 · chồng" : "V1"}</button></span>
      <span class="tl-c6"><button class="tl-trk${slow ? " sl" : ""}" data-speed="blk:${esc(k)}" title="Tốc độ của khối">${spTxt}</button></span>
      <span class="tl-c7"><button class="tl-tog${b.mute ? " off" : ""}" data-mute="blk:${esc(k)}" aria-pressed="${!b.mute}">${b.mute ? "Tắt" : "Bật"}</button></span>
      <span class="tl-c5">${b.manual ? '<span class="tl-tagb">xếp tay</span>' : ""}</span></div>`;
  }).join("");
  const locked = stI && stI.locked;
  $("d5Order").innerHTML = `<div class="tl-oh">Thứ tự trong cụm ${String(c.i + 1).padStart(2, "0")}_${esc(c.stage)} <span class="tl-tagb">bấm khối mẹ trên timeline để chọn cụm</span>
      <span class="tl-ctl2"><input class="tl-inp" data-k="stage:${c.i}" data-stage="${c.i}" type="text" value="${d5mm(stI ? (stI.pinned ? stI.budget_s : stI.total_s) : 0)}" autocomplete="off" aria-label="Thời lượng cụm ${esc(c.stage)}, phút:giây" title="Thời lượng RA TIMELINE của cụm (V1), không vượt thanh đầy">
        <button class="tl-lkb${locked ? " on" : ""}" data-lock="${c.i}" aria-pressed="${!!locked}" aria-label="Khóa thời lượng cụm" title="${locked ? "Đang khóa thời lượng cụm này. Bấm để mở." : "Khóa thời lượng cụm này (cụm khác tự co giãn). Ổ khóa chỉ khóa thời lượng, không khóa vị trí."}">${SVG_LOCK(locked)}</button></span></div>
    <div class="tl-th"><span class="tl-c0">#</span><span class="tl-cg"></span><span class="tl-c1">BIN CON</span><span class="tl-c2">CÓ</span><span class="tl-c3">LẤY (gốc → ra)</span><span class="tl-c4">TRACK</span><span class="tl-c6">TỐC ĐỘ</span><span class="tl-c7">TIẾNG</span><span class="tl-c5">GHI CHÚ</span></div>
    ${rows || '<div class="dim13" style="padding:10px 0">Cụm này chưa có khối nào.</div>'}
    <div class="tl-note">Kéo dòng bằng chấm sáu nút để đổi thứ tự; bấm ô Track để chuyển V1 / V2. Tốc độ: 100% (giữ nguyên), “Slow mượt tự tính” (fps timeline ÷ fps source của từng clip${v.tl_fps_known ? `, timeline ${v.tl_fps_known} fps` : ", chưa đọc được fps timeline nên tạm tính 25"}) hoặc gõ số. Mỗi khối (mẹ hoặc con) có công tắc Tiếng và Tốc độ riêng; đặt ở khối mẹ thì áp cho mọi khối con, khối con đặt riêng thì thắng. Slow giữ nguyên In/Out đã đặt nên clip dài hơn trên timeline và các clip sau bị đẩy ra sau.</div>`;
}

/* ------------------------------------------------------------------ kéo thả */
const d5T = (x, lane) => { const r = lane.getBoundingClientRect(); return Math.max(0, (x - r.left) / r.width * D5.T); };
function d5ClearDrop() { document.querySelectorAll(".tl-drop").forEach((e) => e.remove()); document.querySelectorAll(".dragging").forEach((e) => e.classList.remove("dragging")); }
function d5Drop(lane, t, label) {
  const el = document.createElement("i"); el.className = "tl-drop"; el.style.left = (t / D5.T * 100) + "%"; el.innerHTML = `<em>${label}</em>`;
  lane.appendChild(el);
}

/* đích của một khối con khi thả: V2 (theo thời gian) hoặc V1 (cụm + vị trí) */
function d5BlockTarget(e, key) {
  const L = D5.v.tl, v1 = $("d5V1"), v2 = $("d5V2");
  const r2 = v2.getBoundingClientRect(), r1 = v1.getBoundingClientRect();
  const b = L.blocks[key];
  if (e.clientY < (r2.bottom + r1.top) / 2) {                                    // hàng V2
    const at = Math.max(0, d5T(e.clientX, v2) - (D5.drag.grabT || 0));
    return { track: "V2", at: Math.round(at * 10) / 10, lane: v2, x: at };
  }
  const t = d5T(e.clientX, v1);
  let cl = L.clusters.find((c) => c.v1.length && t >= c.start && t <= c.start + c.dur);
  if (!cl) {
    const cands = L.clusters.filter((c) => c.v1.length || c.stage === (L.blocks[key] || {}).cluster);
    cl = cands.reduce((best, c) => (!best || Math.abs(c.start + c.dur / 2 - t) < Math.abs(best.start + best.dur / 2 - t) ? c : best), null) || L.clusters[0];
  }
  const kids = cl.v1.filter((k) => k !== key);
  let idx = 0;
  for (const k of kids) { const kb = L.blocks[k]; if (kb.start + kb.dur / 2 < t) idx++; }
  const xs = idx === 0 ? (kids.length ? L.blocks[kids[0]].start : cl.start) : (L.blocks[kids[idx - 1]].start + L.blocks[kids[idx - 1]].dur);
  return { track: "V1", cluster: cl.stage, index: idx, lane: v1, x: xs };
}
function d5ClusterTarget(e, stage) {
  const L = D5.v.tl, v1 = $("d5V1"), t = d5T(e.clientX, v1);
  const others = L.clusters.filter((c) => c.stage !== stage);
  let idx = 0;
  for (const c of others) if (c.start + c.dur / 2 < t) idx++;
  const x = idx === 0 ? 0 : (others[idx - 1].start + others[idx - 1].dur);
  return { index: idx, lane: v1, x };
}

$("d5Tl").addEventListener("pointerdown", (e) => {
  if (e.button != null && e.button !== 0) return;
  if (e.target.closest("[data-mute],[data-speed],input,button")) return;
  const rz = e.target.closest("[data-resize]");
  const gb = !rz && e.target.closest("[data-grab]");
  const blk = !rz && !gb && e.target.closest("[data-blk]");
  const fr = !rz && !gb && !blk && e.target.closest("[data-cl]");
  if (!(rz || gb || blk || fr)) return;
  e.preventDefault();
  const dg = { x0: e.clientX, y0: e.clientY, pid: e.pointerId, moved: false };
  if (rz) { dg.kind = "resize"; dg.key = rz.dataset.resize; dg.el = rz.parentElement.classList.contains("tl-fr") ? rz.parentElement : rz.parentElement; }
  else if (gb) { dg.kind = "cl"; dg.key = gb.dataset.grab; dg.el = gb.closest("[data-cl]"); }
  else if (blk) {
    dg.kind = "blk"; dg.key = blk.dataset.blk; dg.el = blk;
    const b = D5.v.tl.blocks[dg.key], lane = b.track === "V2" ? $("d5V2") : $("d5V1");
    dg.grabT = Math.max(0, d5T(e.clientX, lane) - b.start);
  } else { dg.kind = "sel"; dg.key = fr.dataset.cl; }
  D5.drag = dg;
  window.addEventListener("pointermove", d5Move); window.addEventListener("pointerup", d5Up); window.addEventListener("pointercancel", d5Cancel);
});
function d5Move(e) {
  const dg = D5.drag; if (!dg || e.pointerId !== dg.pid) return;
  if (!dg.moved && Math.abs(e.clientX - dg.x0) + Math.abs(e.clientY - dg.y0) < 5) return;
  dg.moved = true;
  d5ClearDrop();
  if (dg.kind === "resize") {
    const k = dg.key.split(":"), L = D5.v.tl;
    let lane, left, have, avail, cur;
    if (k[0] === "s") {
      const c = L.clusters.find((x) => x.i === +k[1]); const si = D5.v.stages[+k[1]];
      lane = $("d5V1"); left = c.start; avail = si.avail_s; cur = c.dur;
    } else { const b = L.blocks[k.slice(1).join(":")]; lane = b.track === "V2" ? $("d5V2") : $("d5V1"); left = b.start; avail = b.avail; cur = b.dur; }
    let s = Math.max(0, Math.min(avail, d5T(e.clientX, lane) - left));
    s = e.shiftKey ? Math.round(s * 10) / 10 : Math.round(s);
    dg.v = s;
    dg.el.classList.add("dragging");
    d5Drop(lane, left + s, `${d5mm(s)}${s >= avail - 0.4 ? " (hết cỡ)" : ""}`);
    return;
  }
  if (dg.kind === "cl") { dg.target = d5ClusterTarget(e, dg.key); dg.el.classList.add("dragging"); d5Drop(dg.target.lane, dg.target.x, "thả vào đây"); }
  else if (dg.kind === "blk") { dg.target = d5BlockTarget(e, dg.key); dg.el.classList.add("dragging"); d5Drop(dg.target.lane, dg.target.x, dg.target.track === "V2" ? "thả lên V2" : "thả vào đây"); }
}
function d5EndDrag() {
  window.removeEventListener("pointermove", d5Move); window.removeEventListener("pointerup", d5Up); window.removeEventListener("pointercancel", d5Cancel);
  d5ClearDrop(); D5.drag = null;
}
function d5Cancel() { d5EndDrag(); if (D5.pending) d5Paint(); }
async function d5Up(e) {
  const dg = D5.drag; if (!dg || e.pointerId !== dg.pid) return;
  const moved = dg.moved;
  d5EndDrag();
  if (!moved) {                                                          // chỉ bấm: chọn cụm / khối
    if (dg.kind === "blk") { const b = D5.v.tl.blocks[dg.key]; D5.sel = b.cluster; D5.hl = dg.key; }
    else if (dg.kind === "cl" || dg.kind === "sel") D5.sel = dg.key;
    d5Paint(); return;
  }
  if (dg.kind === "resize") {
    const k = dg.key.split(":");
    if (k[0] === "s") return void d5Run(() => api().dur_set_stage(+k[1], dg.v));
    const b = D5.v.tl.blocks[k.slice(1).join(":")];
    return void d5Run(() => api().dur_set_bin_take(D5.v.stages.findIndex((s) => s.name === b.stage), b.bin, dg.v));
  }
  if (dg.kind === "cl") { D5.sel = dg.key; return void d5Run(() => api().dur_tl_move_cluster(dg.key, dg.target.index), "Đã dời cả cụm (con đi theo)."); }
  if (dg.kind === "blk") {
    const t = dg.target, b = D5.v.tl.blocks[dg.key];
    D5.hl = dg.key;
    if (t.track === "V2") return void d5Run(() => api().dur_tl_set_track(dg.key, "V2", t.at), "Khối chạy chồng trên V2 (không cộng vào độ dài).");
    D5.sel = t.cluster;
    if (b.track === "V2") await api().dur_tl_set_track(dg.key, "V1");     // từ V2 về V1: chuyển track rồi đặt đúng chỗ
    return void d5Run(() => api().dur_tl_move_block(dg.key, t.cluster, t.index), t.cluster === b.cluster ? "Đã đổi thứ tự." : "Đã chuyển khối sang cụm khác.");
  }
}

/* kéo dòng trong bảng thứ tự (đồng bộ với timeline) */
$("d5Order").addEventListener("pointerdown", (e) => {
  const g = e.target.closest("[data-rowgrab]"); if (!g || (e.button != null && e.button !== 0)) return;
  e.preventDefault();
  D5.drag = { kind: "row", key: g.dataset.rowgrab, x0: e.clientX, y0: e.clientY, pid: e.pointerId, moved: false };
  window.addEventListener("pointermove", d5RowMove); window.addEventListener("pointerup", d5RowUp); window.addEventListener("pointercancel", d5Cancel);
});
function d5RowTarget(e) {
  const rows = [...document.querySelectorAll("#d5Order .tl-tb")].filter((r) => r.dataset.row !== D5.drag.key);
  let idx = 0;
  for (const r of rows) { const b = r.getBoundingClientRect(); if (e.clientY > b.top + b.height / 2) idx++; }
  return { idx, rows };
}
function d5RowMove(e) {
  const dg = D5.drag; if (!dg || e.pointerId !== dg.pid) return;
  if (!dg.moved && Math.abs(e.clientY - dg.y0) < 4) return;
  dg.moved = true;
  document.querySelectorAll("#d5Order .tl-tb").forEach((r) => r.classList.remove("dropbefore", "dropafter", "dragging"));
  const { idx, rows } = d5RowTarget(e);
  const me = document.querySelector(`#d5Order .tl-tb[data-row="${CSS.escape(dg.key)}"]`); if (me) me.classList.add("dragging");
  if (idx < rows.length) rows[idx].classList.add("dropbefore"); else if (rows.length) rows[rows.length - 1].classList.add("dropafter");
  dg.idx = idx;
}
async function d5RowUp(e) {
  const dg = D5.drag; if (!dg || e.pointerId !== dg.pid) return;
  window.removeEventListener("pointermove", d5RowMove); window.removeEventListener("pointerup", d5RowUp); window.removeEventListener("pointercancel", d5Cancel);
  document.querySelectorAll("#d5Order .tl-tb").forEach((r) => r.classList.remove("dropbefore", "dropafter", "dragging"));
  D5.drag = null;
  if (!dg.moved || dg.idx == null) return;
  const L = D5.v.tl, c = L.clusters.find((x) => x.stage === D5.sel); if (!c) return;
  const others = c.kids.filter((k) => k !== dg.key);
  const v1Before = others.slice(0, dg.idx).filter((k) => L.blocks[k].track === "V1").length;       // vị trí chèn tính theo các khối V1
  D5.hl = dg.key;
  d5Run(() => api().dur_tl_move_block(dg.key, c.stage, v1Before), "Đã đổi thứ tự.");
}

/* ------------------------------------------------------------------ menu tốc độ, công tắc tiếng, track, khóa, gõ số */
function d5CloseMenu() { if (D5.menu) { D5.menu.remove(); D5.menu = null; } }
function d5Menu(anchor, kind, name, cur) {
  d5CloseMenu();
  const m = document.createElement("div"); m.className = "tl-menu"; m.setAttribute("role", "menu");
  const fps = D5.v.tl_fps_known;
  const item = (label, sub, spec, active) => `<button class="tl-mi${active ? " on" : ""}" role="menuitem" data-spec='${JSON.stringify(spec)}'><b>${label}</b>${sub ? `<span>${sub}</span>` : ""}</button>`;
  m.innerHTML = item("100% (giữ nguyên)", "", 100, cur.mode === "100") +
    item("Slow mượt tự tính", `fps timeline ÷ fps source${fps ? ` (timeline ${fps} fps)` : ""}: 50p→25p = 50%, 60p→25p = 41,7%`, "auto", cur.mode === "auto") +
    `<div class="tl-mi num"><b>Gõ số %</b><input type="text" inputmode="decimal" placeholder="ví dụ 50" aria-label="Tốc độ phần trăm"></div>` +
    (kind === "block" ? item("Theo cụm mẹ", "bỏ đặt riêng của khối này", null, false) : "");
  document.body.appendChild(m);
  const r = anchor.getBoundingClientRect();
  m.style.left = Math.max(8, Math.min(window.innerWidth - 300, r.left)) + "px";
  m.style.top = Math.min(window.innerHeight - m.offsetHeight - 8, r.bottom + 4) + "px";
  D5.menu = m;
  const apply = (spec) => { d5CloseMenu(); d5Run(() => api().dur_tl_set_speed(kind, name, spec), "Đã đặt tốc độ. Chưa ghi gì vào DaVinci."); };
  m.addEventListener("click", (ev) => { const b = ev.target.closest(".tl-mi[data-spec]"); if (b) apply(JSON.parse(b.dataset.spec)); });
  const inp = m.querySelector("input");
  inp.addEventListener("keydown", (ev) => {
    if (ev.code === "Enter" || ev.code === "NumpadEnter") { const n = Number(String(inp.value).replace(",", ".")); if (!(n >= 5 && n <= 400)) return status("Tốc độ từ 5% đến 400%.", "warn"); apply(n); }
    if (ev.code === "Escape") d5CloseMenu();
    ev.stopPropagation();
  });
  inp.focus();
}
document.addEventListener("pointerdown", (e) => { if (D5.menu && !e.target.closest(".tl-menu") && !e.target.closest("[data-speed]")) d5CloseMenu(); }, true);
document.addEventListener("keydown", (e) => { if (e.code === "Escape" && D5.menu) d5CloseMenu(); });

function d5Click(e) {
  const sp = e.target.closest("[data-speed]");
  if (sp && D5.v) {
    const [k, ...rest] = sp.dataset.speed.split(":"), name = rest.join(":");
    if (k === "cl") return d5Menu(sp, "stage", name, (D5.v.tl.clusters.find((c) => c.stage === name) || {}).speed || { mode: "100" });
    return d5Menu(sp, "block", name, D5.v.tl.blocks[name].speed);
  }
  const mu = e.target.closest("[data-mute]");
  if (mu && D5.v) {
    const [k, ...rest] = mu.dataset.mute.split(":"), name = rest.join(":");
    const cur = k === "cl" ? (D5.v.tl.clusters.find((c) => c.stage === name) || {}).mute : D5.v.tl.blocks[name].mute;
    return d5Run(() => api().dur_tl_set_mute(k === "cl" ? "stage" : "block", name, cur === true ? false : true), "Đã đổi tiếng. Chưa ghi gì vào DaVinci.");
  }
  const tk = e.target.closest("[data-track]");
  if (tk && D5.v) {
    const b = D5.v.tl.blocks[tk.dataset.track];
    return d5Run(() => api().dur_tl_set_track(b.key, b.track === "V2" ? "V1" : "V2", b.track === "V2" ? null : Math.round(b.start * 10) / 10),
      b.track === "V2" ? "Khối về V1." : "Khối chạy chồng trên V2 (không cộng vào độ dài).");
  }
  const lk = e.target.closest("[data-lock]");
  if (lk) return d5Run(() => api().dur_toggle_lock(+lk.dataset.lock));
  const row = e.target.closest("[data-row]");
  if (row && !e.target.closest("input,button")) { D5.hl = row.dataset.row; d5Paint(); }
}
$("d5Tl").addEventListener("click", d5Click);
$("d5Order").addEventListener("click", d5Click);

/* ---- gõ phút:giây (mục tiêu, cụm, khối) ---- */
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

function d5CommitField(el, final) {
  if (!D5.v) return;
  const k = el.dataset.k || "";
  const txt = el.value;
  if (k.startsWith("stage:")) {                           // thời lượng RA TIMELINE của cụm
    const i = +el.dataset.stage;
    if (txt.trim() === "") { if (final) d5Run(() => api().dur_set_stage(i, "")); return; }
    if (!final && !d5Stable(txt)) return;
    const sec = d5Parse(txt, "sec");
    if (sec === null) { if (final) { status("Gõ phút:giây, ví dụ 4:30.", "warn"); d5Paint(); } return; }
    const s = D5.v.stages[i];
    if (Math.abs((s.pinned ? s.budget_s : s.total_s) - sec) < 0.5) { if (final) d5Paint(); return; }
    return void d5Run(() => api().dur_set_stage(i, sec));
  }
  if (k.startsWith("take:")) {                            // LẤY gốc của khối: đổi sang RA = gốc / tốc độ trung bình của khối
    const key = el.dataset.key, b = D5.v.tl.blocks[key];
    if (txt.trim() === "") { if (final) d5Run(() => api().dur_set_bin_take(D5.v.stages.findIndex((s) => s.name === b.stage), b.bin, "")); return; }
    if (!final && !d5Stable(txt)) return;
    const g = d5Parse(txt, "sec");
    if (g === null) { if (final) { status("Gõ phút:giây, ví dụ 0:50.", "warn"); d5Paint(); } return; }
    const ra = b.take_src > 0 && b.dur > 0 ? g * b.dur / b.take_src : g / ((b.speed.pct || 100) / 100);
    return void d5Run(() => api().dur_set_bin_take(D5.v.stages.findIndex((s) => s.name === b.stage), b.bin, ra));
  }
}
document.addEventListener("input", (e) => { const el = e.target; if (page !== 5 || !el.dataset || !el.dataset.k || el.id === "durTarget") return; d5Schedule(el.dataset.k, () => d5CommitField(el, false), 700); });
document.addEventListener("change", (e) => { const el = e.target; if (page !== 5 || !el.dataset || !el.dataset.k || el.id === "durTarget") return; d5Clear(el.dataset.k); d5CommitField(el, true); });
document.addEventListener("keydown", (e) => { const el = e.target; if (page === 5 && el.dataset && el.dataset.k && el.id !== "durTarget" && (e.code === "Enter" || e.code === "NumpadEnter")) el.blur(); });

/* Điều hướng bằng bàn phím chuẩn DaVinci ở Page 5: ←/→ chuyển cụm sự kiện mượt mà */
document.addEventListener("keydown", (e) => {
  if (page !== 5 || !D5.v || !D5.v.stages || !D5.v.stages.length) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.code === "ArrowLeft" || e.code === "ArrowRight") {
    e.preventDefault();
    const list = D5.v.stages;
    let idx = list.findIndex((s) => s.name === D5.sel);
    if (idx < 0) idx = 0;
    else idx = Math.max(0, Math.min(list.length - 1, idx + (e.code === "ArrowLeft" ? -1 : 1)));
    D5.sel = list[idx].name;
    d5Paint();
  }
});

/* ---- nút trên cùng, cột phải ---- */
$("d5Reset").addEventListener("click", async () => {
  if (!D5.v) return;
  if (D5.v.tl_manual) {
    const ok = await ask("Xếp lại theo giờ quay?", "Bạn đã xếp tay (dời cụm, đổi thứ tự, chuyển V2). Bấm đồng ý sẽ đưa thứ tự và V1/V2 về mặc định theo giờ quay thật. <b>Tốc độ và tiếng giữ nguyên.</b> Chỉ đổi trong panel, chưa chạm DaVinci.", "Xếp lại");
    if (!ok) return;
  }
  D5.hl = null;
  d5Run(() => api().dur_tl_reset(), "Đã xếp lại theo giờ quay.");
});
$("d5SugA").addEventListener("click", () => d5Run(() => api().dur_rebalance(), "Đã tự kéo thêm cho đủ mục tiêu. Chưa tạo gì trong DaVinci."));
$("d5SugB").addEventListener("click", () => d5Run(() => api().dur_lower_target(), "Đã hạ mục tiêu xuống số Hiện Tại."));
$("d5SugC").addEventListener("click", () => d5Run(() => api().dur_tl_unslow(), "Đã đưa khối Slow về 100%."));
$("d5SugD").addEventListener("click", () => d5Run(() => api().dur_fit_over(), "Đã thả số đã kéo để bỏ clip ít ưu tiên cho vừa mục tiêu (bạn xem danh sách bỏ trong dòng cụm)."));
$("d5SugE").addEventListener("click", () => {
  const a = D5.v && D5.v.advice.step3; if (!a) return;
  P3.onlyStar = false;                                           // cần thấy cả clip CHƯA sao để chọn thêm
  goPage(3);
  p3View(a.stage, a.bin === "(chưa xếp bin)" ? NONE : a.bin);
  status(`Bước 3: đang xem ${a.bin} của giai đoạn ${S.stages[a.stage] ? S.stages[a.stage].bin : ""}. Bấm J để gắn sao clip muốn dùng.`, "info");
});

/* ---- Đưa lên Timeline mới (luôn bấm được khi có clip; hộp xác nhận ghi dư/thiếu, Slow, tắt tiếng) ---- */
$("d5Create").addEventListener("click", async () => {
  const v = D5.v; if (!v || !v.items.length) return status("Chưa có clip sao ★ nào để đưa lên.", "warn");
  const sm = v.tl_summary, short = v.short_s || 0;
  const gap = v.state === "short" ? `<div class="tl-warn"><b>Đang thiếu ${d5mm(short)}</b> so với mục tiêu ${d5mm(v.target_s)}: chưa đủ clip sao. Vẫn tạo được; Trợ lý không tự thêm clip.</div>`
    : v.state === "over" ? `<div class="tl-warn"><b>Đang dư ${d5mm(v.delta_s)}</b> so với mục tiêu ${d5mm(v.target_s)}. Vẫn tạo được; Trợ lý không tự bỏ clip của bạn.</div>` : `<div>Khớp mục tiêu ${d5mm(v.target_s)}.</div>`;
  const ok = await ask("Tạo timeline mới?",
    `<div>Tên: <b>Rough Cut sao ${esc(v.project || "")} &lt;ngày giờ lúc bấm&gt;</b></div><div>Độ dài V1: <b>${d5mm(v.total_s)}</b> · mục tiêu ${d5mm(v.target_s)}</div>` +
    `<div>Số clip: <b>${sm.n_v1 + sm.n_v2}</b> (V1 ${sm.n_v1}${sm.n_v2 ? `, V2 chồng ${sm.n_v2}` : ""}) / ${v.n_starred} clip sao</div>` + gap +
    `<div>Khối Slow: <b>${sm.slow.length ? esc(sm.slow.join(", ")) : "không có"}</b></div><div>Khối tắt tiếng: <b>${sm.muted.length ? esc(sm.muted.join(", ")) : "không có"}</b></div>` +
    `<div>Thứ tự: theo cách bạn xếp trên màn hình (V1 rồi V2 chồng)</div><br>Chỉ tạo <b>MỘT timeline MỚI</b> có 2 track hình V1, V2. Không sửa hay xóa timeline đang có, không ghi In/Out lên clip gốc. Slow giữ nguyên In/Out nên clip dài hơn và các clip sau V1 bị đẩy ra sau. Tắt tiếng chỉ tắt clip tiếng của khối (A1 cho V1, A2 cho V2), không đụng A3 trở lên. Trợ lý ghi nhật ký trước khi tạo và đọc lại vị trí để kiểm.`,
    "Tạo timeline mới");
  if (!ok) return status("Đã hủy, chưa tạo gì trong DaVinci.", "info");
  const r = await api().dur_create_timeline();
  if (r.error) return status(r.error, "warn");
  status(`Đang tạo timeline “${r.name}”...`, "info");
});
window.addEventListener("resize", () => { if (page === 5) d5Paint(); });
