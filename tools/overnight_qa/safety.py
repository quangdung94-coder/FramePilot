r"""
safety.py - Sandbox isolation & DaVinci Resolve safety guard for Overnight QA.

Guarantees:
1. TROLY_NO_SHUTDOWN=1 is always enforced (never shuts down the PC).
2. TROLY_CONFIG points to an isolated config_sandbox.json inside the run directory
   so real user data (D:\VideoAI\data\troly\projects), cache, SRT, and templates
   are NEVER overwritten.
3. Links real <data_root>\models via an NTFS directory junction into
   <sandbox>\models so GPU AI workers (SigLIP, Whisper, WavLM, CLAP, MediaPipe)
   work offline without duplicating gigabytes of models. Junction is unlinked
   safely with os.rmdir() so real models are NEVER touched during cleanup.
4. In `sandbox_write` mode, strictly requires the active DaVinci Resolve project
   name to start with `FP_TEST_` (configurable prefix). Refuses to run otherwise.
5. Anonymizes real client project names in generated reports by default.
"""
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.join(REPO_ROOT, "app")
DEFAULT_SANDBOX_PREFIX = "FP_TEST_"


class SafetyError(RuntimeError):
    """Raised when a safety precondition is violated."""


def load_real_config(exe_path: str = ""):
    """Load real config.json (preferring next to exe, falling back to repo root)."""
    candidates = []
    if exe_path:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(exe_path)), "config.json"))
    candidates.append(os.path.join(REPO_ROOT, "config.json"))
    for p in candidates:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8-sig") as f:
                return json.load(f) or {}, p
    return {}, ""


def probe_resolve_active_project(real_cfg: dict):
    """Connect read-only to running DaVinci Resolve and return (project_name, bins_list, error)."""
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)
    try:
        # Ensure troly_env reads real config for resolve install_path
        import troly_env
        resolve = troly_env.connect_resolve()
        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject() if pm else None
        if not proj:
            return "", [], "DaVinci Resolve đang mở nhưng chưa mở project nào."
        pname = proj.GetName() or ""
        pool = proj.GetMediaPool()
        bins = []
        if pool:
            root = pool.GetRootFolder()
            if root:
                def walk(folder, prefix):
                    name = folder.GetName() or ""
                    full = f"{prefix}/{name}" if prefix else name
                    clips = folder.GetClipList() or []
                    bins.append({"path": full, "count": len(clips)})
                    for sub in (folder.GetSubFolderList() or []):
                        walk(sub, full)
                walk(root, "")
        return pname, bins, ""
    except Exception as e:
        return "", [], str(e)


def switch_resolve_project(target_project: str):
    """Switch active DaVinci Resolve project to target_project via ProjectManager.LoadProject."""
    if not target_project:
        return False, "Tên project trống"
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)
    try:
        import troly_env
        resolve = troly_env.connect_resolve()
        pm = resolve.GetProjectManager()
        if not pm:
            return False, "Không lấy được ProjectManager từ DaVinci Resolve"
        cur = pm.GetCurrentProject()
        if cur and (cur.GetName() or "") == target_project:
            return True, ""
        loaded = pm.LoadProject(target_project)
        if not loaded:
            return False, f"DaVinci không mở được project '{target_project}' (kiểm tra lại tên chính xác trong Project Manager)."
        return True, ""
    except Exception as e:
        return False, str(e)


def verify_write_guard(mode: str, project_name: str, required_prefix: str = DEFAULT_SANDBOX_PREFIX):
    """Enforce strict project-name guard when mode == 'sandbox_write'."""
    if mode not in ("readonly", "sandbox_write"):
        raise SafetyError(f"Chế độ không hợp lệ: {mode!r} (chỉ chấp nhận 'readonly' hoặc 'sandbox_write').")
    if mode == "sandbox_write":
        if not required_prefix or len(required_prefix) < 3:
            raise SafetyError("Tiền tố bảo vệ project test không được rỗng hoặc quá ngắn.")
        if not project_name or not project_name.startswith(required_prefix):
            raise SafetyError(
                f"CHẶN AN TOÀN: Chế độ 'sandbox_write' chỉ được chạy trên project có tên bắt đầu bằng "
                f"'{required_prefix}' (hiện đang mở: '{project_name or '(không rõ)'}'). "
                f"Hãy nhân bản project sang '{required_prefix}01' trong DaVinci rồi chạy lại, "
                f"hoặc dùng '--mode readonly'."
            )


