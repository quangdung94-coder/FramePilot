/* Bước 2: Gợi ý AI (ADR-0022; demo design/6_ai_goi_y). CHỈ GỢI Ý: "Nhận" chỉ gán nhãn trong Trợ lý (api().ai_accept), không gọi DaVinci.
   Chuyển clip vào bin trong DaVinci vẫn là nút "Áp dụng vào Media Pool" (có nhật ký + Hoàn tác). Phím đọc bằng event.code. */
const AI = { info: null, cache: {}, group: null, poll: null, wasRunning: false, seq: 0, scores: null, scoreSig: "", ranKey: null, after: null, busy: false, thrTimer: null, thrPending: false };

function aiPct(x) { return Math.round(x * 100); }
function aiSrcText(src) { return src === "nhan" ? "theo nhãn bạn xếp" : "theo mô tả"; }
function groupKey() { return gStage + "|" + gSub; }
function aiThrNow() { const v = +$("aiThr").value; return v >= 1 && v <= 100 ? v : 50; }
function aiLive() {                                             // nhóm này đã qua Tự phân loại (lần này hoặc lần trước: đang có clip mang dấu AI xếp)
  return AI.ranKey === groupKey() || !!(AI.scores && Object.values(AI.scores).some((x) => x.auto));
}
function aiWait(c) {                                            // clip đã qua "Tự phân loại" ở nhóm này mà hạng 1 còn dưới ngưỡng: chờ bạn duyệt
  if (!c || c.label || !AI.scores || !aiLive()) return null;
  const s = AI.scores[c.uid]; return s && s.score * 100 + 1e-6 < aiThrNow() ? s : null;
}
function aiKey(c) {                                            // khóa để vẽ lại thẻ khi gợi ý đổi
  const g = AI.group && AI.group[c.uid], w = aiWait(c);
  return (g && g.top ? g.top[0].bin + aiPct(g.top[0].score) : "") + (w ? "|w" : "");
}

async function aiRefreshInfo() {
  try { AI.info = await api().ai_info(); } catch (e) { AI.info = null; }
  if (AI.info && AI.info.running && !AI.poll) AI.poll = setInterval(aiTick, 1500);
  if (AI.info && !AI.info.running && AI.poll) { clearInterval(AI.poll); AI.poll = null; }
  return AI.info;
}
async function aiTick() {
  const was = AI.info && AI.info.running;
  await aiRefreshInfo();
  if (was && AI.info && !AI.info.running) {                    // vừa chạy xong (hoặc bị dừng): làm mới gợi ý
    AI.cache = {};
    if (AI.after && AI.info.has_data) { const uids = AI.after; AI.after = null; await aiApplyGroup(uids); }
    else {
      AI.after = null;
      if (AI.group) await aiGroupLoad();
      status(AI.info.has_data ? "AI đã chạy xong. Bấm Tự phân loại để xếp nhóm đang mở." : "AI đã dừng. Bấm Tự phân loại để làm tiếp.");
      if (AI.info.has_data && AI.auto && AI.auto.after_run) await aiAutoRun();
    }
  }
  aiBoxRender();
}

async function aiForCur() {
  const c = items[cur]; if (!c) return null;
  const k = c.uid + "|" + (c.label || "");
  if (AI.cache[k] === undefined) {
    const r = await api().ai_for([c.uid]);
    AI.cache[k] = r[c.uid] || null;
  }
  return AI.cache[k];
}

function aiButtons(list) {                                      // list: [[id, chữ, tắt?]]
  $("aiActs").innerHTML = list.map(([id, t, off, tip]) => `<button class="btn" id="${id}"${off ? " disabled" : ""}${tip ? ` title="${esc(tip)}"` : ""}>${esc(t)}</button>`).join("");
}

