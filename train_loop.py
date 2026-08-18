# -*- coding: utf-8 -*-
"""训练监督器:启动 train_fast,崩溃后自动用 --resume 续传重启。

用法:
  python train_loop.py                     # 用默认参数(见下)
  python train_loop.py --max-hours 24 --actors 5

原理:
  WDDM 下多进程共享 GPU 偶发 CUDA 错误会导致训练器崩溃。本脚本检测进程
  退出,若为非正常结束(非 max-hours 收尾)则自动重启并续传 latest.pt,
  实现无人值守的持续训练。每次崩溃最多损失 --ckpt-cycles 个 cycle。

收尾检测:日志中出现 "[完成]" 或 "[到时收尾]" 即视为正常结束,不重启。
"""

import argparse
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
TRAIN_LOG = "train.log"
ERR_LOG = "train.err.log"
DONE_MARKERS = ("[完成]", "[到时收尾]")


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def last_cycles(log_path, n=3):
    if not os.path.exists(log_path):
        return []
    lines = [l for l in open(log_path, encoding="utf-8", errors="replace")
             if l.startswith("cycle ")]
    return lines[-n:]


def should_stop(log_path):
    """True if the log shows a clean max-hours shutdown."""
    if not os.path.exists(log_path):
        return False
    tail = open(log_path, encoding="utf-8", errors="replace").read()[-4000:]
    return any(m in tail for m in DONE_MARKERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=8.0)
    ap.add_argument("--forever", action="store_true",
                    help="每轮 max-hours 结束后自动续传继续,直到手动停止(默认开)")
    ap.add_argument("--stop-after", type=int, default=0,
                    help="最多执行几轮(0=无限,配合 --forever)")
    ap.add_argument("--actors", type=int, default=5)
    ap.add_argument("--out", default="ckpts/run1")
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--micro-batch", type=int, default=64)
    ap.add_argument("--max-decisions", type=int, default=64)
    ap.add_argument("--ckpt-cycles", type=int, default=10)
    ap.add_argument("--eval-cycles", type=int, default=20)
    ap.add_argument("--snapshot-cycles", type=int, default=100)
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)
    train_log = os.path.join(out_dir, TRAIN_LOG)
    err_log = os.path.join(out_dir, ERR_LOG)

    launch = 0
    while True:
        launch += 1
        latest = os.path.join(out_dir, "latest.pt")
        cmd = [PY, "-m", "fabledan.train_fast",
               "--out", args.out,
               "--actors", str(args.actors),
               "--batch", str(args.batch),
               "--micro-batch", str(args.micro_batch),
               "--max-decisions", str(args.max_decisions),
               "--buffer", "65536",
               "--infer-device", "cuda:0",
               "--device", "cuda:0",
               "--ckpt-cycles", str(args.ckpt_cycles),
               "--eval-cycles", str(args.eval_cycles),
               "--snapshot-cycles", str(args.snapshot_cycles),
               "--max-hours", str(args.max_hours)]
        if os.path.exists(latest):
            cmd += ["--resume", os.path.relpath(latest, ROOT)]
            log("第 %d 次启动: 续传 %s" % (launch, latest))
        else:
            log("第 %d 次启动: 全新训练" % launch)

        with open(train_log, "a", encoding="utf-8") as fout, \
                open(err_log, "a", encoding="utf-8") as ferr:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=fout, stderr=ferr)
            log("PID %d 已启动 (max %s 小时)" % (proc.pid, args.max_hours))
            proc.wait()

        code = proc.returncode
        log("训练进程退出, returncode=%d" % code)

        if should_stop(train_log) and not args.forever:
            log("检测到正常收尾([到时收尾]/[完成]),且未启用 --forever,训练结束。")
            break

        if code == 0 and not should_stop(train_log):
            log("进程以 0 退出但未见收尾标记,停止(避免死循环)。")
            break

        if args.stop_after and launch >= args.stop_after:
            log("已达 --stop-after=%d 轮,训练结束。" % args.stop_after)
            break

        if should_stop(train_log):
            log("本轮 max-hours 收尾完成,自动续传开始下一轮(无限训练模式)...")
        else:
            log("检测到崩溃(可能为 WDDM CUDA 错误),30 秒后自动续传重启...")
        log("最近进度:")
        for l in last_cycles(train_log):
            log("  " + l.strip())
        time.sleep(30)


if __name__ == "__main__":
    main()