r"""
scenarios.py - Test suites executed inside live FramePilot.exe via CDP.

Suites:
1. smoke_e2e     : Full 5-step workflow + shortcuts (event.code) + modal guard + DOM invariants.
2. ai_gpu        : Real GPU AI workers (SigLIP/DINOv2, Vision In/Out, CLAP, Whisper/WavLM) + zombie check.
3. chaos_race    : Deterministic seeded race-condition & conflict fuzzer (start/stop storms, rapid switching, undo storms).
4. sandbox_write : DaVinci write verification (ONLY in --mode sandbox_write on FP_TEST_* projects).
"""
import json
import os
import random
import time

from .cdp_client import CDPClient, CDPError
from .reporter import BugCollector
from .watchdog import snapshot_fp_workers


class SuiteContext:
    def __init__(
        self,
        cdp: CDPClient,
        bugs: BugCollector,
        run_dir: str,
        mode: str,
        seed: int,
        cycle: int,
        replay_base_cmd: str,
        bin_path: str = "",
        timeline: str = "",
        fp_pid: int = 0,
    ):
        self.cdp = cdp
        self.bugs = bugs
        self.run_dir = run_dir
        self.mode = mode
        self.seed = seed
        self.cycle = cycle
        self.replay_base_cmd = replay_base_cmd
        self.bin_path = bin_path
        self.timeline = timeline
        self.fp_pid = fp_pid
        self.shot_dir = os.path.join(run_dir, "screenshots")
        os.makedirs(self.shot_dir, exist_ok=True)
        self._shot_idx = 0

    def snap(self, tag: str) -> str:
        self._shot_idx += 1
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)[:40]
        path = os.path.join(self.shot_dir, f"c{self.cycle:02d}_{self._shot_idx:03d}_{safe}.png")
        return path if self.cdp.screenshot(path) else ""

    def replay_cmd(self, suite: str) -> str:
        return f"{self.replay_base_cmd} --suites {suite} --seed {self.seed} --cycles 1"

    def flush_passive_errors(self, suite: str, step_tag: str = ""):
        diag = self.cdp.drain_diagnostics()
        ring = diag.get("ring") or []
        found = 0

        for e in diag.get("js_exceptions") or []:
            found += 1
            self.bugs.record_bug(
                category="JS_EXCEPTION",
                severity="HIGH",
                title=f"Lỗi JS chưa bắt ({step_tag}): {str(e.get('text', ''))[:120]}",
                detail=f"{e.get('text', '')}\nAt: {e.get('url', '')}:{e.get('line')}:{e.get('col')}",
                suite=suite,
                cycle=self.cycle,
                screenshot=self.snap(f"{suite}_jsexc"),
                ring=ring,
                replay_cmd=self.replay_cmd(suite),
            )
        for e in diag.get("console_errors") or []:
            found += 1
            self.bugs.record_bug(
                category="CONSOLE_ERROR",
                severity="MEDIUM",
                title=f"Console error ({step_tag}): {str(e.get('text', ''))[:120]}",
                detail=str(e.get("text", "")),
                suite=suite,
                cycle=self.cycle,
                screenshot=self.snap(f"{suite}_console"),
                ring=ring,
                replay_cmd=self.replay_cmd(suite),
            )
        for e in diag.get("network_errors") or []:
            found += 1
            self.bugs.record_bug(
                category="MEDIA_SERVER_ERROR",
                severity="MEDIUM",
                title=f"Lỗi mạng cục bộ ({step_tag}): {e.get('status') or e.get('error')} {str(e.get('url', ''))[:80]}",
                detail=json.dumps(e, ensure_ascii=False),
                suite=suite,
                cycle=self.cycle,
                screenshot=self.snap(f"{suite}_net"),
                ring=ring,
                replay_cmd=self.replay_cmd(suite),
            )
        for e in diag.get("api_errors") or []:
            err_s = str(e.get("error", ""))
            if "[QA_READONLY_GUARD]" in err_s:
                continue
            found += 1
            sev = "HIGH" if "THROW:" in err_s else "MEDIUM"
            self.bugs.record_bug(
                category="API_ERROR",
                severity=sev,
                title=f"API {e.get('fn')} lỗi ({step_tag}): {err_s[:110]}",
                detail=f"fn={e.get('fn')} ms={e.get('ms')} args={e.get('args')}\nerror={err_s}",
                suite=suite,
                cycle=self.cycle,
                screenshot=self.snap(f"{suite}_api"),
                ring=ring,
                replay_cmd=self.replay_cmd(suite),
            )
        for e in diag.get("slow_calls") or []:
            self.bugs.record_bug(
                category="SLOW_API",
                severity="LOW",
                title=f"API {e.get('fn')} chậm bất thường ({e.get('ms')} ms)",
                detail=json.dumps(e, ensure_ascii=False),
                suite=suite,
                cycle=self.cycle,
                ring=ring,
                replay_cmd=self.replay_cmd(suite),
            )
        return found


