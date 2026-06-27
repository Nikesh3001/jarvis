#!/usr/bin/env python3
"""
FRIDAY Pentest Report Generator — Aggregates scan results into
professional HTML/PDF reports.

Usage:
  from tools.report import PentestReport
  report = PentestReport("My Pentest", targets=["example.com"])
  report.add_result("nmap", nmap_output)
  report.add_result("nikto", nikto_output)
  report.generate()  # -> writes HTML (+ PDF if weasyprint installed)
"""

import html as _html
import os
import secrets
from datetime import datetime, timezone


def _esc(text):
    """Escape text for safe HTML embedding."""
    return _html.escape(str(text))


def _severity_from_text(text):
    """Heuristic: extract severity rating from scan output text."""
    lower = text.lower()
    if any(w in lower for w in ["critical", "rce", "remote code execution", "sql injection"]):
        return "critical"
    if any(w in lower for w in ["high", "xss", "cross-site", "directory traversal"]):
        return "high"
    if any(w in lower for w in ["medium", "moderate", "misconfiguration", "missing header"]):
        return "medium"
    if any(w in lower for w in ["low"]):
        return "low"
    if any(w in lower for w in ["informational", "info"]):
        return "info"
    return "info"


SEVERITY_COLORS = {
    "critical": "#dc2626",
    "high":     "#ea580c",
    "medium":   "#d97706",
    "low":      "#2563eb",
    "info":     "#6b7280",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class PentestReport:
    """Collects scan results and generates an HTML (optionally PDF) report."""

    def __init__(self, title="Penetration Test Report", targets=None, tester="FRIDAY Cyber Console"):
        self.title = title
        self.targets = targets or []
        self.tester = tester
        self.start_time = datetime.now(timezone.utc)
        self.results = []   # list of {tool, target, output, severity, timestamp}
        self._report_id = secrets.token_hex(8)

    # ── Add results ────────────────────────────────────────────────────

    def add_result(self, tool, output, target=None, severity=None):
        """Append a scan result. Severity auto-detected if omitted."""
        if severity is None:
            severity = _severity_from_text(output)
        self.results.append({
            "tool": tool,
            "target": target or self.targets[0] if self.targets else "N/A",
            "output": output,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Summary statistics ─────────────────────────────────────────────

    def _summary(self):
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for r in self.results:
            s = r["severity"]
            if s in counts:
                counts[s] += 1
        return counts

    def _risk_label(self, counts):
        if counts["critical"] > 0:
            return "CRITICAL", "#dc2626"
        if counts["high"] > 0:
            return "HIGH", "#ea580c"
        if counts["medium"] > 0:
            return "MEDIUM", "#d97706"
        if counts["low"] > 0:
            return "LOW", "#2563eb"
        return "INFORMATIONAL", "#6b7280"

    # ── HTML generation ────────────────────────────────────────────────

    def generate_html(self):
        """Return the full HTML report as a string."""
        counts = self._summary()
        risk_label, risk_color = self._risk_label(counts)
        total = sum(counts.values())
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        duration_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

        # Group results by tool
        by_tool = {}
        for r in self.results:
            by_tool.setdefault(r["tool"], []).append(r)

        severity_bars = ""
        for sev in ("critical", "high", "medium", "low", "info"):
            cnt = counts[sev]
            if cnt == 0:
                continue
            pct = max(cnt / max(total, 1) * 100, 4)
            severity_bars += (
                f'<div style="display:flex;align-items:center;margin:6px 0">'
                f'<span style="width:80px;font-size:13px;color:{SEVERITY_COLORS[sev]};font-weight:700;text-transform:uppercase">{sev}</span>'
                f'<div style="flex:1;background:#f3f4f6;border-radius:4px;height:22px;margin:0 12px">'
                f'<div style="width:{pct:.0f}%;background:{SEVERITY_COLORS[sev]};height:100%;border-radius:4px"></div></div>'
                f'<span style="width:30px;text-align:right;font-size:13px;font-weight:600">{cnt}</span></div>'
            )

        # Findings table rows
        findings_rows = ""
        sorted_results = sorted(self.results, key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
        for i, r in enumerate(sorted_results):
            sev = r["severity"]
            findings_rows += (
                f'<tr>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #e5e7eb">{i + 1}</td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #e5e7eb"><span style="'
                f'background:{SEVERITY_COLORS.get(sev, "#6b7280")};color:#fff;padding:2px 10px;'
                f'border-radius:4px;font-size:12px;font-weight:700;text-transform:uppercase">{_esc(sev)}</span></td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-weight:600">{_esc(r["tool"])}</td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #e5e7eb">{_esc(r["target"])}</td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280">{_esc(r["timestamp"][:19])}</td>'
                f'</tr>'
            )

        # Tool-specific detail sections
        tool_sections = ""
        for tool_name, tool_results in by_tool.items():
            tool_sections += f'<h2 style="margin:30px 0 14px;padding-bottom:8px;border-bottom:2px solid #e5e7eb;color:#111827">📊 {_esc(tool_name)} Results</h2>'
            for tr in tool_results:
                output_escaped = _esc(tr["output"])
                tool_sections += (
                    f'<div style="margin:10px 0;padding:16px;background:#f9fafb;'
                    f'border:1px solid #e5e7eb;border-radius:8px">'
                    f'<div style="margin-bottom:8px;font-size:13px;color:#6b7280">Target: <b>{_esc(tr["target"])}</b> — {tr["timestamp"][:19]}</div>'
                    f'<pre style="margin:0;white-space:pre-wrap;word-wrap:break-word;font-size:13px;'
                    f'line-height:1.5;color:#374151;font-family:\'Cascadia Code\',\'Fira Code\',monospace">{output_escaped}</pre>'
                    f'</div>'
                )

        # Recommendations
        recs = self._generate_recommendations(counts)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(self.title)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1f2937; line-height: 1.6; background: #fff; }}
  @media print {{
    body {{ font-size: 11pt; }}
    .page-break {{ page-break-before: always; }}
    pre {{ font-size: 9pt; }}
  }}
</style>
</head>
<body>

<!-- ─── COVER ──────────────────────────────────────────────────── -->
<div style="min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;
            background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#334155 100%);color:#fff;padding:60px 40px;text-align:center">
  <div style="font-size:42px;margin-bottom:8px">🛡️</div>
  <h1 style="font-size:36px;font-weight:800;margin-bottom:12px;letter-spacing:-0.5px">{_esc(self.title)}</h1>
  <p style="font-size:16px;color:#94a3b8;margin-bottom:40px">Automated Security Assessment</p>
  <div style="display:flex;gap:30px;font-size:14px;color:#cbd5e1">
    <div><span style="color:#64748b">Tester:</span> <b>{_esc(self.tester)}</b></div>
    <div><span style="color:#64748b">Date:</span> <b>{self.start_time.strftime('%Y-%m-%d')}</b></div>
    <div><span style="color:#64748b">Targets:</span> <b>{len(self.targets)}</b></div>
  </div>
  <div style="margin-top:30px;padding:14px 32px;background:{risk_color};border-radius:8px;
              font-size:18px;font-weight:800;letter-spacing:1px">RISK: {risk_label}</div>
</div>

<!-- ─── EXECUTIVE SUMMARY ──────────────────────────────────────── -->
<div style="padding:50px 60px;max-width:900px;margin:0 auto">
  <h2 style="font-size:24px;font-weight:700;margin-bottom:20px;color:#111827">Executive Summary</h2>
  <p style="color:#4b5563;margin-bottom:24px">
    This automated penetration test assessed <b>{len(self.targets)} target(s)</b> using
    <b>{len(by_tool)} security tool(s)</b>, identifying <b>{total} finding(s)</b> across all severity levels.
    The overall risk rating is <b style="color:{risk_color}">{risk_label}</b>.
  </p>

  <div style="display:flex;gap:20px;margin:20px 0 30px">
    <div style="flex:1;padding:20px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;text-align:center">
      <div style="font-size:36px;font-weight:800;color:{risk_color}">{total}</div>
      <div style="font-size:13px;color:#6b7280;margin-top:4px">Total Findings</div>
    </div>
    <div style="flex:1;padding:20px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;text-align:center">
      <div style="font-size:36px;font-weight:800;color:#111827">{len(by_tool)}</div>
      <div style="font-size:13px;color:#6b7280;margin-top:4px">Tools Used</div>
    </div>
    <div style="flex:1;padding:20px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;text-align:center">
      <div style="font-size:36px;font-weight:800;color:#111827">{duration_str}</div>
      <div style="font-size:13px;color:#6b7280;margin-top:4px">Duration</div>
    </div>
  </div>

  <h3 style="font-size:16px;font-weight:600;margin:18px 0 10px;color:#374151">Severity Breakdown</h3>
  {severity_bars}

  <h3 style="font-size:16px;font-weight:600;margin:24px 0 10px;color:#374151">Targets</h3>
  <ul style="margin:0 0 0 20px;color:#4b5563">
    {"".join(f'<li style="margin:4px 0"><code style="background:#f3f4f6;padding:2px 8px;border-radius:4px">{_esc(t)}</code></li>' for t in self.targets)}
  </ul>
</div>

<!-- ─── FINDINGS TABLE ─────────────────────────────────────────── -->
<div class="page-break" style="padding:50px 60px;max-width:900px;margin:0 auto">
  <h2 style="font-size:24px;font-weight:700;margin-bottom:20px;color:#111827">Findings Overview</h2>
  <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
    <thead>
      <tr style="background:#f9fafb;text-align:left">
        <th style="padding:12px 14px;border-bottom:2px solid #e5e7eb;font-size:12px;text-transform:uppercase;color:#6b7280">#</th>
        <th style="padding:12px 14px;border-bottom:2px solid #e5e7eb;font-size:12px;text-transform:uppercase;color:#6b7280">Severity</th>
        <th style="padding:12px 14px;border-bottom:2px solid #e5e7eb;font-size:12px;text-transform:uppercase;color:#6b7280">Tool</th>
        <th style="padding:12px 14px;border-bottom:2px solid #e5e7eb;font-size:12px;text-transform:uppercase;color:#6b7280">Target</th>
        <th style="padding:12px 14px;border-bottom:2px solid #e5e7eb;font-size:12px;text-transform:uppercase;color:#6b7280">Timestamp</th>
      </tr>
    </thead>
    <tbody>
      {findings_rows if findings_rows else '<tr><td colspan="5" style="padding:20px;text-align:center;color:#9ca3af">No findings recorded</td></tr>'}
    </tbody>
  </table>
</div>

<!-- ─── DETAILED RESULTS ───────────────────────────────────────── -->
<div class="page-break" style="padding:50px 60px;max-width:900px;margin:0 auto">
  <h2 style="font-size:24px;font-weight:700;margin-bottom:20px;color:#111827">Detailed Scan Results</h2>
  {tool_sections if tool_sections else '<p style="color:#9ca3af">No scan results to display.</p>'}
</div>

<!-- ─── RECOMMENDATIONS ────────────────────────────────────────── -->
<div class="page-break" style="padding:50px 60px;max-width:900px;margin:0 auto">
  <h2 style="font-size:24px;font-weight:700;margin-bottom:20px;color:#111827">Recommendations</h2>
  <ol style="margin:0 0 0 20px;color:#4b5563">
    {"".join(f'<li style="margin:10px 0;padding:12px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px">{_esc(r)}</li>' for r in recs)}
  </ol>
</div>

<!-- ─── FOOTER ─────────────────────────────────────────────────── -->
<div style="padding:30px 60px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px;text-align:center">
  Generated by <b>FRIDAY Cyber Console</b> v3.5.0 — {_esc(self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC'))}
  — Report ID: {_esc(self._report_id)}
</div>

</body>
</html>"""
        return html

    # ── Recommendations engine ─────────────────────────────────────────

    def _generate_recommendations(self, counts):
        recs = []
        if counts["critical"] > 0:
            recs.append("Immediately remediate all CRITICAL findings — these represent exploitable vulnerabilities that could lead to full system compromise.")
        if counts["high"] > 0:
            recs.append("Address HIGH severity findings within 24-48 hours — these are actively exploitable or expose sensitive data.")
        if counts["medium"] > 0:
            recs.append("Remediate MEDIUM findings within 1-2 weeks — these are configuration issues or weak spots that increase attack surface.")
        if counts["low"] > 0:
            recs.append("Schedule LOW severity fixes during regular maintenance windows.")
        if counts["info"] > 0:
            recs.append("Review informational findings for additional context — some may indicate further investigation is needed.")

        # Tool-specific recommendations
        tool_names = {r["tool"] for r in self.results}
        if "nmap" in tool_names:
            recs.append("Review open ports and services. Disable or restrict access to any non-essential services.")
        if "nikto" in tool_names:
            recs.append("Address web server misconfigurations identified by Nikto — keep web server software updated.")
        if "sqlmap" in tool_names:
            recs.append("SQL injection was tested — ensure all database queries use parameterized statements and input validation.")
        if "gobuster" in tool_names or "ffuf" in tool_names:
            recs.append("Restrict access to discovered directories/files. Remove or protect sensitive paths exposed during directory brute-forcing.")
        if "hydra" in tool_names:
            recs.append("Brute-force testing was performed — enforce account lockout policies, rate limiting, and strong password requirements.")
        if "headers" in tool_names or "web_headers_check" in tool_names:
            recs.append("Implement all recommended HTTP security headers (HSTS, CSP, X-Frame-Options, etc.).")
        if "ssl" in tool_names or "ssl_check" in tool_names:
            recs.append("Update TLS configuration to use only TLS 1.2+ with strong cipher suites. Remove support for deprecated protocols.")

        if not recs:
            recs.append("No specific findings to recommend on — continue periodic security assessments.")

        recs.append("Conduct regular penetration tests and vulnerability scans on a quarterly basis.")
        recs.append("Implement a vulnerability management program with tracked remediation timelines.")
        return recs

    # ── File output ────────────────────────────────────────────────────

    def generate(self, output_dir=None, filename=None):
        """Write HTML report to disk. Returns the file path.

        If weasyprint is available, also generates a PDF.
        """
        if output_dir is None:
            output_dir = os.path.join(os.path.expanduser("~"), "friday_reports")
        os.makedirs(output_dir, exist_ok=True)

        if filename is None:
            ts = self.start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"pentest_report_{ts}_{self._report_id}"

        html_path = os.path.join(output_dir, f"{filename}.html")
        html_content = self.generate_html()

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        result = {"html": html_path}

        # Attempt PDF generation
        pdf_path = os.path.join(output_dir, f"{filename}.pdf")
        try:
            from weasyprint import HTML
            HTML(string=html_content).write_pdf(pdf_path)
            result["pdf"] = pdf_path
        except ImportError:
            result["pdf"] = None
            result["pdf_note"] = "weasyprint not installed — PDF skipped. Install: pip install weasyprint"
        except Exception as e:
            result["pdf"] = None
            result["pdf_note"] = f"PDF generation failed: {e}"

        return result
