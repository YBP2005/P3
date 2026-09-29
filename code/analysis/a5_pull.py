# -*- coding: utf-8 -*-
"""把 A5 新家族结果从 A800 拉回本地，并与 E2 锚点家族并表。

用法：
    python a5_pull.py

落盘：
    analysis/e2xt_a800/zero/    新家族零池 CSV（e1_<fam>_<ds>_<arm>.csv）
    analysis/e2xt_a800/nonzero/ 新家族非零池 CSV
    analysis/e2xt_a800/anchors/ 从 e2_newh20 复制来的 3 个锚点家族（4 域）

只在两个目录都齐了以后才复制锚点，避免半拉状态被误判。
"""
import io
import os
import posixpath
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'<WORKDIR>\PaperB\analysis\work')
from a800_conn import connect, sh

A = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
LOCAL = r'<WORKDIR>\PaperB\analysis\e2xt_a800'
E2 = r'<WORKDIR>\PaperB\analysis\e2_newh20'
# 冻结判据点名的三个锚点家族（各取一个配置，4 域齐全）
ANCHORS = ['qwen3-vl-32b-awq', 'qwen25vl-72b-awq', 'internvl25-8b-awq']
NEW_FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
            'llava-onevision-qwen2-7b-ov']


def pull(remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    c = connect(A, tries=8, wait=8)
    try:
        sftp = c.open_sftp()
        names = sftp.listdir(remote_dir)
        names = [n for n in names if n.startswith('e1_') and n.endswith('.csv')]
        got = 0
        for n in sorted(names):
            rp = posixpath.join(remote_dir, n)
            lp = os.path.join(local_dir, n)
            rs = sftp.stat(rp).st_size
            if os.path.exists(lp) and os.path.getsize(lp) == rs:
                got += 1
                continue
            sftp.get(rp, lp)
            got += 1
        sftp.close()
    finally:
        c.close()
    return got


def fam_of(name):
    body = name[3:-4]
    for ds in ('st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench'):
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i]
    return None


def main():
    z = pull('/root/e1_results', os.path.join(LOCAL, 'zero'))
    nz = pull('/root/e1_results_nonzero', os.path.join(LOCAL, 'nonzero'))
    print('拉回：零池 %d 个、非零池 %d 个 -> %s' % (z, nz, LOCAL))

    zd = os.path.join(LOCAL, 'zero')
    fams = {}
    for n in os.listdir(zd):
        f = fam_of(n)
        if f:
            fams.setdefault(f, 0)
            fams[f] += 1
    print('零池家族：')
    for f in sorted(fams):
        print('  %-28s %d 个文件' % (f, fams[f]))
    missing = [f for f in NEW_FAMS if f not in fams]
    print('未到齐的新家族：%s' % (missing or '无'))

    if missing:
        print('⇒ 不复制锚点（等新家族齐了再并表）')
        return 2

    ad = os.path.join(LOCAL, 'anchors')
    os.makedirs(ad, exist_ok=True)
    n = 0
    for f in ANCHORS:
        for src in os.listdir(E2):
            if src.startswith('e1_' + f + '_') and src.endswith('.csv'):
                shutil.copy2(os.path.join(E2, src), os.path.join(ad, src))
                n += 1
    print('锚点复制 %d 个文件（%s）' % (n, ', '.join(ANCHORS)))
    merged = os.path.join(LOCAL, 'merged')
    os.makedirs(merged, exist_ok=True)
    for d in (zd, ad):
        for n2 in os.listdir(d):
            if n2.endswith('.csv'):
                shutil.copy2(os.path.join(d, n2), os.path.join(merged, n2))
    print('并表目录 %s：%d 个零池 CSV' % (merged, len([x for x in os.listdir(merged) if x.endswith('.csv')])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