def wait_until_ready_and_load(ctx: SuiteContext, suite: str, timeout: float = 90.0):
    """Wait for pywebviewready + INFO, select a bin with clips, click Load, wait for S.n > 0."""
    deadline = time.time() + 30.0
    while time.time() < deadline:
        ok = ctx.cdp.eval_js(
            "!!(window.pywebview && window.pywebview.api && typeof INFO !== 'undefined' && INFO)",
            await_promise=False,
        )
        if ok:
            break
        time.sleep(0.4)
    else:
        raise CDPError("Giao diện không hoàn thành pywebviewready / INFO trong 30s")

    ctx.cdp.install_api_spy(readonly=(ctx.mode == "readonly"))

    # Check if clips already loaded (e.g., on subsequent cycles)
    cur_n = ctx.cdp.eval_js("(typeof S !== 'undefined' && S && S.n) || 0", await_promise=False) or 0
    if cur_n > 0:
        return int(cur_n)

    # Pick bin: explicit --bin or first non-empty option in #binSel
    picked = ctx.cdp.eval_js(
        f"""(() => {{
            const sel = document.getElementById('binSel');
            if (!sel) return {{ error: 'missing #binSel' }};
            const want = {json.dumps(ctx.bin_path)};
            const opts = Array.from(sel.options).map(o => ({{ v: o.value, t: o.textContent || '' }}));
            let chosen = '';
            if (want && opts.some(o => o.v === want)) {{
                chosen = want;
            }} else {{
                const nonEmpty = opts.filter(o => o.v && !o.t.includes('(0)'));
                chosen = (nonEmpty[0] || opts.find(o => o.v) || {{}}).v || '';
            }}
            if (!chosen) return {{ error: 'Không có bin nào trong #binSel', opts }};
            sel.value = chosen;
            const tl = document.getElementById('tlSel');
            const wantTl = {json.dumps(ctx.timeline)};
            if (tl && wantTl) tl.value = wantTl;
            document.getElementById('loadBtn').click();
            return {{ chosen }};
        }})()""",
        await_promise=False,
    )
    if isinstance(picked, dict) and picked.get("error"):
        raise CDPError(f"Không chọn được bin để nạp clip: {picked['error']}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        st = ctx.cdp.eval_js(
            "({ n: (typeof S !== 'undefined' && S && S.n) || 0, waiting: !!(typeof S !== 'undefined' && S && S.src && S.src.waiting) })",
            await_promise=False,
        ) or {}
        if st.get("n", 0) > 0 and not st.get("waiting"):
            time.sleep(1.0)
            ctx.flush_passive_errors(suite, "after_load")
            return int(st["n"])
        time.sleep(0.6)
    raise CDPError(f"Hết giờ ({timeout:.0f}s) chờ nạp clip từ DaVinci (bin={picked})")


