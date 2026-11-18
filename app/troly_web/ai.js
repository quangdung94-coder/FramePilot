/* Bước 2: Gợi ý AI (ADR-0022; demo design/6_ai_goi_y). CHỈ GỢI Ý: "Nhận" chỉ gán nhãn trong Trợ lý (api().ai_accept), không gọi DaVinci.
   Chuyển clip vào bin trong DaVinci vẫn là nút "Áp dụng vào Media Pool" (có nhật ký + Hoàn tác). Phím đọc bằng event.code. */
const AI = { info: null, cache: {}, group: null, poll: null, wasRunning: false, seq: 0 };
const AI_MIN_GROUP = 0.7;                                   // ngưỡng "Nhận hạng 1 cho clip có điểm từ 70%"

function aiPct(x) { return Math.round(x * 100); }
function aiSrcText(src) { return src === "nhan" ? "theo nhãn anh xếp" : "theo mô tả"; }
function aiKey(uid) {                                          // khóa để vẽ lại thẻ khi gợi ý đổi
  const g = AI.group && AI.group[uid]; return g && g.top ? g.top[0].bin + aiPct(g.top[0].score) : "";
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
    if (AI.group) await aiGroupLoad();
    status(AI.info.has_data ? "AI đã chạy xong. Có gợi ý cho clip chưa xếp." : "AI đã dừng. Bấm Chạy AI để làm tiếp.");
    if (AI.info.has_data && AI.auto && AI.auto.after_run) await aiAutoRun();
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

async function aiBoxRender() {
  const box = $("aiBox"); if (!box || page !== 2) return;
  const mySeq = ++AI.seq;
  const info = AI.info || await aiRefreshInfo();
  if (mySeq !== AI.seq) return;
  const c = items[cur];
  aiAutoPaint(info);
  $("aiSrc").textContent = info && info.has_data ? aiSrcText(info.mode) : "";
  if (!info) { $("aiBody").innerHTML = '<span class="ai-msg">Chưa đọc được trạng thái AI.</span>'; aiButtons([]); return; }
  if (info.running) {
    $("aiBody").innerHTML = `<span class="ai-msg">AI đang chạy nền (không ảnh hưởng DaVinci)…<br>${esc(info.log || "")}</span>`;
    aiButtons([["aiStop", "Dừng"]]); return;
  }
  if (!info.has_data) {
    $("aiBody").innerHTML = '<span class="ai-msg">Chưa chạy AI cho project này. AI so thumbnail với mô tả từng bin (và học từ nhãn anh xếp khi đủ ' + info.min_labels + ' clip). Chạy trên máy này, mất vài giây đến vài phút.</span>';
    aiButtons([["aiRun", "Chạy AI (nền)", !info.can_run, info.can_run ? "" : "Chưa có venv AI hoặc model, xem ADR-0020"]]); return;
  }
  const grp = AI.group ? Object.values(AI.group).filter((g) => g.top) : null;
  const acts = [];
  let body = "";
  if (!c) body = '<span class="ai-msg">Chọn một clip để xem gợi ý.</span>';
  else if (c.label) body = `<span class="ai-msg">Clip đã xếp vào "${esc(c.label)}", không gợi ý. (Bấm 0 để bỏ nhãn.)</span>`;
  else {
    const r = await aiForCur();
    if (mySeq !== AI.seq) return;
    if (r && r.skipped) { body = '<span class="ai-msg">Đã bỏ qua gợi ý cho clip này.</span>'; acts.push(["aiUnskip", "Hiện lại gợi ý"]); }
    else if (!r) body = '<span class="ai-msg">Clip này chưa có gợi ý (chưa có thumbnail/vector, hoặc chưa thuộc giai đoạn nào). Bấm "Chạy lại AI" để cập nhật.</span>';
    else {
      $("aiSrc").textContent = aiSrcText(r.src);
      body = r.top.map((t, i) => `<div class="ai-row${i === 0 ? " first" : ""}"><span class="nm" title="${esc(t.bin)}">${esc(t.bin)}</span><span class="ai-bar"><i style="width:${aiPct(t.score)}%"></i></span><span class="pc">${aiPct(t.score)}%</span><button class="btn" data-ai-take="${esc(t.bin)}">Nhận</button></div>`).join("");
      acts.push(["aiSkip", "Bỏ qua (X)"]);
    }
  }
  if (grp) {
    const n = grp.filter((g) => g.top[0].score >= AI_MIN_GROUP).length;
    body += `<span class="ai-msg">Nhóm đang xem: ${grp.length} clip có gợi ý (thẻ viền đứt trên lưới), ${n} clip từ ${aiPct(AI_MIN_GROUP)}%.</span>`;
    acts.push(["aiTakeAll", `Nhận hạng 1 cho ${n} clip`, !n], ["aiGroupOff", "Tắt gợi ý nhóm"]);
  } else acts.push(["aiGroup", "Gợi ý cho cả nhóm"]);
  acts.push(["aiRun", "Chạy lại AI", !info.can_run]);
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

$("aiBox").addEventListener("click", async (e) => {
  const t = e.target.closest("button"); if (!t || t.disabled) return;
  const c = items[cur];
  if (t.dataset.aiTake && c) return aiTake([[c.uid, t.dataset.aiTake]]);
  if (t.id === "aiRun") { const r = await api().ai_run(); if (r.error) return status(r.error, "warn"); AI.info = r; AI.cache = {}; await aiRefreshInfo(); return aiBoxRender(); }
  if (t.id === "aiStop") { AI.info = await api().ai_stop(); status("Đã gửi lệnh dừng; AI dừng sau lô ảnh hiện tại. Chạy lại để làm tiếp."); return aiBoxRender(); }
  if (t.id === "aiSkip" && c) { await api().ai_skip([c.uid]); AI.cache = {}; if (AI.group) delete AI.group[c.uid]; patchGrid(); return aiBoxRender(); }
  if (t.id === "aiUnskip" && c) { await api().ai_skip([c.uid], true); AI.cache = {}; return aiBoxRender(); }
  if (t.id === "aiGroup") { await aiGroupLoad(); return aiBoxRender(); }
  if (t.id === "aiGroupOff") { AI.group = null; patchGrid(); return aiBoxRender(); }
  if (t.id === "aiTakeAll" && AI.group) {
    const pairs = items.filter((x) => AI.group[x.uid] && AI.group[x.uid].top && AI.group[x.uid].top[0].score >= AI_MIN_GROUP).map((x) => [x.uid, AI.group[x.uid].top[0].bin]);
    const ok = await ask("Nhận gợi ý AI cho cả nhóm", `Gán nhãn hạng 1 của AI cho <b>${pairs.length}</b> clip (điểm từ ${aiPct(AI_MIN_GROUP)}%). Chỉ ghi nhãn trong Trợ lý; chưa chuyển gì trong DaVinci, anh vẫn bấm "Áp dụng vào Media Pool" khi muốn. Bỏ nhãn từng clip bằng phím 0.`, "Nhận " + pairs.length + " clip");
    if (ok) aiTake(pairs);
  }
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
  box.classList.toggle("hidden", !show);
  if (!show) return;
  const au = AI.auto;
  if (!au) { aiAutoRefresh().then(() => { if (AI.auto) aiAutoPaint(AI.info); }); return; }
  if (document.activeElement !== $("aiThr")) $("aiThr").value = Math.round(au.threshold * 100);
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
$("aiThr").addEventListener("change", async () => {
  const r = await api().ai_auto_set($("aiThr").value);
  if (r.error) { status(r.error, "warn"); await aiAutoRefresh(); return aiBoxRender(); }
  AI.auto = r; aiBoxRender();
});
$("aiAutoAfter").addEventListener("change", async () => { AI.auto = await api().ai_auto_set(null, $("aiAutoAfter").checked); });
$("aiAutoRun").addEventListener("click", aiAutoRun);
$("aiAutoUndo").addEventListener("click", async () => {
  const r = await api().ai_auto_undo();
  if (r.error) return status(r.error, "warn");
  AI.cache = {}; setState(r); await aiAutoRefresh(); aiBoxRender();
  const u = r.ai_auto_undo;
  status(`Đã hoàn tác AI xếp: bỏ nhãn ${u.undone} clip` + (u.kept ? `, giữ nguyên ${u.kept} clip anh đã đổi nhãn` : "") + ".", "ok");
});