function aiRunPaint(info) {                                     // nút Tự phân loại + thanh tiến độ "đã chạy a / b"
  const n = items.length, run = !!(info && info.running);
  const g = (S && gStage !== null && gStage >= 0 && S.stages[gStage]) ? (gSub === null ? S.stages[gStage].bin : gSub === NONE ? "Chưa xếp" : gSub) : "";
  $("aiRunT").textContent = run ? "AI đang chạy…" : `Tự phân loại · ${n} clip${g ? " nhóm " + g : ""}`;
  $("aiRun").disabled = run || AI.busy || !n;
  $("aiRun").classList.toggle("run", run || AI.busy);
  $("aiRunI").textContent = run || AI.busy ? "…" : "▶";
  let w = 0;
  if (run) {
    const m = /(\d+)\/(\d+)/.exec(info.log || "");
    if (m && +m[2]) { w = +m[1] / +m[2] * 100; $("aiRunN").textContent = `AI nhúng ảnh ${m[1]} / ${m[2]}`; } else $("aiRunN").textContent = "AI đang chuẩn bị…";
  } else if (AI.scores && aiLive()) {
    const a = Object.keys(AI.scores).length + items.filter((c) => c.label && c.label_by !== "ai_auto").length;
    w = n ? Math.min(100, a / n * 100) : 0; $("aiRunN").textContent = `đã chạy ${a} / ${n}`;
  } else $("aiRunN").textContent = n ? `chưa chạy · ${n} clip` : "";
  $("aiRunBar").style.width = w + "%";
  $("aiRun").title = info && info.can_run === false && !info.has_data ? "Chưa có venv AI hoặc model, xem ADR-0020" : "Chạy AI (nếu cần) rồi gán nhãn cho cả nhóm đang mở: hạng 1 từ ngưỡng thì tự xếp, còn lại chờ bạn duyệt. Chỉ gán nhãn trong Trợ lý, không chuyển clip trong DaVinci.";
}

async function aiScoresSync() {                                // điểm hạng 1 của nhóm đang mở (cho biểu đồ); chỉ đọc, không gọi AI chạy lại
  const info = AI.info; if (!info || !info.has_data || info.running) return;
  const sig = groupKey() + "#" + items.map((c) => c.uid + (c.label || "") + (c.label_by || "")).join(",");
  if (sig === AI.scoreSig) return;
  AI.scoreSig = sig;
  const r = await api().ai_group_scores(items.map((c) => c.uid));
  if (AI.scoreSig !== sig) return;
  AI.scores = r || {};
  aiHistPaint(); patchGrid(); aiRunPaint(AI.info);
}
function aiHistPaint() {                                       // biểu đồ 10 cột + vạch ngưỡng + hai số, tính tại chỗ từ điểm đã có (không gọi AI)
  const box = $("aiHBars"); if (!box) return;
  const thr = aiThrNow(), sc = AI.scores ? Object.values(AI.scores) : [];
  const cols = new Array(10).fill(0);
  for (const x of sc) cols[Math.min(9, Math.floor(x.score * 10))]++;
  const mx = Math.max(1, ...cols);
  box.innerHTML = cols.map((n, i) => `<div class="ai-hc"><i class="${i * 10 >= thr ? "ok" : ""}" style="height:${n ? Math.max(4, Math.round(n / mx * 100)) : 0}%" title="${i * 10}-${i * 10 + 10}%: ${n} clip"></i></div>`).join("");
  $("aiHLine").style.left = thr + "%";
  const ok = sc.filter((x) => x.score * 100 + 1e-6 >= thr).length;
  $("aiCntOk").textContent = ok; $("aiCntWait").textContent = sc.length - ok;
}