def _check_dom_invariants(ctx: SuiteContext, suite: str, tag: str):
    bad = ctx.cdp.eval_js(
        """(() => {
            const ids = ['curName', 'ioIn', 'ioOut', 'ioDur', 'p3Sum', 'd5Res', 'starCount', 'stageCount'];
            const issues = [];
            for (const id of ids) {
                const el = document.getElementById(id);
                if (!el) continue;
                const txt = (el.textContent || '').trim();
                if (/\\b(NaN|undefined|Infinity)\\b/.test(txt)) {
                    issues.push(id + '=' + txt.slice(0, 80));
                }
            }
            return issues;
        })()""",
        await_promise=False,
    ) or []
    if bad:
        ctx.bugs.record_bug(
            category="UI_INVARIANT",
            severity="MEDIUM",
            title=f"Giao diện hiển thị NaN/undefined ({tag}): {', '.join(bad[:3])}",
            detail=f"Các phần tử DOM chứa giá trị lỗi: {bad}",
            suite=suite,
            cycle=ctx.cycle,
            screenshot=ctx.snap(f"{suite}_nan_{tag}"),
            replay_cmd=ctx.replay_cmd(suite),
        )


def run_smoke_e2e(ctx: SuiteContext):
    """Suite 1: Full 5-step workflow + keyboard shortcuts + modal isolation + invariants."""
    suite = "smoke_e2e"
    n_clips = wait_until_ready_and_load(ctx, suite)

    # --- PAGE 1: Giai đoạn ---
    ctx.cdp.eval_js("goPage(1)", await_promise=False)
    time.sleep(0.8)
    ctx.cdp.eval_js(
        """(() => {
            const z = document.getElementById('g1Zoom');
            if (z) { z.value = 160; z.dispatchEvent(new Event('input')); z.value = 118; z.dispatchEvent(new Event('input')); }
            const tiles = document.querySelectorAll('#g1 .tile');
            if (tiles.length > 0) tiles[Math.floor(tiles.length / 3)].click();
        })()""",
        await_promise=False,
    )
    time.sleep(0.4)
    # Test F1 + Shift+F1 + Esc
    ctx.cdp.dispatch_key("F1", "F1", 0x70)
    time.sleep(0.4)
    ctx.cdp.eval_js(
        "(() => { const t = document.querySelectorAll('#g1 .tile'); if (t.length > 3) t[Math.min(t.length-1, Math.floor(t.length/3)+2)].click(); })()",
        await_promise=False,
    )
    time.sleep(0.3)
    ctx.cdp.dispatch_key("F1", "F1", 0x70, shift=True)
    time.sleep(0.4)
    ctx.cdp.dispatch_key("Escape", "Escape", 0x1B)
    time.sleep(0.3)
    _check_dom_invariants(ctx, suite, "page1")
    ctx.flush_passive_errors(suite, "page1")

    # --- PAGE 2: Phân loại bin + Player + Phím tắt + Modal Guard + Multicam ---
    ctx.cdp.eval_js("goPage(2)", await_promise=False)
    time.sleep(1.0)
    ctx.cdp.eval_js(
        """(() => {
            const z = document.getElementById('g2Zoom');
            if (z) { z.value = 150; z.dispatchEvent(new Event('input')); }
            const cards = document.querySelectorAll('#grid .card, #grid .tile');
            if (cards.length > 0) cards[0].click();
        })()""",
        await_promise=False,
    )
    time.sleep(1.2)

    # Test keyboard shortcuts: Space, J, K, L, I, O, Shift+I, Shift+O, P (star), Delete
    for code, key, vk, shift in [
        ("Space", " ", 0x20, False),
        ("Space", " ", 0x20, False),
        ("KeyL", "l", 0x4C, False),
        ("KeyK", "k", 0x4B, False),
        ("KeyJ", "j", 0x4A, False),
        ("KeyK", "k", 0x4B, False),
        ("KeyI", "i", 0x49, False),
        ("KeyO", "o", 0x4F, False),
        ("KeyP", "p", 0x50, False),
        ("KeyP", "p", 0x50, False),
    ]:
        ctx.cdp.dispatch_key(code, key, vk, shift=shift)
        time.sleep(0.25)

    # Test Modal keyboard isolation: open #settingsModal, press KeyP, verify star count didn't change!
    modal_leak = ctx.cdp.eval_js(
        """(async () => {
            const before = (document.getElementById('starCount')?.textContent || '').trim();
            document.getElementById('btnSettings')?.click();
            await new Promise(r => setTimeout(r, 250));
            const open = !document.getElementById('settingsModal')?.classList.contains('hidden');
            return { before, open };
        })()""",
        await_promise=True,
    ) or {}
    if modal_leak.get("open"):
        ctx.cdp.dispatch_key("KeyP", "p", 0x50)
        time.sleep(0.25)
        after_star = ctx.cdp.eval_js(
            "(() => { const a = (document.getElementById('starCount')?.textContent || '').trim(); document.getElementById('setCancel')?.click(); return a; })()",
            await_promise=False,
        )
        if after_star != modal_leak.get("before"):
            ctx.bugs.record_bug(
                category="SHORTCUT_CONFLICT",
                severity="HIGH",
                title="Phím tắt P vẫn lọt xuống nền khi đang mở cửa sổ Cài đặt (#settingsModal)",
                detail=f"starCount trước={modal_leak.get('before')!r}, sau khi bấm P trong modal={after_star!r}",
                suite=suite,
                cycle=ctx.cycle,
                screenshot=ctx.snap(f"{suite}_modal_leak"),
                replay_cmd=ctx.replay_cmd(suite),
            )

    # Test search & filters & LUT toggle
    ctx.cdp.eval_js(
        """(() => {
            const f = document.getElementById('p2Find');
            if (f) { f.value = 'a'; f.dispatchEvent(new Event('input')); f.value = ''; f.dispatchEvent(new Event('input')); }
            const lut = document.getElementById('plLut');
            if (lut) { lut.click(); lut.click(); }
        })()""",
        await_promise=False,
    )
    time.sleep(0.5)
    _check_dom_invariants(ctx, suite, "page2")
    ctx.flush_passive_errors(suite, "page2")

    # --- PAGE 3: In / Out + Waveform + Multicam ---
    ctx.cdp.eval_js("goPage(3)", await_promise=False)
    time.sleep(1.2)
    ctx.cdp.eval_js(
        """(() => {
            document.getElementById('waveZIn')?.click();
            document.getElementById('waveZOut')?.click();
            document.getElementById('waveZFit')?.click();
            document.getElementById('p3ViewText')?.click();
            document.getElementById('p3ViewThumb')?.click();
        })()""",
        await_promise=False,
    )
    time.sleep(0.6)
    _check_dom_invariants(ctx, suite, "page3")
    ctx.flush_passive_errors(suite, "page3")

    # --- PAGE 4: Lời nói ---
    ctx.cdp.eval_js("goPage(4)", await_promise=False)
    time.sleep(1.0)
    ctx.cdp.eval_js(
        """(() => {
            const f = document.getElementById('lnFind');
            if (f) { f.value = 'cảm ơn'; f.dispatchEvent(new Event('input')); f.value = ''; f.dispatchEvent(new Event('input')); }
        })()""",
        await_promise=False,
    )
    time.sleep(0.4)
    _check_dom_invariants(ctx, suite, "page4")
    ctx.flush_passive_errors(suite, "page4")

    # --- PAGE 5: Thời lượng ---
    ctx.cdp.eval_js("goPage(5)", await_promise=False)
    time.sleep(1.0)
    ctx.cdp.eval_js(
        """(() => {
            const p = document.querySelector('#d5Presets button');
            if (p) p.click();
            document.getElementById('d5Fit')?.click();
        })()""",
        await_promise=False,
    )
    time.sleep(0.8)
    _check_dom_invariants(ctx, suite, "page5")
    ctx.flush_passive_errors(suite, "page5")

    return f"Đã test đủ 5 trang trên {n_clips} clip"


