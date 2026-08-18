# -*- coding: utf-8 -*-
"""训练监控:实时解析 train_fast 日志,终端视图 + 生成离线 HTML 图表。

用法:
  python monitor.py                       # 查看最新日志摘要(一次性)
  python monitor.py --watch               # 持续刷新终端视图(每 3 秒)
  python monitor.py --html                # 生成 ckpts/<run>/monitor.html 图表
  python monitor.py --log ckpts/run1/train.log --html

日志格式由 train_fast.py 输出:
  cycle N  samples X  loss L  collect Xs train Ys  Z samples/s
  eval vs rule: 21.0%   vs snapshot(-500 cyc): 33.0%
"""

import argparse
import os
import re
import time

CYCLE_RE = re.compile(
    r"cycle (\d+)\s+samples ([\d,]+)\s+loss ([\d.]+)\s+"
    r"collect ([\d.]+)s train ([\d.]+)s\s+([\d.]+) samples/s")
EVAL_RE = re.compile(r"eval vs rule: ([\d.]+)%\s*(?:vs snapshot.*?([\d.]+)%)?")


def parse_log(path):
    """Parse the log into a list of per-cycle records + eval marks."""
    cycles, evals = [], []
    if not os.path.exists(path):
        return cycles, evals
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = CYCLE_RE.search(line)
            if m:
                cycles.append({
                    "cycle": int(m.group(1)),
                    "samples": int(m.group(2).replace(",", "")),
                    "loss": float(m.group(3)),
                    "collect": float(m.group(4)),
                    "train": float(m.group(5)),
                    "sps": float(m.group(6)),
                })
                continue
            m = EVAL_RE.search(line)
            if m:
                evals.append({
                    "cycle": cycles[-1]["cycle"] if cycles else 0,
                    "rule": float(m.group(1)),
                    "snapshot": float(m.group(2)) if m.group(2) else None,
                })
    return cycles, evals


def terminal_view(cycles, evals, path):
    print("=" * 66)
    print("FableDan 训练监控  |  %s" % path)
    print("=" * 66)
    if not cycles:
        print("暂无 cycle 数据(日志为空或尚未开始训练)。")
        return
    last = cycles[-1]
    print("当前进度: cycle %d | 累计样本 %s | 吞吐 %.0f 样本/s"
          % (last["cycle"], f"{last['samples']:,}", last["sps"]))
    print("最近 loss: ", end="")
    tail = [c["loss"] for c in cycles[-10:]]
    print(" -> ".join("%.3f" % v for v in tail))
    if evals:
        e = evals[-1]
        print("最新评估 vs rule: %.1f%%" % e["rule"],
              end="")
        if e["snapshot"] is not None:
            print(" | vs snapshot: %.1f%%" % e["snapshot"])
        else:
            print()
        print("评估历史: " + " -> ".join("%.0f%%" % v["rule"] for v in evals))
    # Progress bars for loss trend (lower loss = longer bar)
    if len(cycles) >= 2:
        losses = [c["loss"] for c in cycles]
        lo, hi = min(losses), max(losses)
        span = (hi - lo) or 1e-9
        print("loss 曲线(最近 30 个 cycle,左=新 右=旧):")
        for v in losses[-30:]:
            width = int((hi - v) / span * 20) + 1
            print("  %7.3f |%s%s|" % (v, "#" * width, " " * (20 - width)))
    print("-" * 66)


