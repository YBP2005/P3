#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1f_probe.py —— 锚定阶梯（mention5/50/800）的采集器：薄包装，复用 p1d_probe 的实现。"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('P1_FROZEN', '/root/19e_probe_multi.py')
os.environ.setdefault('P1D_PROMPTS', os.path.join(HERE, 'p1f_prompts.json'))
EXTRA = os.environ['P1D_PROMPTS']
EXTRA_MD5 = 'ceaa67e4a59768bf61621b61235ebff8'   # p1f_prompts.json FULL md5

spec = importlib.util.spec_from_file_location('p1dmod', os.path.join(HERE, 'p1d_probe.py'))
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)
pd.EXTRA = EXTRA
pd.EXTRA_MD5 = EXTRA_MD5
print('  p1f_probe：提示词来源 %s（期望 md5 %s…）' % (EXTRA, EXTRA_MD5[:12]))
if not os.path.exists(EXTRA):
    raise SystemExit('!! 缺 %s' % EXTRA)

if __name__ == '__main__':
    raise SystemExit(pd.main())