def run_ai_gpu(ctx: SuiteContext):
    """Suite 2: Exercise real GPU AI workers (SigLIP/DINOv2, Vision In/Out, CLAP, Whisper/WavLM) + zombie check."""
    suite = "ai_gpu"
    n_clips = wait_until_ready_and_load(ctx, suite)

    # 1. Check AI readiness & model availability
    ai_info = ctx.cdp.eval_js("window.pywebview.api.ai_info()", await_promise=True, timeout=20.0) or {}
    if ai_info.get("error"):
        ctx.bugs.record_bug(
            category="AI_ENV_ERROR",
            severity="HIGH",
            title=f"ai_info() báo lỗi: {str(ai_info['error'])[:120]}",
            detail=json.dumps(ai_info, ensure_ascii=False),
            suite=suite,
            cycle=ctx.cycle,
            replay_cmd=ctx.replay_cmd(suite),
        )

    # 2. Trigger AI search (accent-free & synonym test)
    for q in ("co dau", "tiec cuoi", "gia dinh"):
        try:
            ctx.cdp.eval_js(f"window.pywebview.api.ai_search({json.dumps(q)})", await_promise=True, timeout=15.0)
        except Exception:
            pass

    # 3. Trigger Vision In/Out suggestion (troly_vision_io + MediaPipe) then stop cleanly after brief progress
    ctx.cdp.eval_js("goPage(3)", await_promise=False)
    time.sleep(0.6)
    ctx.cdp.eval_js("window.pywebview.api.inout_suggest_start()", await_promise=True, timeout=15.0)
    time.sleep(4.0)
    ctx.flush_passive_errors(suite, "inout_suggest")

    # 4. Trigger CLAP audio_events on first clip (if available)
    first_uid = ctx.cdp.eval_js("(S && S.clips && S.clips[0] && S.clips[0].uid) || ''", await_promise=False) or ""
    if first_uid:
        try:
            ctx.cdp.eval_js(
                f"window.pywebview.api.audio_events({json.dumps(first_uid)})",
                await_promise=True,
                timeout=45.0,
            )
        except Exception as e:
            ctx.bugs.record_bug(
                category="AI_CLAP_ERROR",
                severity="MEDIUM",
                title=f"audio_events (CLAP) lỗi/timeout: {str(e)[:120]}",
                detail=str(e),
                suite=suite,
                cycle=ctx.cycle,
                screenshot=ctx.snap(f"{suite}_clap"),
                replay_cmd=ctx.replay_cmd(suite),
            )

    # 5. Trigger AI embedding (ai_run) for 6 seconds then stop cleanly -> verify no zombie worker
    ctx.cdp.eval_js("goPage(2)", await_promise=False)
    time.sleep(0.4)
    ctx.cdp.eval_js("window.pywebview.api.ai_run()", await_promise=True, timeout=15.0)
    time.sleep(6.0)
    ctx.cdp.eval_js("window.pywebview.api.ai_stop()", await_promise=True, timeout=15.0)
    time.sleep(3.0)

    # 6. Trigger Speech ASR (speech_start) for 5 seconds then speech_stop -> verify clean cancellation
    ctx.cdp.eval_js("goPage(4)", await_promise=False)
    time.sleep(0.4)
    ctx.cdp.eval_js("window.pywebview.api.speech_start()", await_promise=True, timeout=15.0)
    time.sleep(5.0)
    ctx.cdp.eval_js("window.pywebview.api.speech_stop()", await_promise=True, timeout=15.0)
    time.sleep(3.5)

    # Check if AI/ASR workers exited cleanly after stop!
    lingering = [
        w for w in snapshot_fp_workers(ctx.fp_pid)
        if w["name"] in ("python.exe", "pythonw.exe")
    ]
    if lingering:
        ctx.bugs.record_bug(
            category="ZOMBIE_WORKER",
            severity="HIGH",
            title=f"Còn {len(lingering)} tiến trình AI worker chưa tắt sau khi bấm Stop",
            detail=json.dumps(lingering, ensure_ascii=False, indent=2),
            suite=suite,
            cycle=ctx.cycle,
            replay_cmd=ctx.replay_cmd(suite),
        )

    ctx.flush_passive_errors(suite, "ai_gpu_end")
    return f"Đã stress-test AI/GPU/Cancel trên {n_clips} clip (lingering_workers={len(lingering)})"


