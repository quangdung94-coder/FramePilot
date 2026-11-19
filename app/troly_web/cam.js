/* Nhiều camera, trang 1 (ADR-0031): thẻ máy, đặt tên, máy chuẩn, chỉnh đồng hồ bằng một khoảnh khắc chung.
   Giao diện theo design/nhieu_camera/1_nhan_may.html. Chỉ đổi kế hoạch của Trợ lý, KHÔNG ghi gì vào DaVinci.
   Phụ thuộc app.js (S, $, esc, api, setState, status, fmt, pct, view). */
const CAMS_MAX = 4;
const CM = { sel: null, r: { uid: null, pos: 0, locked: false }, x: { uid: null, pos: 0, locked: false }, manual: false, calc: null,
  sigCards: "", sigClock: "", bad: {} };
const hms = (sec) => { const s = Math.abs(Math.round(sec)); return String(Math.floor(s / 3600) % 24).padStart(2, "0") + ":" + String(Math.floor(s % 3600 / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
const fmtOff = (sec) => (sec < 0 ? "-" : "+") + [Math.floor(Math.abs(sec) / 3600), Math.floor(Math.abs(sec) % 3600 / 60), Math.abs(sec) % 60].map((n) => String(Math.round(n)).padStart(2, "0")).join(":");
const camS = () => (S && S.cams) || null;
const camClips = (L) => (S ? S.clips : []).filter((c) => c.cam_l === L && c.raw_s != null).sort((a, b) => a.raw_s - b.raw_s);
const camCard = (L) => (camS() ? camS().cards.find((c) => c.letter === L) : null);

/* ---- hàng thời gian: mỗi máy một hàng (gọi từ renderTimeline) ---- */
function camRowsHtml() {
  const C = camS(), letters = C && C.cards.length ? C.cards.map((c) => c.letter) : ["A"];
  const rows = letters.map((L) => {
    let h = `<div class="dens-row ${L}"><span class="lab cam-chip ${L}" title="${esc(C && camCard(L) ? camCard(L).name : "Máy " + L)}">${L}</span>`;
    if (S) for (const c of S.clips) {
      if (c.m0 == null || c.m1 < view[0] || c.m0 > view[1]) continue;
      if ((c.cam_l || (C && C.cards.length ? "" : "A")) !== L) continue;
      h += `<i style="left:${pct(c.m0)}"></i>`;
    }
    return h + "</div>";
  });
  if (C && C.unassigned.length) {
    let h = `<div class="dens-row"><span class="lab cam-chip" title="Chưa gán máy">?</span>`;
    for (const c of S.clips) if (!c.cam_l && c.m0 != null && c.m1 >= view[0] && c.m0 <= view[1]) h += `<i style="left:${pct(c.m0)};background:#888"></i>`;
    rows.push(h + "</div>");
  }
  let mom = "";
  if (CM.r.locked && CM.x.locked && CM.calc && CM.calc.ref_time != null && C && C.multi) {
    const m = CM.calc.ref_time / 60;
    if (m >= view[0] && m <= view[1]) mom = `<div class="moment" title="Khoảnh khắc đang dùng để chỉnh đồng hồ" style="left:${pct(m)}"></div>`;
  }
  return rows.join("") + mom;
}

/* ---- chip máy cạnh tên bin (gọi từ renderBinGrid) ---- */
function camChipsOfStage(i) {
  const C = camS(); if (!C || !S) return "";
  const set = new Set(S.clips.filter((c) => c.stage === i && c.cam_l).map((c) => c.cam_l));
  return C.cards.filter((c) => set.has(c.letter)).map((c) => `<span class="cam-chip ${c.letter}" title="${esc(c.name)}">${c.letter}</span>`).join("");
}

/* ---- vẽ cột trái, thẻ máy, nhóm cần xem, cột phải ---- */
function renderCams() {
  const C = camS(), has = !!(S && S.n);
  const multi = !!(C && C.multi);
  $("page1").classList.toggle("one", !multi);
  $("clockCol").classList.toggle("hidden", !has);
  $("camSec").classList.toggle("hidden", !has);
  $("tlSub").textContent = has ? "Mỗi hàng là một máy, mỗi vạch là một file, theo giờ chung" : "Mỗi vạch là một file quay, đặt đúng theo giờ máy quay ghi lại";
  if (!has || !C) return;
  const sigCards = JSON.stringify([C.cards, C.groups, C.ref, C.unassigned]);
  if (sigCards !== CM.sigCards) { CM.sigCards = sigCards; buildCards(C); buildSync(C); buildGroups(C); }
  const sigClock = JSON.stringify([C.ref, C.cards.map((c) => c.letter + c.name)]);
  if (multi && sigClock !== CM.sigClock) { CM.sigClock = sigClock; buildClock(C); }
}

function tagOf(c, one) {
  if (one) return '<span class="off-tag set">Máy duy nhất</span>';
  if (c.is_ref) return '<span class="off-tag set">Máy chuẩn</span>';
  if (c.set) return `<span class="off-tag set">Đã chỉnh ${c.shift_txt}</span>`;
  return '<span class="off-tag warn">Chưa chỉnh giờ</span>';
}
function buildCards(C) {
  const one = !C.multi;
  $("camCards").innerHTML = C.cards.map((c) => `<div class="cam-card ${c.letter}" id="card${c.letter}">
    <div class="top1"><span class="cam-chip ${c.letter}">${c.letter}</span><input class="inp" data-cam="${c.letter}" value="${esc(c.name)}" maxlength="20" aria-label="Tên máy ${c.letter}"></div>
    <span class="nmsg" id="nmsg${c.letter}"></span>
    <div class="meta"><b>${esc(c.model)}</b>${c.serial ? " · " + esc(c.serial) : ""}<br>${c.n} file${c.span ? " · " + c.span : ""}</div>
    ${one ? "" : `<label class="ref multi"><input type="radio" name="camref" value="${c.letter}" ${c.is_ref ? "checked" : ""}>Chuẩn giờ</label>`}
    <div>${tagOf(c, one)}</div></div>`).join("");
  if (C.unassigned.length && !C.cards.length) $("camCards").innerHTML = '<div class="dim12">Chưa gán máy nào: xem bảng nhóm máy bên dưới.</div>';
}
function camNameCheck(L, v) {
  const C = camS(); v = v.trim();
  if (!v) return "Tên máy không được để trống.";
  if (C.cards.some((c) => c.letter !== L && c.name.toLowerCase() === v.toLowerCase())) return "Trùng tên với máy khác. Mỗi máy một tên.";
  return "";
}
function camNameShow(L, err) {
  const inp = document.querySelector(`#camCards input[data-cam="${L}"]`), m = $("nmsg" + L);
  if (inp) inp.classList.toggle("bad", !!err);
  if (m) { m.textContent = err; m.classList.toggle("show", !!err); }
  CM.bad[L] = !!err;
  updateApplyBtn();
}
$("camCards").addEventListener("input", (e) => {
  const L = e.target.dataset && e.target.dataset.cam; if (!L) return;
  camNameShow(L, camNameCheck(L, e.target.value));
});
async function camNameCommit(e) {
  const L = e.target.dataset && e.target.dataset.cam; if (!L) return;
  const err = camNameCheck(L, e.target.value);
  if (err) { const c = camCard(L); e.target.value = c ? c.name : ""; camNameShow(L, ""); return; }
  if (camCard(L) && camCard(L).name === e.target.value.trim()) return;
  const r = await api().cams_rename(L, e.target.value);
  if (r.error) { camNameShow(L, r.error); return; }
  camNameShow(L, ""); setState(r);
}
$("camCards").addEventListener("change", (e) => {
  if (e.target.name === "camref") { api().cams_set_ref(e.target.value).then((r) => { if (r.error) return status(r.error, "warn"); CM.sel = null; resetPair(); setState(r); if (r.cam_msg) status(r.cam_msg.text, "info"); }); return; }
  camNameCommit(e);
});
$("camCards").addEventListener("keydown", (e) => { if (e.code === "Enter" && e.target.dataset && e.target.dataset.cam) e.target.blur(); });

function buildSync(C) {
  const box = $("syncBox");
  box.innerHTML = `<span style="display:flex;justify-content:space-between;align-items:center"><b>Timeline sau khi sync</b><span class="pending-tag">ghi chú, chưa làm</span></span>` +
    C.cards.map((c, i) => `<div class="row"><span>V${i + 1} · A${i + 1}</span><span>${esc(c.name)}${i < 2 ? " (máy " + (i + 1) + ")" : ""}</span></div>`).join("") +
    `<div class="row"><span>dưới cùng</span><span>Nhạc, Tascam</span></div>` +
    `<span class="dim12" style="line-height:1.5">Tối đa ${CAMS_MAX} máy. Source máy quay xếp trên, nhạc và Tascam luôn đẩy xuống dưới. Chia khung xem 2/4 máy làm trong DaVinci.</span>`;
}

/* nhóm máy nhập nhằng / chưa gán: để người dựng gán tay (không có trong demo vì demo luôn nhận đúng) */
function buildGroups(C) {
  const need = C.ambiguous.length || C.unassigned.length || C.groups.length > C.cards.length;
  const box = $("camGroups");
  if (!need) { box.innerHTML = ""; return; }
  const nAmb = C.ambiguous.length + C.unassigned.length;
  box.innerHTML = `<details class="rules-box grp-box" id="grpBox"${CM.grpOpen || C.unassigned.length ? " open" : ""}><summary><b>Nhóm máy Trợ lý đọc được${nAmb ? ` · ${nAmb} chỗ cần bạn xem` : ""}</b> <span class="dim12">bấm để xem và gán tay</span></summary>` + C.groups.map((g) => {
    const label = [g.maker, g.model].filter(Boolean).join(" ") || g.key;
    return `<div class="grp-row${g.ambiguous ? " amb" : ""}"><span class="t"><b>${esc(label)}</b>${g.serial ? " · " + esc(g.serial) : ""} · ${g.n} file${g.source === "name" ? " · theo tên file" : ""}${g.ambiguous ? `<br><em>${esc(g.ambiguous)}</em>` : ""}</span>
      <select class="sel" data-grp="${esc(g.key)}" aria-label="Gán nhóm máy vào máy"><option value="">Chưa gán</option>${"ABCD".split("").map((L) => `<option value="${L}"${g.letter === L ? " selected" : ""}>Máy ${L}${camCard(L) ? " (" + esc(camCard(L).name) + ")" : ""}</option>`).join("")}</select></div>`;
  }).join("") + `<span class="dim12">Hai nhóm gán cùng một chữ thì gộp thành một máy.${C.unassigned.length ? " Còn " + C.unassigned.length + " nhóm chưa gán: clip của nhóm đó không cộng độ lệch." : ""}</span></details>`;
  $("grpBox").addEventListener("toggle", (e) => { CM.grpOpen = e.target.open; });
}
$("camGroups").addEventListener("change", (e) => {
  const key = e.target.dataset && e.target.dataset.grp; if (key === undefined) return;
  api().cams_assign(key, e.target.value).then((r) => { if (r.error) return status(r.error, "warn"); CM.sel = null; CM.sigClock = ""; setState(r); });
});

/* ---- cột phải: chỉnh đồng hồ ---- */
function clipLabel(c) { return `${hms(c.raw_s)} · ${c.name}`; }
function pickDefaults(C) {
  const ref = C.ref, others = C.cards.filter((c) => c.letter !== ref).map((c) => c.letter);
  if (!others.includes(CM.sel)) CM.sel = (others.find((L) => !camCard(L).set) || others[0]) || null;
  const rc = camClips(ref), xc = camClips(CM.sel);
  const x = xc.length ? xc[Math.floor(xc.length / 2)] : null;
  const r = rc.length ? (x ? rc.reduce((b, c) => (Math.abs(c.raw_s - x.raw_s) < Math.abs(b.raw_s - x.raw_s) ? c : b), rc[0]) : rc[Math.floor(rc.length / 2)]) : null;
  CM.r = { uid: r ? r.uid : null, pos: 0, locked: false };
  CM.x = { uid: x ? x.uid : null, pos: 0, locked: false };
  CM.manual = false; CM.calc = null;
}
function resetPair() { CM.sigClock = ""; CM.sel = null; }
function buildClock(C) {
  const box = $("clockMulti");
  pickDefaults(C);
  const others = C.cards.filter((c) => c.letter !== C.ref);
  box.innerHTML = `<div class="row-between baseline"><h2>Chỉnh đồng hồ máy</h2><span class="dim12">giờ chung = giờ ${esc(camCard(C.ref).name)}</span></div>
    <span class="dim12" style="line-height:1.5">Mỗi máy đặt giờ một kiểu. Lướt tới <b style="color:var(--dim2)">cùng một khoảnh khắc</b> (tiếng pháo, cô dâu bước ra) trên hai máy rồi bấm Lấy khung này.</span>
    <div class="seg small" id="camSeg" style="align-self:flex-start">${others.map((c) => `<button data-c="${c.letter}" class="${c.letter === CM.sel ? "seg-on" : "seg-off"}">Chỉnh ${esc(c.name)}</button>`).join("")}</div>
    <div class="pair">${pairBox("R", C.ref)}${pairBox("X", CM.sel)}</div>
    <div class="diff-box">
      <span class="lbl" style="color:var(--link)">Độ lệch tính được</span>
      <span class="big" id="bigDiff">…</span><span class="eq" id="eqDiff"></span>
      <div class="off-in"><span>Hoặc gõ tay</span><input class="inp center" id="offInp" placeholder="+01:12:14" aria-label="Độ lệch giờ:phút:giây"><span>±giờ:phút:giây</span></div>
      <div class="msg" id="offMsg"></div>
      <div class="inline8"><button class="btn-accent btn-44 flex1" id="applyBtn">Áp dụng</button><button class="btn btn-44" id="resetOne">Về 0</button></div>
    </div>
    <div class="rules-box"><b>Quy định</b><ul>
      <li>Đổi máy chuẩn giờ: mọi độ lệch tính lại theo máy mới.</li>
      <li>Tên máy không trống, không trùng, dùng chung 3 trang.</li>
      <li>Khoảnh khắc nằm trong clip; sau khi chỉnh hai clip phải chồng nhau.</li>
      <li>Độ lệch tối đa ±12 giờ, trên 3 giờ có cảnh báo.</li></ul></div>`;
  openPair("R"); openPair("X"); refreshClock();
}
function pairBox(side, L) {
  const clips = camClips(L), st = side === "R" ? CM.r : CM.x, c = (S.clips.find((o) => o.uid === st.uid)) || {};
  const dur = Math.max(1, Math.floor(c.dur || 1));
  return `<div class="pair-box" data-side="${side}">
    <div class="pv" id="pv${side}" style="background:linear-gradient(135deg,#2A2A30,#18181B)"><span class="cam-chip ${L}">${L}</span><span class="tc" id="tc${side}">--:--:--</span></div>
    <div class="nm"><b style="color:var(--text)">${esc(camCard(L).name)}</b>${side === "R" ? " · chuẩn" : ""}<br>
      <select class="sel clip-sel" id="cs${side}" aria-label="Chọn clip">${clips.length ? clips.map((o) => `<option value="${o.uid}"${o.uid === st.uid ? " selected" : ""}>${esc(clipLabel(o))}</option>`).join("") : "<option>Máy này chưa có clip</option>"}</select></div>
    <input class="scrub" id="sc${side}" type="range" min="0" max="${dur}" step="0.5" value="${st.pos}" aria-label="Lướt ${side === "R" ? "máy chuẩn" : "máy cần chỉnh"}">
    <button class="btn lock-btn" id="lk${side}">Lấy khung này</button></div>`;
}
async function openPair(side) {
  const st = side === "R" ? CM.r : CM.x, pv = $("pv" + side); if (!pv || !st.uid) return;
  pv.querySelectorAll("video,img,.pv-note").forEach((n) => n.remove());
  const uid = st.uid, r = await api().play_info(uid);
  if ((side === "R" ? CM.r : CM.x).uid !== uid || !$("pv" + side)) return;
  if (r && r.url) {
    const v = document.createElement("video");
    v.muted = true; v.preload = "auto"; v.className = "pv-vid"; v.src = r.url; v.addEventListener("loadedmetadata", () => { v.currentTime = st.pos; });
    pv.insertBefore(v, pv.firstChild);
  } else {
    const note = document.createElement("span"); note.className = "pv-note"; note.textContent = (r && r.error) || "Chưa có hình";
    pv.appendChild(note);
    api().big(uid).then((b) => { if (b && b.src && $("pv" + side) && (side === "R" ? CM.r : CM.x).uid === uid) { const im = document.createElement("img"); im.className = "pv-vid"; im.src = b.src; pv.insertBefore(im, pv.firstChild); } });
  }
}
function setMsg(kind, text) { const e = $("offMsg"); if (!e) return; e.className = "msg" + (text ? " show " + kind : ""); e.textContent = text || ""; }
function updateApplyBtn() {
  const b = $("applyBtn"); if (!b || !CM.sel) return;
  const c = camCard(CM.sel);
  b.textContent = "Áp dụng cho " + (c ? c.name : "");
  b.disabled = Object.values(CM.bad).some(Boolean) || (!(CM.r.locked && CM.x.locked) && !CM.manual);
}
async function refreshClock() {
  const C = camS(); if (!C || !$("clockMulti").firstChild || !CM.sel) return;
  const both = CM.r.locked && CM.x.locked, inp = $("offInp");
  for (const [k, side] of [["r", "R"], ["x", "X"]]) {
    const st = CM[k], c = S.clips.find((o) => o.uid === st.uid);
    $("tc" + side).textContent = c ? hms(c.raw_s + st.pos) : "--:--:--";
    const b = $("lk" + side); b.classList.toggle("locked", st.locked); b.textContent = st.locked ? "Đã lấy khung ✓" : "Lấy khung này";
  }
  if (both) {
    const m = await api().cams_moment(CM.sel, CM.r.uid, CM.r.pos, CM.x.uid, CM.x.pos);
    if (!(CM.r.locked && CM.x.locked)) return;
    if (m.error) { CM.calc = null; $("bigDiff").textContent = "Chưa tính được"; $("eqDiff").textContent = m.error; }
    else {
      CM.calc = m;
      const nr = camCard(C.ref).name, nx = camCard(CM.sel).name;
      $("bigDiff").textContent = `${nx} ${m.offset >= 0 ? "chậm" : "nhanh"} hơn ${nr} ${hms(m.offset)}`;
      $("eqDiff").textContent = `${hms(m.ref_time)} (${nr}) − ${hms(m.cam_time)} (${nx}) = ${m.text}`;
      if (!CM.manual) inp.value = m.text;
    }
  } else { CM.calc = null; $("bigDiff").textContent = "Chưa đủ hai khung"; $("eqDiff").textContent = "Lướt tới cùng một khoảnh khắc ở cả hai máy rồi bấm Lấy khung này ở mỗi bên."; }
  updateApplyBtn(); if (page === 1) renderTimeline();
}
function clipOf(uid) { return S.clips.find((o) => o.uid === uid); }
$("clockMulti").addEventListener("input", (e) => {
  const id = e.target.id;
  if (id === "scR" || id === "scX") {
    const k = id === "scR" ? "r" : "x", st = CM[k], v = $("pv" + id.slice(2)).querySelector("video");
    st.pos = +e.target.value; st.locked = false; CM.manual = false; setMsg("", "");
    if (v) v.currentTime = st.pos;
    refreshClock();
  } else if (id === "offInp") { CM.manual = true; setMsg("", ""); e.target.classList.remove("bad"); updateApplyBtn(); }
});
$("clockMulti").addEventListener("change", (e) => {
  const id = e.target.id;
  if (id === "csR" || id === "csX") {
    const k = id === "csR" ? "r" : "x", side = id.slice(2), c = clipOf(e.target.value);
    CM[k] = { uid: e.target.value, pos: 0, locked: false }; CM.manual = false;
    const sc = $("sc" + side); sc.max = Math.max(1, Math.floor((c && c.dur) || 1)); sc.value = 0;
    openPair(side); refreshClock();
  }
});
$("clockMulti").addEventListener("click", async (e) => {
  const t = e.target.closest("button"); if (!t) return;
  if (t.parentElement && t.parentElement.id === "camSeg") { CM.sel = t.dataset.c; buildClock(camS()); return; }
  if (t.id === "lkR" || t.id === "lkX") { const st = t.id === "lkR" ? CM.r : CM.x; st.locked = true; CM.manual = false; refreshClock(); return; }
  if (t.id === "resetOne") { const r = await api().cams_reset(CM.sel); if (r.error) return setMsg("bad", r.error); setState(r); $("offInp").value = ""; CM.manual = false; setMsg("warn", r.cam_msg ? r.cam_msg.text : ""); refreshClock(); return; }
  if (t.id === "applyBtn") {
    let r;
    if (CM.manual) r = await api().cams_apply(CM.sel, $("offInp").value);
    else r = await api().cams_apply_moment(CM.sel, CM.r.uid, CM.r.pos, CM.x.uid, CM.x.pos);
    if (r.error) { setMsg("bad", r.error); $("offInp").classList.add("bad"); return; }
    $("offInp").classList.remove("bad"); setState(r);
    if (r.cam_msg) setMsg(r.cam_msg.kind, r.cam_msg.text);
  }
});
$("resetAll").addEventListener("click", async () => {
  const r = await api().cams_reset(null); if (r.error) return status(r.error, "warn");
  CM.manual = false; CM.sigClock = ""; setState(r); status(r.cam_msg ? r.cam_msg.text : "Đã đặt lại độ lệch.", "info");
});
