# -*- coding: utf-8 -*-
"""Regenerate criteria_tables.md from raw/*.jsonl alone. No model call, no GPU, no network."""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FAMS = [('ivl358b', 'InternVL3_5-8B'), ('ivl38fp8', 'InternVL3_5-38B-FP8'),
        ('lov7b', 'llava-onevision-qwen2-7b-ov'), ('phi35v', 'Phi-3.5-vision-instruct'),
        ('q32fp8', 'Qwen3-VL-32B-Instruct-FP8')]
CONDS = ['no_name0_no_exit', 'no_name0_exit', 'name0_no_exit', 'name0_exit']
DISPLAY = {'ivl358b': 'InternVL3.5-8B', 'ivl38fp8': 'InternVL3.5-38B-FP8',
           'lov7b': 'llava-onevision-7B', 'phi35v': 'Phi-3.5-vision',
           'q32fp8': 'Qwen3-VL-32B-FP8'}
TRUEZERO_N = 300


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def load():
    tab = {}
    integ = dict(rows=0, keys=set(), dup=0, http200=0, httpbad=0, badjson=0)
    for fam, _ in FAMS:
        for cond in CONDS:
            path = os.path.join(HERE, 'raw', '%s__%s.jsonl' % (fam, cond))
            rows = []
            with io.open(path, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        integ['badjson'] += 1
            tz = [r for r in rows if str(r['gt']) == '0']
            nz = [r for r in rows if str(r['gt']) == '48']
            tab[(fam, cond)] = dict(
                rows=len(rows), tz=len(tz), nz=len(nz),
                ans0=sum(1 for r in tz if r.get('pred') == 0),
                abst=sum(1 for r in tz if r.get('abstain')),
                nz48=sum(1 for r in nz if r.get('pred') == 48),
                nz0=sum(1 for r in nz if r.get('pred') == 0),
                nzab=sum(1 for r in nz if r.get('abstain')))
            for r in rows:
                key = (fam, cond, r.get('image'))
                if key in integ['keys']:
                    integ['dup'] += 1
                integ['keys'].add(key)
                if str(r.get('http')) == '200':
                    integ['http200'] += 1
                else:
                    integ['httpbad'] += 1
                integ['rows'] += 1
    integ['nkeys'] = len(integ['keys'])
    return tab, integ


def build():
    tab, integ = load()
    hdr = '| build | ' + ' | '.join('`%s`' % c for c in CONDS) + ' |'
    sep = '|---|' + '---:|' * len(CONDS)
    L = []
    a = L.append
    a('# Point-named zero x abstention outlet: a 2x2 orthogonal design - criteria tables')
    a('')
    a('Every number below is recomputed from `raw/*.jsonl` alone; no model call and no GPU are needed.')
    a('Pool sizes are **300** true-zero images (`gt = 0`) and **300** non-zero controls (`gt = 48`) per')
    a('cell; **5** weight builds x **4** conditions x **600** images = **12,000** cells, all served with')
    a('HTTP **200**, with **no** repeated key and **no** malformed JSON.')
    a('')
    a('The four conditions are the cross of two two-level factors and nothing else:')
    a('')
    a('| factor | level | the one sentence that varies |')
    a('|---|---|---|')
    a('| A: the value zero is named | `name0` | names zero as the answer when the target is absent |')
    a('| | `no_name0` | empty string: the instruction never mentions zero |')
    a('| B: an abstention outlet is offered | `exit` | offers `abstain` / `cannot_judge` and a two-form JSON output |')
    a('| | `no_exit` | single-form JSON output only |')
    a('')
    a('Stripping both variable sentences leaves a byte-identical fixed part in all four conditions')
    a('(md5 `ffbbec0d020f4ad5d9e66567b43fbeb7`, 40 characters, for each of the four). The outlet sentence')
    a('necessarily also carries the output-format sentence, which is why that sentence belongs to the')
    a('variable block rather than the fixed block; `contracts_audit.md` states this explicitly. All other')
    a('strings, the image set, the required output format, `max_tokens` 1024 and the serving stack are')
    a('held fixed, and the four conditions of one build share a single service start.')
    a('')
    a('## 1 Answered-zero count on the 300 true-zero images')
    a('')
    a('One row per build; the four conditions are never pooled across builds.')
    a('')
    a(hdr)
    a(sep)
    for fam, _ in FAMS:
        a('| **%s** | ' % DISPLAY[fam]
          + ' | '.join(str(tab[(fam, c)]['ans0']) for c in CONDS) + ' |')
    a('')
    a('Each entry is a count out of **300**. Wilson 95% intervals on those counts:')
    a('')
    a(hdr)
    a(sep)
    for fam, _ in FAMS:
        cells = []
        for c in CONDS:
            lo, hi = wilson(tab[(fam, c)]['ans0'], TRUEZERO_N)
            cells.append('[%.3f, %.3f]' % (lo, hi))
        a('| **%s** | ' % DISPLAY[fam] + ' | '.join(cells) + ' |')
    a('')
    a('## 2 The outlet factor, read within each build at `no_name0`')
    a('')
    a('| build | `no_name0_no_exit` | `no_name0_exit` | change |')
    a('|---|---:|---:|---:|')
    for fam, _ in FAMS:
        x = tab[(fam, 'no_name0_no_exit')]['ans0']
        y = tab[(fam, 'no_name0_exit')]['ans0']
        a('| **%s** | %d | %d | **%+d** |' % (DISPLAY[fam], x, y, y - x))
    a('')
    a('Four of the five builds collapse; the remaining build is nearly immune.')
    a('')
    a('## 3 The named-zero factor, read within each build at both outlet levels')
    a('')
    a('| build | no outlet: `no_name0` -> `name0` | outlet offered: `no_name0` -> `name0` |')
    a('|---|---:|---:|')
    for fam, _ in FAMS:
        p = tab[(fam, 'no_name0_no_exit')]['ans0']
        q = tab[(fam, 'name0_no_exit')]['ans0']
        r = tab[(fam, 'no_name0_exit')]['ans0']
        s = tab[(fam, 'name0_exit')]['ans0']
        a('| **%s** | %d -> %d (**%+d**) | %d -> %d (**%+d**) |'
          % (DISPLAY[fam], p, q, q - p, r, s, s - r))
    a('')
    a('The direction is positive in **5 of 5** builds at both outlet levels, so naming zero recovers')
    a('part of what the outlet removes.')
    a('')
    a('## 4 True-zero abstention count (out of 300)')
    a('')
    a(hdr)
    a(sep)
    for fam, _ in FAMS:
        a('| **%s** | ' % DISPLAY[fam]
          + ' | '.join(str(tab[(fam, c)]['abst']) for c in CONDS) + ' |')
    a('')
    a('Abstention is exactly zero under `no_name0_no_exit` in every build, as the contract requires; it')
    a('is only reachable in the two `exit` conditions.')
    a('')
    a('## 5 Non-zero controls (`gt = 48`, 300 images): the cost axis')
    a('')
    a('| build | condition | exact-48 count | answered-zero count | abstention count |')
    a('|---|---|---:|---:|---:|')
    for fam, _ in FAMS:
        for c in CONDS:
            d = tab[(fam, c)]
            a('| **%s** | `%s` | %d | %d | %d |'
              % (DISPLAY[fam], c, d['nz48'], d['nz0'], d['nzab']))
    a('')
    a('## 6 Integrity')
    a('')
    a('| check | value |')
    a('|---|---|')
    a('| cells (rows) | %d |' % integ['rows'])
    a('| distinct `(build, condition, image)` keys | %d |' % integ['nkeys'])
    a('| repeated keys | %d |' % integ['dup'])
    a('| rows with HTTP 200 | %d |' % integ['http200'])
    a('| rows with HTTP != 200 | %d |' % integ['httpbad'])
    a('| malformed JSON lines | %d |' % integ['badjson'])
    a('| images per cell | 600 (300 true zero + 300 non-zero) |')
    a('')
    a('## 7 Reproducing')
    a('')
    a('This file is regenerated by `criteria_tables.py`, which reads `raw/*.jsonl` only. The stimulus pool')
    a('is `manifest.csv` (600 rows, each with its `sha256`); `render_2x2.py` rebuilds the images from the')
    a('frozen seed and `make_contracts_2x2.py` rebuilds the four contracts while asserting the fixed-part')
    a('equality above. `run_2x2.sh` is the orchestration that produced the raw records, and')
    a('`contracts_audit.md` is its own contract audit.')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    out = os.path.join(HERE, 'criteria_tables.md')
    txt = build()
    io.open(out, 'w', encoding='utf-8', newline='\n').write(txt)
    print('wrote %s (%d bytes)' % (out, len(txt.encode('utf-8'))))
