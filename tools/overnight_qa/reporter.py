r"""
reporter.py - Deduplicating Morning Bug Report Generator (Markdown + offline HTML + JSON).

Collects all bugs, warnings, suite results, and resource telemetry during an
overnight QA run, deduplicates identical findings by fingerprint, masks real
client names, maps findings to likely source files in D:\VideoAI\TroLyFileQuay\app\,
and outputs:
- summary.json (machine-readable)
- report.md    (concise Vietnamese report for morning review & AI fixing)
- report.html  (offline dark-mode dashboard with inline SVG RAM/VRAM chart)
"""
import datetime
import hashlib
import html
import json
import os
import re

from .safety import anonymize_text

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

SOURCE_HINTS = [
    (r"player\.js|play_info|frames_open|troly_play|PL\.|FR\.", "app/troly_web/player.js & app/troly_play.py"),
    (r"multicam|mcBar|mcLanes|mc-apply", "app/troly_web/multicam.js"),
    (r"step3|wave|inout_suggest|p3|troly_vision_io", "app/troly_web/step3.js & app/troly_vision_io.py"),
    (r"speech|ln[A-Z]|diarize|asr|whisper|wavlm", "app/troly_web/speech.js & app/troly_speech*.py"),
    (r"step5|dur_|d5|troly_dur", "app/troly_web/step5.js & app/troly_dur.py"),
    (r"ai_|ai\.js|siglip|dinov2|openclip|troly_ai", "app/troly_web/ai.js & app/troly_ai.py"),
    (r"audio_events|clap", "app/troly_audio_events.py & app/troly_api.py"),
    (r"resolve|apply|MoveClips|CreateTimeline", "app/troly_resolve.py & app/troly_api.py"),
    (r"MEMORY_LEAK|HANDLE_LEAK|VRAM_LEAK|ZOMBIE", "app/troly_frames.py / app/troly_play.py / app/troly_proc.py"),
]


def guess_source_hint(category: str, title: str, detail: str) -> str:
    blob = f"{category} {title} {detail}"
    for pattern, hint in SOURCE_HINTS:
        if re.search(pattern, blob, re.IGNORECASE):
            return hint
    return "app/troly_api.py & app/troly_web/app.js"


def _fingerprint(category: str, title: str) -> str:
    # Normalize numbers/timestamps/hex IDs so repeated occurrences of the same bug collapse into 1 card
    norm = re.sub(r"\b\d+(\.\d+)?\b", "<N>", f"{category}|{title}".lower())
    norm = re.sub(r"0x[0-9a-f]+", "<HEX>", norm)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