async function aiBoxRender() {
  const box = $("aiBox"); if (!box || page !== 2) return;
  const mySeq = ++AI.seq;
  const info = AI.info || await aiRefreshInfo();
  if (mySeq !== AI.seq) return;
  const c = items[cur];
  aiAutoPaint(info);
  aiRunPaint(info);
  $("aiSrc").textContent = info && info.has_data ? aiSrcText(info.mode) : "";
  if (!info) { $("aiBody").innerHTML = '<span class="ai-msg">Chưa đọc được trạng thái AI.</span>'; aiButtons([]); return; }
  if (info.running) {
    $("aiBody").innerHTML = `<span class="ai-msg">AI đang chạy nền (không ảnh hưởng DaVinci)…<br>${esc(info.log || "")}</span>`;
    aiButtons([["aiStop", "Dừng"]]); return;
  }
  if (!info.has_data) {
    $("aiBody").innerHTML = '<span class="ai-msg">Chưa chạy AI cho project này. Bấm Tự phân loại: AI so thumbnail với mô tả từng bin (và học từ nhãn bạn xếp khi đủ ' + info.min_labels + ' clip), chạy trên máy này, mất vài giây đến vài phút.</span>';
    aiButtons([]); return;
  }
  aiScoresSync();
  const acts = [];
  let body = "";
  if (!c) body = '<span class="ai-msg">Chọn một clip để xem gợi ý.</span>';
  else if (c.label) body = `<span class="ai-msg">Clip đã xếp vào "${esc(c.label)}"${c.label_by === "ai_auto" ? " (AI xếp, chưa phải bạn xếp)" : ""}, không gợi ý. (Bấm 0 để bỏ nhãn.)</span>`;
  else {
    const r = await aiForCur();
    if (mySeq !== AI.seq) return;
    if (r && r.skipped) { body = '<span class="ai-msg">Đã bỏ qua gợi ý cho clip này.</span>'; acts.push(["aiUnskip", "Hiện lại gợi ý"]); }
    else if (!r) body = '<span class="ai-msg">Clip này chưa có gợi ý (chưa có thumbnail/vector, hoặc chưa thuộc giai đoạn nào). Bấm Tự phân loại để cập nhật.</span>';
    else {
      $("aiSrc").textContent = aiSrcText(r.src);
      body = r.top.map((t, i) => `<div class="ai-row${i === 0 ? " first" : ""}"><span class="nm" title="${esc(t.bin)}">${esc(t.bin)}</span><span class="ai-bar"><i style="width:${aiPct(t.score)}%"></i></span><span class="pc">${aiPct(t.score)}%</span><button class="btn" data-ai-take="${esc(t.bin)}">Nhận</button></div>`).join("");
      acts.push(["aiSkip", "Bỏ qua (X)"]);
    }
  }
  $("aiBody").innerHTML = body;
  aiButtons(acts);
}

async function aiGroupLoad() {
  const uids = items.map((c) => c.uid);
  AI.group = await api().ai_for(uids);
  for (const u in AI.group) if (AI.group[u].skipped) delete AI.group[u];
  patchGrid();
}

async function aiTake(pairs) {                                  // pairs: [[uid, bin]] -> chỉ gán nhãn trong kế hoạch Trợ lý
  if (!pairs.length) return;
  keepCur = cur;
  const st = await api().ai_accept(pairs);
  if (st.error) { keepCur = null; return status(st.error, "warn"); }
  AI.cache = {};
  setState(st);
  keepCur = null;
  if (AI.group) { for (const [u] of pairs) delete AI.group[u]; patchGrid(); }
  status(`Đã nhận ${st.ai_accepted} gợi ý (chỉ gán nhãn trong Trợ lý; chưa chuyển gì trong DaVinci).` + (st.ai_bad ? ` ${st.ai_bad} clip bị bỏ qua vì bin không thuộc giai đoạn.` : ""));
  if (pairs.length === 1 && cur < items.length - 1) moveCur(cur + 1);
  aiBoxRender();
}

