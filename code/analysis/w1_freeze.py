# -*- coding: utf-8 -*-
"""w1_freeze.py — 冻结 W1 预注册判据：写 md5 与冻结时间，且**拒绝覆盖**已冻结的记录。

纪律（本项目已吃过一次亏：同名覆盖毁掉过一轮材料包）：
  · 冻结记录 append-only：`w1_prereg.md5` 已存在即拒绝重写；
  · md5 由脚本计算，**不许手打进文档**（手打的哈希是不可溯源的断言）。
用法：python w1_freeze.py           # 冻结并打印
      python w1_freeze.py --check   # 只校验当前 json 是否与已冻结的一致
"""
import datetime
import hashlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, 'w1_prereg.json')
MD5F = os.path.join(HERE, 'w1_prereg.md5')


def digest(path):
    return hashlib.md5(io.open(path, 'rb').read()).hexdigest()


def main():
    cur = digest(JS)
    if '--check' in sys.argv:
        if not os.path.exists(MD5F):
            print('尚未冻结：缺少 w1_prereg.md5')
            return 1
        txt = io.open(MD5F, encoding='utf-8').read()
        frozen = txt.split()[0].strip()
        same = (frozen == cur)
        print('冻结值 %s\n当前值 %s\n%s' % (frozen, cur, '一致 ✓' if same else '**不一致 ✗ ⇒ 判据被改过，必须说明原因**'))
        return 0 if same else 1

    if os.path.exists(MD5F):
        print('已存在 w1_prereg.md5，拒绝覆盖（append-only）：')
        print(io.open(MD5F, encoding='utf-8').read().strip())
        print('当前 json md5 = %s' % cur)
        return 1
    with io.open(MD5F, 'w', encoding='utf-8', newline='\n') as f:
        f.write('%s  w1_prereg.json  frozen_at=%s  (md5 由 w1_freeze.py 计算)\n'
                % (cur, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print('已冻结：md5 %s' % cur)
    print('记录文件：%s' % MD5F)
    return 0


if __name__ == '__main__':
    sys.exit(main())