def _create_dir_junction(link_path: str, target_path: str) -> bool:
    """Create an NTFS directory junction on Windows (no admin privileges required)."""
    if os.path.exists(link_path):
        return True
    if not os.path.isdir(target_path):
        return False
    if os.name == "nt":
        res = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link_path, target_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return res.returncode == 0
    try:
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError:
        return False


def _remove_dir_junction_safely(link_path: str):
    """Remove ONLY the junction/symlink pointer — NEVER delete contents of target_path!"""
    if not os.path.lexists(link_path):
        return
    try:
        if os.path.islink(link_path):
            os.unlink(link_path)
        else:
            # On Windows Python 3.10, os.rmdir removes a directory junction safely without recursing
            os.rmdir(link_path)
    except OSError:
        pass


class SandboxEnv:
    """Manages an isolated sandbox data_root, cache_root, srt_root, and config_sandbox.json."""

    def __init__(self, run_dir: str, real_cfg: dict, preserve_models: bool = True):
        self.run_dir = os.path.abspath(run_dir)
        self.sandbox_dir = os.path.join(self.run_dir, "sandbox")
        self.data_root = os.path.join(self.sandbox_dir, "data")
        self.cache_root = os.path.join(self.sandbox_dir, "cache")
        self.srt_root = os.path.join(self.sandbox_dir, "srt")
        self.templates_path = os.path.join(self.data_root, "troly", "templates.json")
        self.config_path = os.path.join(self.sandbox_dir, "config_sandbox.json")
        self.models_link = os.path.join(self.data_root, "models")
        self._real_cfg = dict(real_cfg or {})
        self._preserve_models = preserve_models
        self.models_linked = False

    def setup(self):
        os.makedirs(os.path.join(self.data_root, "troly", "projects"), exist_ok=True)
        os.makedirs(self.cache_root, exist_ok=True)
        os.makedirs(self.srt_root, exist_ok=True)

        # Link real models directory (read-only usage) so GPU AI workers find all models offline
        real_data = self._real_cfg.get("data_root") or r"D:\VideoAI\data"
        real_models = os.path.join(real_data, "models")
        if self._preserve_models and os.path.isdir(real_models):
            self.models_linked = _create_dir_junction(self.models_link, real_models)

        # Copy templates.json if present (into sandbox so edits never touch real templates)
        real_tpl = self._real_cfg.get("templates_path") or os.path.join(real_data, "troly", "templates.json")
        if os.path.isfile(real_tpl):
            try:
                shutil.copy2(real_tpl, self.templates_path)
            except OSError:
                pass

        cfg = dict(self._real_cfg)
        cfg["data_root"] = self.data_root
        cfg["cache_root"] = self.cache_root
        cfg["srt_root"] = self.srt_root
        cfg["templates_path"] = self.templates_path

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return self.config_path

    def build_process_env(self, cdp_port: int) -> dict:
        """Build child process environment with TROLY_CONFIG, TROLY_NO_SHUTDOWN, and CDP flags."""
        env = os.environ.copy()
        env["TROLY_CONFIG"] = self.config_path
        env["TROLY_NO_SHUTDOWN"] = "1"
        existing = env.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "").strip()
        cdp_flag = f"--remote-debugging-port={cdp_port}"
        if cdp_flag not in existing:
            env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{existing} {cdp_flag}".strip()
        return env

    def teardown(self, keep_sandbox: bool = False):
        """Safely unlink the models junction first, then optionally remove sandbox folder."""
        _remove_dir_junction_safely(self.models_link)
        if not keep_sandbox and os.path.isdir(self.sandbox_dir):
            # Double-check models link is gone before rmtree!
            if not os.path.lexists(self.models_link):
                shutil.rmtree(self.sandbox_dir, ignore_errors=True)


def anonymize_text(text: str, project_name: str, enabled: bool = True) -> str:
    """Replace real client project names in logs/reports with a neutral placeholder."""
    if not enabled or not project_name or not text:
        return text
    if project_name.startswith(DEFAULT_SANDBOX_PREFIX):
        return text
    return text.replace(project_name, "PROJECT_TEST_MASKED")
