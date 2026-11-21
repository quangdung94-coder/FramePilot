/* multicam.js - Nhiều camera Trang 2 (lọc máy + làn ngang) và Trang 3 (Các máy khác lúc này + gợi ý theo giờ chung).
   Bám demo design/nhieu_camera/ (2_bin_nhieu_may, 2b_bin_lan_ngang, 3_inout_nhieu_may). Tự ẩn khi chỉ có 1 máy. */
"use strict";

(function initMulticam() {
  let mcCam = "all";       // "all" hoặc letter A/B/C/D
  let mcLaneMode = false;  // false = lưới, true = làn ngang theo máy
  let mcSyncSug = false;   // công tắc gợi ý In/Out theo giờ chung (mặc định TẮT)

  const CAM_COLORS = { A: "#4FC1A6", B: "#A78BFA", C: "#F472B6", D: "#FBBF24" };

  function machines() {
    return (window.S && Array.isArray(S.machines) && S.machines.length > 1) ? S.machines : [];
  }

  function renderPage2Mc() {
    const bar = $("mcBar2"), lanes = $("mcLanes2"), gridScroll = $("gridScroll");
    if (!bar || !lanes || !gridScroll) return;
    const ms = machines();
    if (!ms.length) {
      bar.classList.add("hidden");
      lanes.classList.add("hidden");
      gridScroll.classList.remove("hidden");
      return;
    }
    bar.classList.remove("hidden");
    const pills = [
      `<button class="mc-pill${mcCam === "all" ? " on" : ""}" data-cam="all">Tất cả máy</button>`,
      ...ms.map((m) => `<button class="mc-pill${mcCam === m.letter ? " on" : ""}" data-cam="${esc(m.letter)}"><i class="cam-chip" style="background:${m.color || CAM_COLORS[m.letter] || "#888"}">${esc(m.letter)}</i> ${esc(m.name || ("Máy " + m.letter))}</button>`),
      `<span class="flex1"></span>`,
      `<button class="mc-pill${!mcLaneMode ? " on" : ""}" id="mcModeGrid">Lưới</button>`,
      `<button class="mc-pill${mcLaneMode ? " on" : ""}" id="mcModeLane">Làn ngang</button>`,
    ].join("");
    bar.innerHTML = pills;

    bar.querySelectorAll("[data-cam]").forEach((b) => {
      b.onclick = () => { mcCam = b.dataset.cam; renderPage2Mc(); };
    });
    const mg = document.getElementById("mcModeGrid"), ml = document.getElementById("mcModeLane");
    if (mg) mg.onclick = () => { mcLaneMode = false; renderPage2Mc(); };
    if (ml) ml.onclick = () => { mcLaneMode = true; renderPage2Mc(); };

    // Lọc thẻ trên lưới theo máy nếu đang ở chế độ lưới
    document.querySelectorAll("#grid .card").forEach((el) => {
      const i = +el.dataset.i, c = items[i];
      const hide = (!mcLaneMode && mcCam !== "all" && c && c.mk !== mcCam);
      el.style.display = hide ? "none" : "";
    });

    if (!mcLaneMode) {
      lanes.classList.add("hidden");
      gridScroll.classList.remove("hidden");
      return;
    }

    // Chế độ làn ngang theo từng máy
    gridScroll.classList.add("hidden");
    lanes.classList.remove("hidden");
    const showMs = mcCam === "all" ? ms : ms.filter((m) => m.letter === mcCam);
    lanes.innerHTML = showMs.map((m) => {
      const mClips = items.map((c, idx) => ({ c, idx })).filter(({ c }) => c.mk === m.letter);
      const chips = mClips.length ? mClips.map(({ c, idx }) => {
        const cls = "mc-lclip" + (idx === cur ? " cur" : "") + (c.star ? " star" : "");
        return `<div class="${cls}" data-i="${idx}" title="${esc(c.name)} (${c.time})">
          <div class="mc-ltop"><b>${esc(c.name)}</b>${c.star ? " ★" : ""}</div>
          <div class="mc-lsub">${c.time} · ${(c.dur || 0).toFixed(1)}s ${c.label ? "· " + esc(c.label) : ""}</div>
        </div>`;
      }).join("") : `<span class="dim12">Không có clip trong góc này</span>`;
      return `<div class="mc-lane-row">
        <div class="mc-lane-hd"><i class="cam-chip" style="background:${m.color || CAM_COLORS[m.letter] || "#888"}">${esc(m.letter)}</i><span>${esc(m.name || ("Máy " + m.letter))}</span><span class="dim12">(${mClips.length})</span></div>
        <div class="mc-lane-track">${chips}</div>
      </div>`;
    }).join("");

    lanes.querySelectorAll(".mc-lclip").forEach((el) => {
      el.onclick = () => {
        const idx = +el.dataset.i;
        sel = new Set([idx]); cur = idx; anchor = idx;
        renderPage2Mc();
        if (typeof showCur === "function") showCur();
      };
    });
  }

  function renderPage3Mc() {
    const box = $("mcLanes3");
    if (!box) return;
    const ms = machines();
    const curC = typeof curClip === "function" ? curClip() : null;
    if (!ms.length || !curC || curC.m0 == null || curC.m1 == null) {
      box.classList.add("hidden");
      return;
    }
    box.classList.remove("hidden");

    // Tìm các clip máy khác quay cùng lúc (giao khoảng [m0, m1] tính bằng phút)
    const others = (S.clips || []).filter((c) =>
      c.uid !== curC.uid && c.mk && c.mk !== curC.mk && c.m0 != null && c.m1 != null &&
      c.m0 < curC.m1 && c.m1 > curC.m0
    );

    const hasCurIo = (curC.in_s != null && curC.out_s != null);
    const rows = others.length ? others.map((c) => {
      const ovStartM = Math.max(curC.m0, c.m0), ovEndM = Math.min(curC.m1, c.m1);
      const ovSec = Math.max(0, (ovEndM - ovStartM) * 60);
      let sugBtn = "";
      if (mcSyncSug && hasCurIo) {
        // Đổi In/Out của curC sang giờ chung (phút -> giây) rồi chiếu lên clip c
        const gIn = curC.m0 * 60 + curC.in_s;
        const gOut = curC.m0 * 60 + curC.out_s;
        const cIn = Math.max(0, gIn - c.m0 * 60);
        const cOut = Math.min(c.dur || 0, gOut - c.m0 * 60);
        const span = cOut - cIn;
        if (span >= 3.0) {
          sugBtn = `<button class="btn mc-apply-sug" data-uid="${esc(c.uid)}" data-in="${cIn.toFixed(2)}" data-out="${cOut.toFixed(2)}">Nhận gợi ý (${cIn.toFixed(1)}s–${cOut.toFixed(1)}s)</button>`;
        } else {
          sugBtn = `<span class="dim12">Phủ &lt; 3s</span>`;
        }
      }
      return `<div class="mc-other-row">
        <i class="cam-chip" style="background:${CAM_COLORS[c.mk] || "#888"}">${esc(c.mk)}</i>
        <span class="mc-oname">${esc(c.name)}</span>
        <span class="dim12">trùng ${ovSec.toFixed(0)}s</span>
        <span class="flex1"></span>
        ${sugBtn}
      </div>`;
    }).join("") : `<div class="dim12">Không có máy nào khác quay cùng thời điểm clip này.</div>`;

    box.innerHTML = `
      <div class="row-between center">
        <b>Các máy khác lúc này</b>
        <label class="p3-tg" style="padding:0"><input type="checkbox" id="mcSyncTg"${mcSyncSug ? " checked" : ""}><span class="sw"><i></i></span>Gợi ý In/Out theo giờ chung</label>
      </div>
      <div class="mc-others">${rows}</div>`;

    const tg = document.getElementById("mcSyncTg");
    if (tg) tg.onchange = () => { mcSyncSug = tg.checked; renderPage3Mc(); };

    box.querySelectorAll(".mc-apply-sug").forEach((btn) => {
      btn.onclick = async () => {
        const r = await api().set_inout(btn.dataset.uid, +btn.dataset.in, +btn.dataset.out);
        if (r && r.error) { if (typeof status === "function") status(r.error, "warn"); return; }
        const st = await api().state();
        if (st && !st.error && typeof setState === "function") setState(st);
        if (typeof status === "function") status("Đã đặt In/Out theo giờ chung vào kế hoạch (chưa ghi DaVinci).", "ok");
      };
    });
  }

  // Hook nhẹ nhàng vào renderPage2 và showCur mà không sửa logic lõi của app.js / step3.js
  const _origRenderP2 = window.renderPage2;
  if (typeof _origRenderP2 === "function") {
    window.renderPage2 = function (rebuild) {
      _origRenderP2.apply(this, arguments);
      renderPage2Mc();
    };
  }
  const _origShowCur = window.showCur;
  if (typeof _origShowCur === "function") {
    window.showCur = function () {
      _origShowCur.apply(this, arguments);
      renderPage3Mc();
    };
  }
})();
