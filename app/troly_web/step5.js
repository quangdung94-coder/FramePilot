/* Bước 5: Thời lượng (ADR-0013; demo design/4_thoi_luong). Số mặc định là ĐỀ XUẤT, anh sửa được.
   Panel chỉ tính kế hoạch cắt gọt; "Đưa lên Timeline mới" chỉ tạo MỘT timeline mới sau hộp xác nhận (api().dur_create_timeline). */
const D5 = { v: null, sel: 0, drag: null };
const D5_SCALE = 90;
const d5mm = (s) => durTxt(s);
const d5Signed = (s) => (s < 0 ? "−" : "+") + durTxt(Math.abs(s));

async function renderPage5() {
  if (page !== 5) return;
  if (!S || !S.n) { D5.v = null; d5Paint(); return; }
  D5.v = await api().dur_state();
  d5Paint();
}

function d5Apply(v) {                                  // kết quả của một lệnh sửa/cắt gọt
  if (v && v.error) { status(v.error, "warn"); return renderPage5(); }
  D5.v = v; d5Paint();
}

function d5Paint() {
  const v = D5.v;
  const empty = !v;
  $("d5Create").disabled = empty || !v.cut_ready || !v.items.length;
  $("d5Cut").disabled = empty;
  if (empty) {
    $("d5Total").textContent = "0:00"; $("d5TotalSub").textContent = 'Bấm "Đọc clip" ở bước 1 trước.'; $("d5TotalSub").className = "d5-sub";
    $("d5Shots").textContent = "0 / 0"; $("d5ShotsSub").textContent = "";
    $("d5Stages").innerHTML = ""; $("d5Legend").innerHTML = ""; $("d5Strip").innerHTML = ""; $("d5Rows").innerHTML = ""; $("d5Warn").classList.add("hidden");
    $("d5StageTitle").textContent = "Giai đoạn trên timeline"; return;
  }
  if (D5.sel >= v.stages.length) D5.sel = 0;
  if (document.activeElement !== $("durTarget")) $("durTarget").value = v.target_min;
  // thẻ tổng
  $("d5Total").textContent = d5mm(v.total_s);
  const tol = v.target_s * 0.05;
  const sub = $("d5TotalSub");
  if (!v.n_starred) { sub.textContent = "Chưa có clip sao ★ (phím J ở Bước 2)"; sub.className = "d5-sub warn"; }
  else if (Math.abs(v.delta_s) <= tol) { sub.textContent = `Sát mục tiêu ${d5mm(v.target_s)} (chênh ${d5Signed(v.delta_s)})`; sub.className = "d5-sub ok"; }
  else { sub.textContent = `Mục tiêu ${d5mm(v.target_s)} · chênh ${d5Signed(v.delta_s)} (${v.delta_s < 0 ? "ngắn hơn" : "dài hơn"})`; sub.className = "d5-sub warn"; }
  $("d5Shots").textContent = `${v.n_used} / ${v.n_clips}`;
  $("d5ShotsSub").textContent = `Chọn từ ${v.n_starred} clip có sao ★, theo bảng quy tắc từng bin ở Bước 3`;
  // thanh chia giai đoạn
  $("d5Stages").innerHTML = v.stages.map((s, i) =>
    `<div class="d5-seg${i === D5.sel ? " sel" : ""}" data-i="${i}" style="flex:${Math.max(s.share, 0.005)} 1 0;background:${s.color || "#888"}" title="${esc(s.name)} · ${Math.round(s.share * 100)}% = ${d5mm(s.budget_s)}">${d5mm(s.budget_s)}${i < v.stages.length - 1 ? '<span class="d5-grip" data-grip="' + i + '"></span>' : ""}</div>`).join("");
  $("d5Legend").innerHTML = v.stages.map((s, i) => `<span data-i="${i}" class="${i === D5.sel ? "sel" : ""}"><i style="background:${s.color || "#888"}"></i>${esc(s.name)} · ${Math.round(s.share * 100)}%</span>`).join("");
  // giai đoạn đang chọn
  const st = v.stages[D5.sel];
  $("d5StageTitle").textContent = `${st.name} trên timeline · ${d5mm(st.total_s)}`;
  const shown = st.bins.filter((b) => b.total_s > 0);
  $("d5Strip").innerHTML = shown.length ? shown.map((b) => `<div class="d5-bin" style="flex:${Math.max(b.total_s, 1)} 1 0;background:${b.color}33;border:1px solid ${b.color}"><b title="${esc(b.name)}">${esc(b.name)}</b><span>${Math.round(b.total_s)}s</span></div>`).join("")
    : '<div class="d5-bin" style="flex:1;border:1px dashed #4A4A52"><span>Chưa có clip sao nào trong giai đoạn này</span></div>';
  $("d5Rows").innerHTML = st.bins.map((b, j) => {
    const left = Math.min(100, b.min / D5_SCALE * 100), wid = Math.max(0.6, Math.min(100 - left, (b.max - b.min) / D5_SCALE * 100));
    const mark = Math.min(98.5, b.total_s / D5_SCALE * 100);
    return `<div class="d5-row" data-bin="${esc(b.name)}">
      <span class="d5-name"><i style="background:${b.color}"></i><span title="${esc(b.name)}">${esc(b.name)}</span>${b.edited ? "" : "<em>đề xuất</em>"}</span>
      <span class="d5-mm"><input class="num${b.edited ? " ed" : ""}" data-k="min" type="number" min="0" step="1" value="${b.min}"> – <input class="num${b.edited ? " ed" : ""}" data-k="max" type="number" min="0" step="1" value="${b.max}"> giây</span>
      <div class="d5-track"><div class="d5-range" style="left:${left}%;width:${wid}%;background:${b.color}33;border:1px solid ${b.color}"></div><div class="d5-mark" style="left:calc(${mark}% - 2px)"></div></div>
      <span style="font-weight:600">${Math.round(b.total_s)}s</span><span class="dim">${b.shots}${b.dropped ? " (bỏ " + b.dropped + ")" : ""}</span></div>`;
  }).join("");
  // cảnh báo
  const w = $("d5Warn");
  if (v.warnings.length) { w.innerHTML = v.warnings.map((x) => `<span>⚠ ${esc(x.text)}</span>`).join(""); w.classList.remove("hidden"); } else w.classList.add("hidden");
  $("d5Reset").classList.toggle("hidden", !(v.edited.target || v.edited.share || v.edited.bins));
  $("d5Create").title = v.cut_ready ? "Tạo MỘT timeline mới từ bản đã cắt gọt" : 'Bấm "Cắt gọt cho vừa" trước (và sau mỗi lần chỉnh)';
}