/* ---- nút Tự phân loại (gộp hai nút cũ): chạy AI nếu cần, rồi gán nhãn cả nhóm theo ngưỡng. KHÔNG chuyển clip trong DaVinci ---- */
async function aiRunGroup() {
  if (AI.busy) return;
  if (!items.length) return status("Nhóm này chưa có clip.", "warn");
  const uids = items.map((c) => c.uid), info = await aiRefreshInfo();
  if (info && info.running) return;
  AI.busy = true; aiRunPaint(info);
  try {
    if (info && info.can_run) {                                // AI nhúng ảnh nền (làm tiếp phần chưa có), xong thì tự gán nhãn cho nhóm này
      const r = await api().ai_run();
      if (r.error) { if (!info.has_data) return status(r.error, "warn"); }
      else { AI.info = r; AI.cache = {}; AI.after = uids; await aiRefreshInfo(); return; }
    }
    if (!info || !info.has_data) return status("Chưa có dữ liệu AI và chưa chạy được AI trên máy này (xem docs/adr/0020).", "warn");
    await aiApplyGroup(uids);
  } finally { AI.busy = false; aiBoxRender(); }
}
async function aiApplyGroup(uids) {
  AI.busy = true;
  try {
    const r = await api().ai_auto_apply($("aiThr").value, uids);
    if (r.error) return status(r.error, "warn");
    AI.cache = {}; AI.ranKey = groupKey(); AI.scoreSig = "";
    setState(r); await aiAutoRefresh(); await aiGroupLoad();
    const x = r.ai_auto;
    status(`Tự phân loại xong: ${x.n} clip được xếp (hạng 1 từ ${Math.round(x.threshold * 100)}%), ${x.below} clip chờ bạn duyệt. Chỉ nhãn trong Trợ lý (dấu "AI xếp"); chưa chuyển gì trong DaVinci. Bấm Hoàn tác AI xếp để bỏ.`, x.n ? "ok" : "info");
  } finally { AI.busy = false; await aiScoresSync(); aiBoxRender(); }
}

$("aiBox").addEventListener("click", async (e) => {
  const t = e.target.closest("button"); if (!t || t.disabled) return;
  const c = items[cur];
  if (t.dataset.aiTake && c) return aiTake([[c.uid, t.dataset.aiTake]]);
  if (t.id === "aiRun") return aiRunGroup();
  if (t.id === "aiStop") { AI.after = null; AI.info = await api().ai_stop(); status("Đã gửi lệnh dừng; AI dừng sau lô ảnh hiện tại. Bấm Tự phân loại để làm tiếp."); return aiBoxRender(); }
  if (t.id === "aiSkip" && c) { await api().ai_skip([c.uid]); AI.cache = {}; if (AI.group) delete AI.group[c.uid]; patchGrid(); return aiBoxRender(); }
  if (t.id === "aiUnskip" && c) { await api().ai_skip([c.uid], true); AI.cache = {}; return aiBoxRender(); }
});

document.addEventListener("keydown", (e) => {                   // A nhận hạng 1, X bỏ qua; chỉ ở Bước 2, không khi đang gõ chữ
  if (page !== 2 || e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
  if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable) return;
  if (e.code !== "KeyA" && e.code !== "KeyX") return;
  const c = items[cur]; if (!c || c.label || !AI.info || !AI.info.has_data || AI.info.running) return;
  e.preventDefault();
  if (e.code === "KeyX") { const b = $("aiSkip"); if (b) b.click(); return; }
  const first = document.querySelector("#aiBody [data-ai-take]"); if (first) first.click();
});

