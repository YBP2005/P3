# -*- coding: utf-8 -*-
"""下载完成即启动该家族的网格：每次调用检查 DL_DONE，若某家族已下完且尚未跑，就起它的网格。

用法： python a800_chain_families.py            # 跑一轮检查（可反复调用）
各家族的额外 vLLM 参数（实测/文档要求）：
  · InternVL3.5-8B        → --trust-remote-code
  · Phi-3.5-vision        → --trust-remote-code
  · LLaVA-OneVision(-hf)  → 无（-hf 版可直接加载）
"""
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'<WORKDIR>\PaperB\analysis\work')
from a800_conn import connect, sh, launch

A = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
FAMILIES = [
    ('internvl3.5-8b', '/root/models/InternVL3_5-8B', 'InternVL3_5-8B', '--trust-remote-code'),
    ('phi-3.5-vision', '/root/models/Phi-3.5-vision-instruct', 'Phi-3.5-vision-instruct', '--trust-remote-code'),
    ('llava-ov-7b', '/root/models/llava-onevision-qwen2-7b-ov', 'llava-onevision-qwen2-7b-ov', ''),
]

c = connect(A, tries=6, wait=10)
try:
    # ★ 先上传**最新**的 a5_grid.sh —— 上一轮我改了本地脚本却忘了上传，
    #   结果 `--trust-remote-code` 被丢掉，InternVL 报 "contains custom code ... trust_remote_code=True"。
    sftp = c.open_sftp()
    sftp.put(r'<WORKDIR>\PaperB\analysis\work\a5_grid.sh', '/root/a5_grid.sh')
    sftp.close()
    print('a5_grid.sh 已上传（最新版）')

    # ★ 串行闸门：只有一张卡，两个家族同时起服会 OOM（各要 0.85 利用率）
    running = sh(c, 'ps -eo cmd | grep -c "[a]5_grid.sh"').strip()
    running = 0 if running in ('', '0') else int(running)
    print('当前正在跑的网格数：%d' % running)

    log = sh(c, 'cat /root/dl_a5.log 2>/dev/null | grep DL_DONE')
    done = [ln.split()[1] for ln in log.splitlines() if len(ln.split()) > 1]
    print('已下载完成：%s' % (done or '（暂无）'))
    launched = False
    for tag, path, name, extra in FAMILIES:
        key = [d for d in done if path.rstrip('/').split('/')[-1] in d]
        if not key:
            print('  %-22s 下载未完成 → 等下一轮' % tag)
            continue
        if sh(c, 'grep -c A5_%s_DONE /root/logs/a5_%s.log 2>/dev/null' % (tag, tag)).strip() not in ('0', ''):
            print('  %-22s 网格已完成 → 跳过' % tag)
            continue
        if running or launched:
            print('  %-22s 有网格在跑 ⇒ 本轮不启动（串行）' % tag)
            continue
        print('  %-22s 启动网格（extra=%r）' % (tag, extra))
        launch(c, 'cd /root && setsid nohup bash /root/a5_grid.sh %s %s %s %s </dev/null > /dev/null 2>&1 &'
               % (name, path, tag, extra))
        launched = True
        time.sleep(10)
        print('    已发；当前 grid 进程：' + (sh(c, 'ps -eo etime,cmd | grep "[a]5_grid.sh" | head -3') or '（无）'))
    print()
    print('=== 现状 ===')
    print('  零池文件 %s / 非零池 %s' % (sh(c, 'ls /root/e1_results | wc -l'),
                                         sh(c, 'ls /root/e1_results_nonzero | wc -l')))
    print('  磁盘 ' + sh(c, 'df -h / | tail -1'))
finally:
    c.close()
print('CHAIN_CHECK_DONE')