def run_chaos_race(ctx: SuiteContext, steps: int = 35):
    """Suite 3: Deterministic seeded chaos & race-condition hunter."""
    suite = "chaos_race"
    n_clips = wait_until_ready_and_load(ctx, suite)
    rng = random.Random(ctx.seed * 1009 + ctx.cycle)

    uids = ctx.cdp.eval_js("(S && S.clips || []).slice(0, 30).map(c => c.uid)", await_promise=False) or []
    if not uids:
        return "Không có clip để fuzz"

    for i in range(steps):
        action = rng.choice([
            "switch_page",
            "rapid_clip_scrub",
            "star_and_undo",
            "inout_mutate",
            "style_flip",
            "ai_start_stop_race",
            "speech_start_stop_race",
            "wave_and_frames_race",
        ])

        if action == "switch_page":
            pg = rng.randint(1, 5)
            ctx.cdp.eval_js(f"goPage({pg})", await_promise=False)
            time.sleep(rng.uniform(0.08, 0.25))

        elif action == "rapid_clip_scrub":
            ctx.cdp.eval_js("goPage(2)", await_promise=False)
            pick = rng.sample(uids, min(5, len(uids)))
            for u in pick:
                ctx.cdp.eval_js(
                    f"(async () => {{ try {{ window.pywebview.api.big({json.dumps(u)}); window.pywebview.api.play_info({json.dumps(u)}); }} catch(_){{}} }})()",
                    await_promise=False,
                )
                time.sleep(0.06)

        elif action == "star_and_undo":
            u = rng.choice(uids)
            ctx.cdp.eval_js(
                f"(async () => {{ await window.pywebview.api.toggle_star([{json.dumps(u)}]); await window.pywebview.api.undo(); }})()",
                await_promise=True,
                timeout=15.0,
            )

        elif action == "inout_mutate":
            u = rng.choice(uids)
            t1 = round(rng.uniform(0.5, 3.0), 2)
            t2 = round(t1 + rng.uniform(1.0, 4.0), 2)
            ctx.cdp.eval_js(
                f"window.pywebview.api.set_inout({json.dumps(u)}, {t1}, {t2})",
                await_promise=True,
                timeout=15.0,
            )

        elif action == "style_flip":
            st = rng.choice(["", "traditional", "psc"])
            ctx.cdp.eval_js(
                f"window.pywebview.api.set_shoot_style({json.dumps(st)})",
                await_promise=True,
                timeout=15.0,
            )

        elif action == "ai_start_stop_race":
            ctx.cdp.eval_js("window.pywebview.api.ai_run()", await_promise=False)
            time.sleep(rng.uniform(0.2, 1.0))
            ctx.cdp.eval_js("window.pywebview.api.ai_stop()", await_promise=True, timeout=15.0)

        elif action == "speech_start_stop_race":
            ctx.cdp.eval_js("window.pywebview.api.speech_start()", await_promise=False)
            time.sleep(rng.uniform(0.2, 0.9))
            ctx.cdp.eval_js("window.pywebview.api.speech_stop()", await_promise=True, timeout=15.0)

        elif action == "wave_and_frames_race":
            u = rng.choice(uids)
            ctx.cdp.eval_js(
                f"(() => {{ window.pywebview.api.wave({json.dumps(u)}); window.pywebview.api.keyframes({json.dumps(u)}); }})()",
                await_promise=False,
            )
            time.sleep(0.15)

        if i % 8 == 7:
            _check_dom_invariants(ctx, suite, f"chaos_step_{i}")
            ctx.flush_passive_errors(suite, f"chaos_{action}")

    # Final state consistency check
    st = ctx.cdp.eval_js("window.pywebview.api.state()", await_promise=True, timeout=15.0) or {}
    if not st or st.get("n") != n_clips:
        ctx.bugs.record_bug(
            category="STATE_DESYNC",
            severity="CRITICAL",
            title=f"Sai lệch số clip sau chaos fuzz: ban đầu={n_clips}, hiện tại={st.get('n')}",
            detail=json.dumps(st, ensure_ascii=False)[:800],
            suite=suite,
            cycle=ctx.cycle,
            screenshot=ctx.snap(f"{suite}_desync"),
            replay_cmd=ctx.replay_cmd(suite),
        )
    ctx.flush_passive_errors(suite, "chaos_end")
    return f"Đã chạy {steps} bước chaos/race (seed={ctx.seed})"


