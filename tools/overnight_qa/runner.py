r"""
runner.py - Main entry point for FramePilot.exe Overnight QA Harness (100% local, offline).

Usage examples (PowerShell, $py = "C:\VideoAI_venv\Scripts\python.exe"):
  # 1. Quick 15s health & CDP check (READONLY, zero writes to DaVinci):
  & $py -m tools.overnight_qa.runner --check-only

  # 2. Run 6 hours overnight in READONLY mode (safe even on a real project copy):
  & $py -m tools.overnight_qa.runner --hours 6 --mode readonly

  # 3. Run overnight WITH DaVinci write tests (ONLY on a project named FP_TEST_*):
  & $py -m tools.overnight_qa.runner --hours 6 --mode sandbox_write --suites smoke_e2e,ai_gpu,chaos_race,sandbox_write

  # 4. Replay a specific bug seed from morning report:
  & $py -m tools.overnight_qa.runner --suites chaos_race --seed 42 --cycles 1
"""
import argparse
import datetime
import json
import os
import random
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.overnight_qa.cdp_client import CDPClient, CDPError, wait_for_page_target
from tools.overnight_qa.reporter import BugCollector
from tools.overnight_qa.safety import (
    DEFAULT_SANDBOX_PREFIX,
    SafetyError,
    SandboxEnv,
    load_real_config,
    probe_resolve_active_project,
    verify_write_guard,
)
from tools.overnight_qa.scenarios import SUITE_REGISTRY, SuiteContext
from tools.overnight_qa.watchdog import ResourceWatchdog, detect_error_dialogs, snapshot_fp_workers

DEFAULT_EXE = r"D:\VideoAI\FramePilot_EXE\FramePilot.exe"
DEFAULT_REPORTS_ROOT = r"D:\VideoAI\data\overnight_qa_reports"


