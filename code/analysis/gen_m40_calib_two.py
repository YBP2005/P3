# -*- coding: utf-8 -*-
"""gen_m40_calib_two.py --freeze <raw.json> [--apply]

把 `m40_calib_two.py --json` 的**原始输出**冻成锚点门禁要用的 `m40_calib_two_result.json`。
只做一件事：按 `m40_calib_two.printed_block()` 的**同一函数**补出 `printed` 段，
使 §M.40.1 (iii)/(v) 正文里印出的每一个数都能追到这一次实测（`anchor_m40m41.py` 的取值宇宙）。

用法：
    python gen_m40_calib_two.py --freeze <raw.json>          # 只打印
    python gen_m40_calib_two.py --freeze <raw.json> --apply  # 写盘
"""
import argparse
import importlib.util
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'm40_calib_two_result.json')


def _load_calib():
    p = os.path.join(HERE, 'm40_calib_two.py')
    if not os.path.isfile(p):
        raise SystemExit('缺件：%s' % p)
    spec = importlib.util.spec_from_file_location('_m40c', p)
    m = importlib.util.module_from_spec(spec)
    src = io.open(p, encoding='utf-8').read()
    # 只跑到 main/run 之前：本件只需要 printed_block 这一个纯函数
    prefix = src.split('def main():')[0]
    ns = {'__name__': '_m40c_prefix', '__file__': p}
    exec(compile(prefix, p, 'exec'), ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--freeze', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if not os.path.isfile(a.freeze):
        raise SystemExit('缺件：%s' % a.freeze)
    ns = _load_calib()
    out = json.loads(io.open(a.freeze, encoding='utf-8').read())
    if 'printed' not in out:
        out['printed'] = ns['printed_block'](out)
    out['_provenance'] = {
        '_what': 'Appendix M.40.1 (iii)/(v) calibration measurements: the values as printed',
        'generator': 'm40_calib_two.py --nsplit 200',
        'freezer': 'gen_m40_calib_two.py --freeze <raw.json> --apply',
        'note': 'printed block only; no value in the raw sections is altered',
        'raw_input': os.path.basename(a.freeze),
    }
    txt = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    print('printed 段：')
    print(json.dumps(out['printed'], ensure_ascii=False, indent=1, sort_keys=True))
    if a.apply:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(txt)
        print('\n已写 %s（%d 字节）' % (OUT, len(txt.encode('utf-8'))))
    else:
        print('\n（未写盘；加 --apply）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
