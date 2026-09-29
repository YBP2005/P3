# -*- coding: utf-8 -*-
"""w1_monitor.py — 后台监视 W1 全流水线，直到出现 W1_RECOVER3_DONE（或超时/异常终止）。

为什么要它：整条链由 6 段脚本在同一张卡上串行排队，预计 4–6 小时。人工反复轮询既浪费上下文，
又容易在"看起来没动静"时误判。本脚本每 5 分钟取一次状态，**只在状态变化时打印**，
并在流水线结束（或某段报致命错）时退出，从而让"完成/卡住"成为一个可被通知的事件。
用法：python w1_monitor.py [--max-hours 8]
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
# ★ 2026-09-23 修：后台作业里 stdout 是管道 ⇒ Python 默认**块缓冲**（约 8 KB），
#   于是"没有新输出"往往是"没刷出来"，而不是真的没变化（我因此白等过一轮 30 分钟）。
#   line_buffering=True 让每行立即写出，监视才有意义。
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')

SECTIONS = ['w1_dl', 'w1_run', 'w1_dl2', 'w1_recover', 'w1_fsc', 'w1_recover2', 'w1_fsc_late', 'w1_recover3']
DONE_MARKS = ['W1_PANEL_DONE', 'W1_RECOVER_DONE', 'W1_FSC_DONE', 'W1_RECOVER2_DONE',
              'W1_FSC_LATE_DONE', 'W1_RECOVER3_DONE', 'W1_HOSTED_DONE']
CMD = (
    'for f in %s; do printf "%%s|" "$f"; tail -1 /root/logs/$f.log 2>/dev/null || printf "(无)"; printf "\\n"; done; '
    'echo "---MARKS"; grep -l -E "%s" /root/logs/*.log 2>/dev/null; '
    'echo "---COUNTS"; echo "zero=$(ls /root/w1_results/zero 2>/dev/null | wc -l) '
    'nonzero=$(ls /root/w1_results/nonzero 2>/dev/null | wc -l) '
    'smoke=$(ls /root/w1_results/smoke 2>/dev/null | wc -l) '
    'fsc=$(ls /root/w1_results/fsc 2>/dev/null | wc -l) '
    'hosted=$(ls /root/w1_results/hosted 2>/dev/null | wc -l)"; '
    'echo "---GPU"; nvidia-smi --query-gpu=memory.used --format=csv,noheader; '
    'echo "---ALIVE"; ps -eo pid,cmd | grep -c "[w]1_"'
    % (' '.join(SECTIONS), '|'.join(DONE_MARKS)))


def main():
    maxh = 8.0
    if '--max-hours' in sys.argv:
        maxh = float(sys.argv[sys.argv.index('--max-hours') + 1])
    t0 = time.time()
    last = None
    last_print = time.time()
    fails = 0
    while True:
        if (time.time() - t0) / 3600.0 > maxh:
            print('[monitor] 达到最大监视时长 %.1f h，退出' % maxh)
            return 0
        try:
            c = connect(HOST, tries=3, wait=10)
            out = sh(c, CMD, t=90)
            c.close()
            fails = 0
        except Exception as ex:
            fails += 1
            print('[monitor] 连接失败 %d 次：%s' % (fails, str(ex)[:100]))
            if fails >= 12:
                print('[monitor] 连续连接失败过多，退出')
                return 1
            time.sleep(300)
            continue
        if out != last:
            print('=' * 70)
            print('[monitor] %s' % time.strftime('%H:%M:%S'))
            print(out)
            last = out
            last_print = time.time()
        elif time.time() - last_print > 1800:
            # ★ 心跳：状态"没变化"本身也是信息——若某处卡住（下载停滞、队列等一个永不到来的标记），
            #   只在变化时打印会让我迟迟不知道。故每 30 分钟无论如何都打一次。
            print('[monitor] 心跳 %s（状态较上次无变化；已运行 %.1f h）'
                  % (time.strftime('%H:%M:%S'), (time.time() - t0) / 3600.0))
            print(out)
            last_print = time.time()
        marks = [m for m in DONE_MARKS if m in out]
        if 'W1_RECOVER3_DONE' in marks:
            print('[monitor] 全流水线完成（W1_RECOVER3_DONE）')
            return 0
        time.sleep(300)


if __name__ == '__main__':
    sys.exit(main())
