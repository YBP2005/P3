#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1e_probe.py —— placebo100 探索臂的采集器（**薄包装**，复用 p1d_probe 的全部实现）。

为什么是包装而不是复制：`p1d_probe.py` 里已经有"冻结断言 + 泛化对象名词适配 + 交叉自检 + CSV 续跑"
这一整套；复制一份会让两条链各自漂移。这里只做一件事：把提示词来源与期望 md5 换成 p1e 的，
然后调用 p1d 的 main。**不改 p1d 的任何文件**（它此刻正在跑其余家族）。
"""
import hashlib
import importlib.util
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('P1_FROZEN', '/root/19e_probe_multi.py')
os.environ.setdefault('P1D_PROMPTS', os.path.join(HERE, 'p1e_prompts.json'))
EXTRA = os.environ['P1D_PROMPTS']
EXTRA_MD5 = '24e3af806db3eee7f216deada70e62b9'   # p1e_prompts.json 的 FULL md5

spec = importlib.util.spec_from_file_location('p1dmod', os.path.join(HERE, 'p1d_probe.py'))
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)
pd.EXTRA = EXTRA
pd.EXTRA_MD5 = EXTRA_MD5
print('  p1e_probe：提示词来源 %s（期望 md5 %s…）' % (EXTRA, EXTRA_MD5[:12]))
if not os.path.exists(EXTRA):
    raise SystemExit('!! 缺 %s' % EXTRA)

if __name__ == '__main__':
    raise SystemExit(pd.main())