/* ---- Video mục tiêu ---- */
$("durTarget").addEventListener("change", async () => {
  if (!S || !S.n) return;
  d5Apply(await api().dur_set_target($("durTarget").value));
});

/* ---- Min / Max từng bin ---- */
$("d5Rows").addEventListener("change", async (e) => {
  const row = e.target.closest(".d5-row[data-bin]"); if (!row || !D5.v) return;
  const mn = row.querySelector('[data-k="min"]').value, mx = row.querySelector('[data-k="max"]').value;
  d5Apply(await api().dur_set_bin(D5.sel, row.dataset.bin, mn, mx));
});

/* ---- chọn giai đoạn + kéo tỉ lệ ---- */
$("d5Legend").addEventListener("click", (e) => { const s = e.target.closest("span[data-i]"); if (s) { D5.sel = +s.dataset.i; d5Paint(); } });
$("d5Stages").addEventListener("mousedown", (e) => {
  const grip = e.target.closest(".d5-grip");
  if (grip) {                                          // kéo vạch giữa giai đoạn i và i+1
    e.preventDefault();
    const i = +grip.dataset.grip, bar = $("d5Stages"), shares = D5.v.stages.map((s) => s.share);
    const before = shares.slice(0, i).reduce((a, b) => a + b, 0);
    D5.drag = { i, bar, before, shares, value: null };
    return;
  }
  const seg = e.target.closest(".d5-seg"); if (seg) { D5.sel = +seg.dataset.i; d5Paint(); }
});
document.addEventListener("mousemove", (e) => {
  const d = D5.drag; if (!d) return;
  const r = d.bar.getBoundingClientRect();
  const f = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) - d.before;     // phần của giai đoạn i = vị trí vạch − tổng phần trước nó
  d.value = Math.max(0.02, Math.min(1 - 0.02 * (d.shares.length - 1) - d.before, f));
  const rest = d.shares.reduce((a, b, k) => a + (k === d.i ? 0 : b), 0) || 1, rest_new = 1 - d.value;
  const sh = d.shares.map((x, k) => (k === d.i ? d.value : Math.max(0.02, x / rest * rest_new)));
  d.bar.querySelectorAll(".d5-seg").forEach((el, k) => { el.style.flex = `${sh[k]} 1 0`; });
});
document.addEventListener("mouseup", async () => {
  const d = D5.drag; if (!d) return;
  D5.drag = null;
  if (d.value != null) d5Apply(await api().dur_set_share(d.i, d.value)); else d5Paint();
});

/* ---- nút ---- */
$("d5Reset").addEventListener("click", async (e) => { e.preventDefault(); d5Apply(await api().dur_reset()); status("Đã đặt lại về số đề xuất.", "ok"); });
$("d5Cut").addEventListener("click", async () => {
  const v = await api().dur_cut(); D5.v = v; d5Paint();
  if (!v.n_starred) return status("Chưa có clip sao ★. Gắn sao ở Bước 2 trước.", "warn");
  status(`Đã cắt gọt: ${v.n_used} đoạn, tổng ${d5mm(v.total_s)}, chênh ${d5Signed(v.delta_s)} so với mục tiêu ${d5mm(v.target_s)}. Chưa tạo gì trong DaVinci.`, v.warnings.length ? "warn" : "ok");
});
$("d5Create").addEventListener("click", async () => {
  const v = D5.v; if (!v || !v.cut_ready) return status('Hãy bấm "Cắt gọt cho vừa" trước.', "warn");
  const ws = v.warnings.length ? `<br><br><b>Còn ${v.warnings.length} cảnh báo:</b><br>` + v.warnings.slice(0, 5).map((x) => "• " + esc(x.text)).join("<br>") : "";
  const ok = await ask("Đưa lên Timeline mới",
    `Tạo <b>MỘT timeline mới</b> trong DaVinci gồm <b>${v.n_used}</b> đoạn, tổng <b>${d5mm(v.total_s)}</b> (mục tiêu ${d5mm(v.target_s)}, chênh ${d5Signed(v.delta_s)}). ` +
    `Theo thứ tự giai đoạn rồi giờ quay thật. Mỗi đoạn là clip con theo In/Out đã cắt gọt.<br><br>Không sửa hay xóa timeline đang có, không ghi In/Out lên clip gốc. Trợ lý ghi nhật ký trước khi tạo và kiểm lại số timeline sau khi tạo.` + ws,
    "Tạo timeline mới");
  if (!ok) return status("Đã hủy, chưa tạo gì trong DaVinci.", "info");
  const r = await api().dur_create_timeline();
  if (r.error) return status(r.error, "warn");
  status(`Đang tạo timeline “${r.name}”...`, "info");
});
window.addEventListener("resize", () => { if (page === 5) d5Paint(); });