def _kill_proc_tree(pid: int):
    if not pid:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def launch_exe_with_cdp(exe_path: str, project_name: str, env: dict, cdp_port: int, timeout: float = 28.0):
    """Launch FramePilot.exe with TROLY_CONFIG + CDP enabled, wait for WebView2 page target, return (proc, cdp)."""
    cmd = [exe_path, "--project", project_name]
    proc = subprocess.Popen(
        cmd,
        cwd=os.path.dirname(os.path.abspath(exe_path)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        target = wait_for_page_target(cdp_port, timeout=timeout, proc=proc)
        cdp = CDPClient(target["webSocketDebuggerUrl"], timeout=10.0)
        cdp.enable_domains()
        return proc, cdp
    except Exception:
        dialogs = detect_error_dialogs(proc.pid)
        _kill_proc_tree(proc.pid)
        if dialogs:
            raise CDPError(f"FramePilot.exe hiện hộp thoại lỗi khi khởi động: {dialogs}")
        raise


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="FramePilot.exe Overnight QA Harness (100% local, offline)")
    ap.add_argument("--exe", default=DEFAULT_EXE, help="Đường dẫn tới FramePilot.exe")
    ap.add_argument("--mode", default="readonly", choices=("readonly", "sandbox_write"), help="Chế độ an toàn (mặc định: readonly)")
    ap.add_argument("--sandbox-prefix", default=DEFAULT_SANDBOX_PREFIX, help="Tiền tố bắt buộc của tên project khi chạy sandbox_write")
    ap.add_argument("--project", default="", help="Tên project (mặc định: tự đọc project đang mở trong DaVinci)")
    ap.add_argument("--bin", default="", help="Đường dẫn bin cần nạp (mặc định: tự chọn bin đầu tiên có clip)")
    ap.add_argument("--timeline", default="", help="Tên timeline nguồn (tùy chọn)")
    ap.add_argument("--suites", default="smoke_e2e,ai_gpu,chaos_race", help="Danh sách bài test cách nhau bằng dấu phẩy")
    ap.add_argument("--hours", type=float, default=0.0, help="Số giờ chạy xuyên đêm (vd: 6). Nếu >0 sẽ lặp tới hết giờ.")
    ap.add_argument("--cycles", type=int, default=1, help="Số vòng lặp tối đa (khi --hours = 0)")
    ap.add_argument("--seed", type=int, default=0, help="Random seed cố định để tái hiện lỗi (0 = tự sinh)")
    ap.add_argument("--cdp-port", type=int, default=9222, help="Cổng CDP nội bộ (127.0.0.1)")
    ap.add_argument("--out-root", default=DEFAULT_REPORTS_ROOT, help="Thư mục gốc lưu báo cáo")
    ap.add_argument("--check-only", action="store_true", help="Chỉ kiểm chứng nhanh 15s (kết nối DaVinci + mở EXE + kiểm tra CDP)")
    ap.add_argument("--keep-sandbox", action="store_true", help="Giữ lại thư mục sandbox sau khi chạy để kiểm tra file JSON/SRT")
    ap.add_argument("--no-anonymize", action="store_true", help="Không ẩn tên project trong báo cáo")
    a = ap.parse_args()

    if not os.path.isfile(a.exe):
        sys.exit(f"[LỖI] Không tìm thấy file EXE: {a.exe}")

    real_cfg, real_cfg_path = load_real_config(a.exe)
    print(f"[QA] Đọc cấu hình gốc: {real_cfg_path or '(không thấy)'}")

    # 1. Detect active DaVinci Resolve project
    active_proj, bins, resolve_err = probe_resolve_active_project(real_cfg)
    if resolve_err:
        print(f"[CẢNH BÁO] Kết nối DaVinci: {resolve_err}")
    project_name = a.project or active_proj
    if not project_name:
        sys.exit("[LỖI] Không xác định được tên project đang mở trong DaVinci. Hãy mở DaVinci + mở project test, hoặc truyền --project.")

    # 2. Enforce strict write safety guard
    try:
        verify_write_guard(a.mode, project_name, required_prefix=a.sandbox_prefix)
    except SafetyError as e:
        sys.exit(f"[AN TOÀN] {e}")

    seed = a.seed or random.randint(1000, 999999)
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{a.mode}"
    run_dir = os.path.join(a.out_root, run_id)
    os.makedirs(run_dir, exist_ok=True)

    sandbox = SandboxEnv(run_dir, real_cfg, preserve_models=True)
    sandbox.setup()
    proc_env = sandbox.build_process_env(cdp_port=a.cdp_port)

    anonymize = not a.no_anonymize
    bugs = BugCollector(run_dir, project_name=project_name, anonymize=anonymize)
    watchdog = ResourceWatchdog(interval_sec=5.0)
    watchdog.start()

    suites = [s.strip() for s in a.suites.split(",") if s.strip()]
    for s in suites:
        if s not in SUITE_REGISTRY:
            sandbox.teardown(keep_sandbox=False)
            watchdog.stop()
            sys.exit(f"[LỖI] Không có bài test tên '{s}'. Hợp lệ: {', '.join(SUITE_REGISTRY)}")

    replay_base = f"& C:\\VideoAI_venv\\Scripts\\python.exe -m tools.overnight_qa.runner --mode {a.mode}"
    print(f"[QA] Run ID     : {run_id}")
    print(f"[QA] Mode       : {a.mode} | Seed: {seed} | Models linked: {sandbox.models_linked}")
    print(f"[QA] Report dir : {run_dir}")

    proc = None
    cdp = None
    cycles_done = 0
    end_deadline = (time.time() + a.hours * 3600.0) if a.hours > 0 else None

    try:
        if a.check_only:
            print("[QA] Chạy kiểm chứng nhanh (--check-only)...")
            proc, cdp = launch_exe_with_cdp(a.exe, project_name, proc_env, a.cdp_port)
            watchdog.set_target_pid(proc.pid)
            time.sleep(2.5)
            spy_res = cdp.install_api_spy(readonly=True)
            info = cdp.eval_js(
                "({ ready: !!(window.pywebview && window.pywebview.api), title: document.title, hasOnEvent: typeof window.onEvent })",
                await_promise=False,
            )
            print(f"[QA] CHECK-ONLY OK! PID={proc.pid} | spy={spy_res} | page={info}")
            return

        cycle = 0
        while True:
            cycle += 1
            if end_deadline is not None:
                if time.time() >= end_deadline:
                    break
            elif cycle > a.cycles:
                break

            print(f"\n========== VÒNG {cycle} (seed={seed}) ==========")
            # Fresh launch each cycle so we also verify cold-start, persistence & zombie cleanup
            try:
                proc, cdp = launch_exe_with_cdp(a.exe, project_name, proc_env, a.cdp_port)
                watchdog.set_target_pid(proc.pid)
            except Exception as e:
                bugs.record_bug(
                    category="LAUNCH_CRASH",
                    severity="CRITICAL",
                    title=f"Không mở được FramePilot.exe / CDP ở vòng {cycle}: {str(e)[:120]}",
                    detail=str(e),
                    suite="startup",
                    cycle=cycle,
                    replay_cmd=f"{replay_base} --check-only",
                )
                time.sleep(3.0)
                continue

            ctx = SuiteContext(
                cdp=cdp,
                bugs=bugs,
                run_dir=run_dir,
                mode=a.mode,
                seed=seed,
                cycle=cycle,
                replay_base_cmd=replay_base,
                bin_path=a.bin,
                timeline=a.timeline,
                fp_pid=proc.pid,
            )

            for sname in suites:
                if end_deadline is not None and time.time() >= end_deadline:
                    break
                t0 = time.time()
                print(f"  -> Đang chạy suite '{sname}'...")
                try:
                    note = SUITE_REGISTRY[sname](ctx)
                    bugs.record_suite(sname, cycle, True, time.time() - t0, note=str(note or "OK"))
                    print(f"     [PASS] {sname} ({time.time()-t0:.1f}s): {note}")
                except Exception as e:
                    shot = ctx.snap(f"{sname}_fail") if cdp else ""
                    bugs.record_bug(
                        category="SUITE_FAILURE",
                        severity="CRITICAL" if proc.poll() is not None else "HIGH",
                        title=f"Bài test '{sname}' thất bại: {str(e)[:120]}",
                        detail=str(e),
                        suite=sname,
                        cycle=cycle,
                        screenshot=shot,
                        replay_cmd=ctx.replay_cmd(sname),
                    )
                    bugs.record_suite(sname, cycle, False, time.time() - t0, note=str(e)[:160])
                    print(f"     [FAIL] {sname} ({time.time()-t0:.1f}s): {e}")
                    # If exe crashed, break inner loop so next cycle relaunches cleanly
                    if proc.poll() is not None:
                        break

            # Clean close + zombie check
            if cdp is not None:
                cdp.close()
                cdp = None
            if proc is not None:
                _kill_proc_tree(proc.pid)
                watchdog.set_target_pid(0)
                proc = None
            time.sleep(2.0)

            zombies = snapshot_fp_workers(0)
            if zombies:
                bugs.record_bug(
                    category="ZOMBIE_AFTER_EXIT",
                    severity="HIGH",
                    title=f"Còn {len(zombies)} tiến trình xác sống sau khi đóng FramePilot.exe",
                    detail=json.dumps(zombies, ensure_ascii=False, indent=2),
                    suite="teardown",
                    cycle=cycle,
                )

            cycles_done = cycle

            # Persist intermediate report every cycle (so even if PC loses power at 4 AM, report is saved!)
            for leak in watchdog.analyze_leaks():
                bugs.record_bug(
                    category=leak["category"],
                    severity=leak["severity"],
                    title=leak["title"],
                    detail=leak["detail"],
                    suite="watchdog",
                    cycle=cycle,
                )
            for dlg in watchdog.popup_dialogs:
                bugs.record_bug(
                    category="POPUP_DIALOG",
                    severity="CRITICAL",
                    title=f"Hộp thoại lỗi Windows: {dlg.get('title', '')}",
                    detail=dlg.get("body", ""),
                    suite="watchdog",
                    cycle=cycle,
                )
            watchdog.popup_dialogs.clear()

            bugs.write_reports(
                meta={"mode": a.mode, "seed": seed, "cycles_done": cycles_done, "exe": a.exe, "suites": suites},
                watchdog_samples=watchdog.samples,
                peak_stats=watchdog.peak_stats(),
            )

    finally:
        if cdp is not None:
            cdp.close()
        if proc is not None:
            _kill_proc_tree(proc.pid)
        watchdog.stop()
        if not a.check_only:
            paths = bugs.write_reports(
                meta={"mode": a.mode, "seed": seed, "cycles_done": cycles_done, "exe": a.exe, "suites": suites},
                watchdog_samples=watchdog.samples,
                peak_stats=watchdog.peak_stats(),
            )
            print("\n========== HOÀN TẤT KIỂM THỬ ==========")
            print(f"Báo cáo Markdown : {paths['md']}")
            print(f"Báo cáo HTML     : {paths['html']}")
            print(f"Tổng lỗi duy nhất: {len(bugs.sorted_bugs())}")
        sandbox.teardown(keep_sandbox=a.keep_sandbox)


if __name__ == "__main__":
    main()