def run_sandbox_write(ctx: SuiteContext):
    """Suite 4: DaVinci write verification (ONLY allowed in sandbox_write mode on FP_TEST_*)."""
    suite = "sandbox_write"
    if ctx.mode != "sandbox_write":
        return "Bỏ qua (đang ở chế độ readonly)"

    wait_until_ready_and_load(ctx, suite)

    # 1. Preview + Apply + Undo
    prev = ctx.cdp.eval_js("window.pywebview.api.apply_preview()", await_promise=True, timeout=20.0)
    if isinstance(prev, dict) and prev.get("error"):
        ctx.bugs.record_bug(
            category="RESOLVE_WRITE_ERROR",
            severity="HIGH",
            title=f"apply_preview() lỗi: {prev['error'][:120]}",
            detail=json.dumps(prev, ensure_ascii=False),
            suite=suite,
            cycle=ctx.cycle,
            replay_cmd=ctx.replay_cmd(suite),
        )
    else:
        ap = ctx.cdp.eval_js("window.pywebview.api.apply()", await_promise=True, timeout=60.0)
        if isinstance(ap, dict) and ap.get("error"):
            ctx.bugs.record_bug(
                category="RESOLVE_WRITE_ERROR",
                severity="HIGH",
                title=f"apply() lỗi: {ap['error'][:120]}",
                detail=json.dumps(ap, ensure_ascii=False),
                suite=suite,
                cycle=ctx.cycle,
                screenshot=ctx.snap(f"{suite}_apply"),
                replay_cmd=ctx.replay_cmd(suite),
            )
        time.sleep(1.0)
        ctx.cdp.eval_js("window.pywebview.api.undo()", await_promise=True, timeout=30.0)

    # 2. In/Out write preview on 1 clip + write + undo
    first_uid = ctx.cdp.eval_js("(S && S.clips && S.clips[0] && S.clips[0].uid) || ''", await_promise=False) or ""
    if first_uid:
        ctx.cdp.eval_js(f"window.pywebview.api.set_inout({json.dumps(first_uid)}, 1.0, 4.0)", await_promise=True, timeout=15.0)
        io_prev = ctx.cdp.eval_js(f"window.pywebview.api.inout_write_preview([{json.dumps(first_uid)}])", await_promise=True, timeout=20.0)
        if isinstance(io_prev, dict) and not io_prev.get("error"):
            io_wr = ctx.cdp.eval_js(f"window.pywebview.api.inout_write([{json.dumps(first_uid)}])", await_promise=True, timeout=30.0)
            if isinstance(io_wr, dict) and io_wr.get("error"):
                ctx.bugs.record_bug(
                    category="RESOLVE_WRITE_ERROR",
                    severity="HIGH",
                    title=f"inout_write() lỗi: {io_wr['error'][:120]}",
                    detail=json.dumps(io_wr, ensure_ascii=False),
                    suite=suite,
                    cycle=ctx.cycle,
                    screenshot=ctx.snap(f"{suite}_iowrite"),
                    replay_cmd=ctx.replay_cmd(suite),
                )
            time.sleep(0.8)
            ctx.cdp.eval_js("window.pywebview.api.inout_undo()", await_promise=True, timeout=30.0)

    ctx.flush_passive_errors(suite, "sandbox_write_end")
    return "Đã test ghi & hoàn tác trên project FP_TEST_*"


SUITE_REGISTRY = {
    "smoke_e2e": run_smoke_e2e,
    "ai_gpu": run_ai_gpu,
    "chaos_race": run_chaos_race,
    "sandbox_write": run_sandbox_write,
}