def build_html(cycles, evals, path, out_html, refresh_seconds=10):
    if not cycles:
        print("没有可绘制的数据。")
        return
    xs = [c["cycle"] for c in cycles]
    losses = [c["loss"] for c in cycles]
    sps = [c["sps"] for c in cycles]
    eval_cycles = [e["cycle"] for e in evals]
    eval_rules = [e["rule"] for e in evals]

    # Simple inline SVG line chart (no CDN, offline-friendly)
    W, H, PAD = 900, 260, 40
    def poly(points, w, h, lo, hi):
        span = (hi - lo) or 1e-9
        return " ".join(
            "%.1f,%.1f" % (
                PAD + (x - min(xs)) / max(1, max(xs) - min(xs)) * (w - 2 * PAD),
                h - PAD - (v - lo) / span * (h - 2 * PAD),
            )
            for x, v in points)

    def chart(title, points, lo, hi, color, extra=""):
        p = poly(points, W, H, lo, hi)
        lines = ['<h3>%s</h3>' % title,
                 '<svg width="%d" height="%d" style="background:#0d1b14;border-radius:10px">'
                 % (W, H),
                 '<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (p, color)]
        for lbl, v in (("max", hi), ("min", lo)):
            y = H - PAD - (v - lo) / ((hi - lo) or 1e-9) * (H - 2 * PAD)
            lines.append('<text x="%d" y="%.1f" fill="#8a8a8a" font-size="11">%s %.2f</text>'
                         % (W - PAD + 6, y + 4, lbl, v))
        lines.append('</svg>')
        return "\n".join(lines)

    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>FableDan 训练监控</title>
<meta http-equiv="refresh" content="%(refresh)s">
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif;
     background:#0b0f0d;color:#e8e8e8;padding:24px;max-width:960px;margin:auto}
h1{font-size:22px;color:#e8b930} h3{color:#9adc8e;margin:18px 0 8px}
.stat{display:flex;gap:28px;flex-wrap:wrap;margin:12px 0 20px}
.card{background:#14241b;border:1px solid #2a4a35;border-radius:12px;padding:12px 18px;min-width:130px}
.card .k{font-size:12px;color:#8a9a8f} .card .v{font-size:20px;font-weight:700;color:#fff;margin-top:4px}
table{border-collapse:collapse;width:100%%;font-size:13px}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid #1e3327}
th{color:#e8b930} td:first-child,th:first-child{text-align:left}
tr:hover td{background:#16261c}
.up{color:#7ecb7e} .down{color:#ff8a80}
</style></head><body>
<h1>FableDan 掼蛋 AI · 训练监控</h1>
<p style="color:#8a8a8a">日志: %(path)s</p>
<div class="stat">
  <div class="card"><div class="k">当前 cycle</div><div class="v">%(cycle)d</div></div>
  <div class="card"><div class="k">累计样本</div><div class="v">%(samples)s</div></div>
  <div class="card"><div class="k">最新 loss</div><div class="v">%(loss)s</div></div>
  <div class="card"><div class="k">吞吐</div><div class="v">%(sps)s /s</div></div>
  <div class="card"><div class="k">vs rule 最新</div><div class="v">%(rule)s%%</div></div>
</div>
%(loss_chart)s
%(sps_chart)s
%(eval_chart)s
<h3>最近 15 个 cycle</h3>
<table><tr><th>cycle</th><th>样本</th><th>loss</th><th>Δloss</th><th>collect(s)</th><th>train(s)</th><th>样本/s</th></tr>
%(rows)s
</table>
<p style="color:#555;margin-top:20px">刷新页面即可更新。生成时间: %(time)s</p>
</body></html>"""

    rows = []
    prev_loss = None
    for c in cycles[-15:]:
        delta = ""
        if prev_loss is not None:
            d = c["loss"] - prev_loss
            cls = "up" if d < 0 else "down"
            delta = '<span class="%s">%+.4f</span>' % (cls, d)
        rows.append(
            "<tr><td>%d</td><td>%s</td><td>%.4f</td><td>%s</td><td>%.1f</td>"
            "<td>%.1f</td><td>%.0f</td></tr>"
            % (c["cycle"], f"{c['samples']:,}", c["loss"], delta,
               c["collect"], c["train"], c["sps"]))
        prev_loss = c["loss"]

    loss_chart = chart("loss 曲线(越低越好)", list(zip(xs, losses)),
                       min(losses), max(losses), "#e8b930")
    sps_chart = chart("训练吞吐(样本/秒)", list(zip(xs, sps)),
                      min(sps), max(sps), "#4fc3f7")
    eval_chart = ""
    if evals:
        eval_chart = chart("vs rule 胜率(%)", list(zip(eval_cycles, eval_rules)),
                           min(eval_rules), max(eval_rules), "#7ecb7e")

    out = html % {
        "path": path,
        "refresh": refresh_seconds,
        "cycle": cycles[-1]["cycle"],
        "samples": f"{cycles[-1]['samples']:,}",
        "loss": "%.4f" % cycles[-1]["loss"],
        "sps": "%.0f" % cycles[-1]["sps"],
        "rule": ("%.1f" % evals[-1]["rule"]) if evals else "—",
        "loss_chart": loss_chart,
        "sps_chart": sps_chart,
        "eval_chart": eval_chart,
        "rows": "\n".join(rows),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(out)
    print("图表已生成: %s" % out_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="ckpts/run1/train.log")
    ap.add_argument("--watch", action="store_true", help="持续刷新终端视图")
    ap.add_argument("--html", action="store_true", help="生成 HTML 图表")
    ap.add_argument("--serve", action="store_true",
                    help="后台持续刷新 HTML 图表(配合页面自动刷新)")
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--refresh", type=int, default=10,
                    help="HTML 页面自动刷新间隔(秒)")
    args = ap.parse_args()

    if args.watch:
        last_line = 0
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                cycles, evals = parse_log(args.log)
                terminal_view(cycles, evals, args.log)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n退出监控。")
        return

    if args.serve:
        # 持续重新生成 HTML 图表,配合 <meta refresh> 让浏览器自动更新。
        run_dir = os.path.dirname(args.log) or "ckpts/run1"
        out_html = os.path.join(run_dir, "monitor.html")
        print("持续刷新监控图表: %s (每 %ds)" % (out_html, args.refresh))
        try:
            while True:
                cycles, evals = parse_log(args.log)
                build_html(cycles, evals, args.log, out_html, args.refresh)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n退出监控服务。")
        return

    cycles, evals = parse_log(args.log)
    terminal_view(cycles, evals, args.log)
    if args.html:
        run_dir = os.path.dirname(args.log) or "ckpts/run1"
        out_html = os.path.join(run_dir, "monitor.html")
        build_html(cycles, evals, args.log, out_html, args.refresh)


if __name__ == "__main__":
    main()