/* ---- Việc 3 (ADR-0023): AI tự xếp theo ngưỡng. Chỉ gán nhãn trong Trợ lý (dấu "AI xếp"), có Hoàn tác, không tính vào dữ liệu AI học, không đụng DaVinci ---- */
AI.auto = null;
async function aiAutoRefresh() { try { AI.auto = await api().ai_auto_info(); } catch (e) { AI.auto = null; } return AI.auto; }
function aiAutoPaint(info) {
  const box = $("aiAuto"); if (!box) return;
  const show = !!(info && info.has_data && !info.running);
  if (show) aiHistPaint();
  box.classList.toggle("hidden", !show);
  if (!show) return;
  const au = AI.auto;
  if (!au) { aiAutoRefresh().then(() => { if (AI.auto) aiAutoPaint(AI.info); }); return; }
  if (!AI.thrPending && document.activeElement !== $("aiThr") && document.activeElement !== $("aiThrR")) { $("aiThr").value = Math.round(au.threshold * 100); $("aiThrR").value = Math.round(au.threshold * 100); }
  $("aiAutoAfter").checked = !!au.after_run;
  $("aiAutoUndo").classList.toggle("hidden", !au.batches);
  $("aiAutoUndo").textContent = "Hoàn tác AI xếp (" + au.last_n + ")";
}
async function aiAutoRun() {
  const r = await api().ai_auto_run($("aiThr").value);
  if (r.error) return status(r.error, "warn");
  AI.cache = {}; setState(r); await aiAutoRefresh(); aiBoxRender();
  const x = r.ai_auto;
  status(`AI đã xếp ${x.n} clip (hạng 1 từ ${Math.round(x.threshold * 100)}%); ${x.below} clip dưới ngưỡng để anh duyệt` + (x.skipped ? `, ${x.skipped} clip đã bỏ qua` : "") +
    `. Chỉ nhãn trong Trợ lý (dấu "AI xếp"); chưa chuyển gì trong DaVinci. Bấm Hoàn tác AI xếp để bỏ.`, x.n ? "ok" : "info");
}
/* Ngưỡng: kéo thanh hoặc gõ số là ÁP DỤNG NGAY (tính từ điểm đã có, không gọi AI chạy lại). Đã chạy Tự phân loại ở nhóm này thì nhãn AI xếp đổi theo luôn. */
function aiThrSet(v, fromRange) {
  v = Math.round(+v); if (!(v >= 1)) return; v = Math.min(100, v);
  $("aiThr").value = v; $("aiThrR").value = v;
  aiHistPaint(); patchGrid();
  AI.thrPending = true;                                         // chưa lưu xong thì các lần vẽ lại khác không được ghi đè số bạn vừa kéo
  clearTimeout(AI.thrTimer);
  AI.thrTimer = setTimeout(aiThrApply, fromRange ? 180 : 0);
}
async function aiThrApply() {
  try {
    const v = aiThrNow(), live = aiLive() && AI.info && AI.info.has_data && !AI.busy;
    if (!live) { const r = await api().ai_auto_set(v); if (r && !r.error) AI.auto = r; return; }   // chưa Tự phân loại nhóm này: chỉ nhớ ngưỡng
    const r = await api().ai_auto_apply(v, items.map((c) => c.uid));
    if (r.error) { status(r.error, "warn"); AI.thrPending = false; return aiAutoRefresh().then(() => aiBoxRender()); }
    AI.cache = {}; AI.scoreSig = ""; if (AI.auto) AI.auto.threshold = r.ai_auto.threshold; setState(r); await aiAutoRefresh();
    const x = r.ai_auto;
    status(`Ngưỡng ${v}%: ${x.n ? x.n + " clip mới được xếp" : "không thêm clip nào"}${x.released ? `, ${x.released} clip trả về chờ bạn duyệt` : ""}. Không chạy lại AI.`, "info");
  } finally { AI.thrPending = false; }
}
$("aiThr").addEventListener("input", () => aiThrSet($("aiThr").value, false));
$("aiThrR").addEventListener("input", () => aiThrSet($("aiThrR").value, true));
$("aiAutoAfter").addEventListener("change", async () => { AI.auto = await api().ai_auto_set(null, $("aiAutoAfter").checked); });
$("aiAutoUndo").addEventListener("click", async () => {
  const r = await api().ai_auto_undo();
  if (r.error) return status(r.error, "warn");
  AI.cache = {}; setState(r); await aiAutoRefresh(); aiBoxRender();
  const u = r.ai_auto_undo;
  status(`Đã hoàn tác AI xếp: bỏ nhãn ${u.undone} clip` + (u.kept ? `, giữ nguyên ${u.kept} clip anh đã đổi nhãn` : "") + ".", "ok");
});