class BugCollector:
    """Thread-safe deduplicating bug & suite result recorder."""

    def __init__(self, run_dir: str, project_name: str = "", anonymize: bool = True):
        self.run_dir = os.path.abspath(run_dir)
        self.project_name = project_name
        self.anonymize = anonymize
        self.started_at = datetime.datetime.now()
        self.suite_runs = []
        self._bugs = {}  # fingerprint -> bug dict

    def _clean(self, text: str) -> str:
        return anonymize_text(str(text or ""), self.project_name, enabled=self.anonymize)

    def record_bug(
        self,
        category: str,
        severity: str,
        title: str,
        detail: str = "",
        suite: str = "",
        cycle: int = 0,
        screenshot: str = "",
        ring: list = None,
        replay_cmd: str = "",
    ):
        clean_title = self._clean(title)
        clean_detail = self._clean(detail)
        fp = _fingerprint(category, clean_title)
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        if fp in self._bugs:
            b = self._bugs[fp]
            b["count"] += 1
            b["last_seen"] = now_str
            if screenshot and not b["screenshot"]:
                b["screenshot"] = screenshot
            return b

        bug = {
            "id": f"BUG-{len(self._bugs) + 1:03d}",
            "fingerprint": fp,
            "category": category,
            "severity": severity if severity in SEVERITY_ORDER else "MEDIUM",
            "title": clean_title,
            "detail": clean_detail[:2000],
            "suite": suite,
            "cycle": cycle,
            "count": 1,
            "first_seen": now_str,
            "last_seen": now_str,
            "screenshot": screenshot,
            "ring": [self._clean(json.dumps(x, ensure_ascii=False)) for x in (ring or [])[-20:]],
            "replay_cmd": self._clean(replay_cmd),
            "source_hint": guess_source_hint(category, clean_title, clean_detail),
        }
        self._bugs[fp] = bug
        return bug

    def record_suite(self, suite: str, cycle: int, ok: bool, duration_s: float, note: str = ""):
        self.suite_runs.append({
            "ts": datetime.datetime.now().strftime("%H:%M:%S"),
            "suite": suite,
            "cycle": cycle,
            "ok": ok,
            "duration_s": round(duration_s, 2),
            "note": self._clean(note),
        })

    def sorted_bugs(self):
        return sorted(
            self._bugs.values(),
            key=lambda b: (SEVERITY_ORDER.get(b["severity"], 9), -b["count"], b["id"]),
        )

    def write_reports(self, meta: dict, watchdog_samples: list, peak_stats: dict):
        os.makedirs(self.run_dir, exist_ok=True)
        bugs = self.sorted_bugs()
        finished_at = datetime.datetime.now()
        elapsed_min = round((finished_at - self.started_at).total_seconds() / 60.0, 2)

        sev_counts = {k: 0 for k in SEVERITY_ORDER}
        for b in bugs:
            sev_counts[b["severity"]] = sev_counts.get(b["severity"], 0) + 1

        summary = {
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": finished_at.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_min": elapsed_min,
            "meta": {k: self._clean(v) if isinstance(v, str) else v for k, v in (meta or {}).items()},
            "severity_counts": sev_counts,
            "total_unique_bugs": len(bugs),
            "total_bug_events": sum(b["count"] for b in bugs),
            "peak_stats": peak_stats or {},
            "suite_runs": self.suite_runs,
            "bugs": bugs,
        }

        json_path = os.path.join(self.run_dir, "summary.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        md_path = os.path.join(self.run_dir, "report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown(summary))

        html_path = os.path.join(self.run_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(self._render_html(summary, watchdog_samples or []))

        return {"json": json_path, "md": md_path, "html": html_path}

    def _render_markdown(self, s: dict) -> str:
        m = s["meta"]
        pk = s["peak_stats"]
        sc = s["severity_counts"]
        lines = [
            "# Báo cáo Kiểm thử Xuyên Đêm — FramePilot.exe",
            "",
            f"- **Thời gian:** `{s['started_at']}` → `{s['finished_at']}` (**{s['elapsed_min']} phút**)",
            f"- **Chế độ:** `{m.get('mode', 'readonly')}` | **Seed:** `{m.get('seed', '')}` | **Số vòng:** `{m.get('cycles_done', 0)}`",
            f"- **Bản EXE:** `{m.get('exe', '')}`",
            f"- **Tổng lỗi duy nhất:** **{s['total_unique_bugs']}** "
            f"(CRITICAL: {sc['CRITICAL']}, HIGH: {sc['HIGH']}, MEDIUM: {sc['MEDIUM']}, LOW: {sc['LOW']}) "
            f"— tổng số lần xảy ra: {s['total_bug_events']}",
            f"- **Tài nguyên đỉnh:** RAM tổng `{pk.get('peak_total_mb', 0)} MB` "
            f"(FramePilot `{pk.get('peak_fp_mb', 0)} MB` + WebView2 `{pk.get('peak_wv2_mb', 0)} MB`), "
            f"Handles `{pk.get('peak_handles', 0)}`, VRAM GPU `{pk.get('peak_vram_mb', 'N/A')} MB`",
            "",
            "## 1. Kết quả theo từng bài test",
            "",
            "| Giờ | Vòng | Bài test | Trạng thái | Thời gian | Ghi chú |",
            "|---|---:|---|---|---:|---|",
        ]
        for r in s["suite_runs"]:
            st = "PASS" if r["ok"] else "FAIL"
            lines.append(f"| {r['ts']} | {r['cycle']} | `{r['suite']}` | **{st}** | {r['duration_s']}s | {r['note']} |")

        lines.extend(["", "## 2. Danh sách lỗi & xung đột phát hiện được", ""])
        if not s["bugs"]:
            lines.append("Không phát hiện lỗi hay xung đột nào trong phiên chạy này!")
        else:
            for b in s["bugs"]:
                lines.extend([
                    f"### [{b['severity']}] {b['id']} — {b['title']} (lặp {b['count']} lần)",
                    f"- **Nhóm lỗi:** `{b['category']}` | **Bài test:** `{b['suite']}` (vòng {b['cycle']}) | **Thời điểm:** {b['first_seen']} – {b['last_seen']}",
                    f"- **Gợi ý vị trí code:** `{b['source_hint']}`",
                ])
                if b["screenshot"]:
                    rel = os.path.basename(b["screenshot"])
                    lines.append(f"- **Ảnh chụp:** `screenshots/{rel}`")
                if b["replay_cmd"]:
                    lines.append(f"- **Lệnh tái hiện nhanh:** `{b['replay_cmd']}`")
                if b["detail"]:
                    lines.extend(["", "```text", b["detail"], "```"])
                if b["ring"]:
                    lines.extend(["", "<details><summary>20 thao tác / sự kiện gần nhất trước khi lỗi</summary>", "", "```json"])
                    lines.extend(b["ring"])
                    lines.extend(["```", "</details>"])
                lines.append("")
        return "\n".join(lines)

    def _render_svg_chart(self, samples: list) -> str:
        if len(samples) < 2:
            return "<p style='color:#9ca3af'>Chưa đủ mẫu đo RAM/VRAM để vẽ biểu đồ.</p>"
        w, h, pad = 760, 180, 28
        rams = [float(x.get("total_app_mb") or 0) for x in samples]
        vrams = [float(x["vram_used_mb"]) for x in samples if x.get("vram_used_mb") is not None]
        max_y = max(max(rams), max(vrams) if vrams else 0, 100.0)

        def to_pts(vals):
            n = max(1, len(vals) - 1)
            pts = []
            for i, v in enumerate(vals):
                x = pad + (w - 2 * pad) * (i / n)
                y = h - pad - (h - 2 * pad) * (v / max_y)
                pts.append(f"{x:.1f},{y:.1f}")
            return " ".join(pts)

        ram_poly = to_pts(rams)
        vram_poly = to_pts([float(x.get("vram_used_mb") or 0) for x in samples]) if vrams else ""
        vram_svg = f'<polyline fill="none" stroke="#f59e0b" stroke-width="2" points="{vram_poly}" />' if vram_poly else ""
        return (
            f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" style="background:#111216;border-radius:8px;border:1px solid #2b2d35">'
            f'<text x="{pad}" y="18" fill="#9ca3af" font-size="11">Đỉnh: {max_y:.0f} MB | Xanh: Tổng RAM App | Cam: VRAM GPU</text>'
            f'<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="{ram_poly}" />'
            f'{vram_svg}</svg>'
        )

    def _render_html(self, s: dict, samples: list) -> str:
        esc = html.escape
        sc = s["severity_counts"]
        pk = s["peak_stats"]
        cards = []
        for b in s["bugs"]:
            sev_color = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#60a5fa"}.get(b["severity"], "#9ca3af")
            img_html = ""
            if b["screenshot"]:
                rel = "screenshots/" + os.path.basename(b["screenshot"])
                img_html = f'<div style="margin-top:8px"><a href="{esc(rel)}" target="_blank"><img src="{esc(rel)}" style="max-width:460px;border-radius:6px;border:1px solid #333"></a></div>'
            cards.append(
                f'<div class="card" style="border-left:4px solid {sev_color}">'
                f'<div><span class="badge" style="background:{sev_color}">{esc(b["severity"])}</span> '
                f'<b>{esc(b["id"])}</b> — {esc(b["title"])} <span class="dim">(lặp {b["count"]} lần)</span></div>'
                f'<div class="dim" style="margin:6px 0">Nhóm: <code>{esc(b["category"])}</code> · Bài test: <code>{esc(b["suite"])}</code> · Gợi ý code: <code>{esc(b["source_hint"])}</code></div>'
                f'<pre>{esc(b["detail"])}</pre>'
                f'{img_html}</div>'
            )
        bugs_html = "".join(cards) if cards else '<div class="card" style="border-left:4px solid #22c55e"><b>Không phát hiện lỗi nào!</b></div>'
        rows = "".join(
            f'<tr><td>{esc(r["ts"])}</td><td>{r["cycle"]}</td><td><code>{esc(r["suite"])}</code></td>'
            f'<td style="color:{"#22c55e" if r["ok"] else "#ef4444"};font-weight:700">{"PASS" if r["ok"] else "FAIL"}</td>'
            f'<td>{r["duration_s"]}s</td><td>{esc(r["note"])}</td></tr>'
            for r in s["suite_runs"]
        )
        return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>FramePilot Overnight QA Report</title>
<style>
body{{background:#18181b;color:#e4e4e7;font-family:"Segoe UI",sans-serif;margin:0;padding:24px;line-height:1.5}}
.wrap{{max-width:1100px;margin:0 auto}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}}
.kpi{{background:#222228;padding:14px;border-radius:8px;border:1px solid #2e2e36}}
.kpi .v{{font-size:24px;font-weight:700;margin-top:4px}}
.card{{background:#222228;padding:14px 16px;border-radius:8px;margin:12px 0;border:1px solid #2e2e36}}
.badge{{color:#111;font-weight:700;padding:2px 7px;border-radius:4px;font-size:12px}}
.dim{{color:#a1a1aa;font-size:13px}}
pre{{background:#111216;padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;color:#fca5a5}}
table{{width:100%;border-collapse:collapse;background:#222228;border-radius:8px;overflow:hidden}}
th,td{{padding:8px 10px;border-bottom:1px solid #2e2e36;text-align:left;font-size:13px}}
th{{background:#1c1c21;color:#a1a1aa}}
code{{background:#111216;padding:1px 5px;border-radius:4px;font-size:12px}}
</style></head><body><div class="wrap">
<h1>Báo cáo Kiểm thử Xuyên Đêm — FramePilot.exe</h1>
<div class="dim">{esc(s['started_at'])} → {esc(s['finished_at'])} ({s['elapsed_min']} phút) · Chế độ: <code>{esc(str(s['meta'].get('mode','')))}</code> · Seed: <code>{esc(str(s['meta'].get('seed','')))}</code></div>
<div class="kpis">
  <div class="kpi"><div class="dim">Lỗi duy nhất</div><div class="v">{s['total_unique_bugs']}</div><div class="dim">CRIT {sc['CRITICAL']} · HIGH {sc['HIGH']} · MED {sc['MEDIUM']}</div></div>
  <div class="kpi"><div class="dim">Tổng RAM App đỉnh</div><div class="v">{pk.get('peak_total_mb', 0)} MB</div><div class="dim">FP {pk.get('peak_fp_mb', 0)} + WV2 {pk.get('peak_wv2_mb', 0)}</div></div>
  <div class="kpi"><div class="dim">VRAM GPU đỉnh</div><div class="v">{pk.get('peak_vram_mb', 'N/A')} MB</div><div class="dim">Handles đỉnh: {pk.get('peak_handles', 0)}</div></div>
  <div class="kpi"><div class="dim">Tổng bài test đã chạy</div><div class="v">{len(s['suite_runs'])}</div><div class="dim">Số vòng: {s['meta'].get('cycles_done', 0)}</div></div>
</div>
<h2>Biểu đồ RAM & VRAM theo thời gian</h2>
{self._render_svg_chart(samples)}
<h2>Danh sách lỗi & xung đột</h2>
{bugs_html}
<h2>Lịch sử các bài test</h2>
<table><thead><tr><th>Giờ</th><th>Vòng</th><th>Bài test</th><th>KQ</th><th>TG</th><th>Ghi chú</th></tr></thead><tbody>{rows}</tbody></table>
</div></body></html>"""
