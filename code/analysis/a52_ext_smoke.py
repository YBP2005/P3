# -*- coding: utf-8 -*-
"""A5-2 ext smoke probe.

Reuses the FROZEN module /root/a52/a52_probe.py for prompts, parser and JPEG b64
encoding, so the stimulus + prompt text are byte-identical to the frozen set.
Adds what the frozen probe does not record: output (completion) token counts,
and a clean single-stream (workers=1) latency series next to the official
workers=4 series.

Phases:
  warmup : 1 call, discarded from the stats
  seq    : N_SEQ calls, one at a time   -> true per-call latency
  conc   : N_CONC calls, WORKERS threads -> official A5-2 serving regime
"""
import os, sys, io, json, time, csv, urllib.request, urllib.error, statistics
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/root/a52')
import a52_probe as P                      # frozen probe module
from PIL import Image

PORT = int(os.environ['PORT'])
SERVED = os.environ['SERVED']
OUTDIR = os.environ.get('OUTDIR', '/root/a52_ext_smoke')
TAG = os.environ.get('TAG', 'b0')
GRID = '/root/a52/stim'
API = 'http://127.0.0.1:%d/v1/chat/completions' % PORT
N_SEQ = int(os.environ.get('N_SEQ', '15'))
N_CONC = int(os.environ.get('N_CONC', '24'))
WORKERS = int(os.environ.get('WORKERS', '4'))
LOAD_S = os.environ.get('LOAD_S', '')
MAXTOK = 128
os.makedirs(OUTDIR, exist_ok=True)


def call_once(rec):
    t0 = time.time()
    rel = rec.get('img') or ('images/%s.png' % rec['layout_id'])
    im = Image.open(os.path.join(GRID, rel)).convert('RGB')
    b64 = P.b64_of(im)
    t_enc = time.time() - t0
    payload = {'model': SERVED, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': PROMPT}]}], 'temperature': 0.0, 'max_tokens': MAXTOK}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer dummy'})
    last = None
    for a in range(5):
        try:
            th = time.time()
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read().decode())
            t_http = time.time() - th
            u = j.get('usage') or {}
            return {'item': rec['layout_id'], 'latency_s': time.time() - t0, 'http_s': t_http,
                    'enc_s': t_enc, 'prompt_tokens': u.get('prompt_tokens', ''),
                    'completion_tokens': u.get('completion_tokens', ''),
                    'total_tokens': u.get('total_tokens', ''),
                    'raw': j['choices'][0]['message']['content'], 'err': ''}
        except urllib.error.HTTPError as ex:
            last = ex
            if ex.code in (429, 500, 502, 503, 504):
                time.sleep(min(30, 3 * (2 ** a))); continue
            break
        except Exception as ex:
            last = ex
            time.sleep(min(20, 2 * (a + 1)))
    return {'item': rec['layout_id'], 'latency_s': time.time() - t0, 'http_s': '',
            'enc_s': '', 'prompt_tokens': '', 'completion_tokens': '', 'total_tokens': '',
            'raw': 'ERR:%s' % str(last)[:200], 'err': '1'}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float('nan')


def main():
    print('== A5-2 ext smoke ==')
    if P.selfcheck(verbose=False) != 0:
        print('!! frozen probe selfcheck FAILED -> refusing to run'); return 3
    prompts, _ = P.build_prompts()
    global PROMPT
    PROMPT = prompts['base']
    mf = os.path.join(GRID, 'manifest.csv')
    rows = list(csv.DictReader(io.open(mf, encoding='utf-8-sig', newline='')))
    need = 1 + N_SEQ + N_CONC
    if len(rows) < need:
        print('!! manifest too short'); return 2
    rows = rows[:need]
    print('  frozen probe selfcheck OK | manifest %d rows | using first %d' % (len(rows), need))
    print('  port=%d served=%s tag=%s load_s=%s' % (PORT, SERVED, TAG, LOAD_S or 'n/a'))

    out = os.path.join(OUTDIR, '%s_smoke.csv' % TAG)
    cols = ['phase', 'item', 'latency_s', 'http_s', 'enc_s', 'prompt_tokens',
            'completion_tokens', 'total_tokens', 'err', 'raw']

    w = call_once(rows[0])
    print('  WARMUP %s  latency=%.2fs http=%.2fs ctok=%s raw=%r'
          % (w['item'], w['latency_s'], w['http_s'] or 0, w['completion_tokens'], w['raw'][:40]))

    res = []

    t_a = time.time()
    for r in rows[1:1 + N_SEQ]:
        d = call_once(r); d['phase'] = 'seq'; res.append(d)
        print('    seq %-22s %.2fs ctok=%s' % (d['item'], d['latency_s'], d['completion_tokens']))
    seq_wall = time.time() - t_a

    t_b = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        conc = list(ex.map(call_once, rows[1 + N_SEQ:1 + N_SEQ + N_CONC]))
    conc_wall = time.time() - t_b
    for d in conc:
        d['phase'] = 'conc'
    res.extend(conc)

    with io.open(out, 'w', newline='', encoding='utf-8') as fh:
        cw = csv.DictWriter(fh, fieldnames=cols, lineterminator='\n')
        cw.writeheader()
        cw.writerow({**{k: w.get(k, '') for k in cols}, 'phase': 'warmup'})
        for d in res:
            cw.writerow({k: d.get(k, '') for k in cols})

    def stats(tag, ds, wall):
        ls = [float(d['latency_s']) for d in ds]
        hs = [float(d['http_s']) for d in ds if d['http_s'] != '']
        ct = [int(d['completion_tokens']) for d in ds if d['completion_tokens'] != '']
        pt = [int(d['prompt_tokens']) for d in ds if d['prompt_tokens'] != '']
        ne = sum(1 for d in ds if d['err'] == '1')
        print('  [%s] n=%d wall=%.1fs  latency mean=%.2f p50=%.2f p90=%.2f min=%.2f max=%.2f'
              % (tag, len(ds), wall, statistics.mean(ls), pct(ls, .5), pct(ls, .9), min(ls), max(ls)))
        if hs:
            print('       http mean=%.2f p50=%.2f p90=%.2f | enc mean=%.3f'
                  % (statistics.mean(hs), pct(hs, .5), pct(hs, .9),
                     statistics.mean([float(d['enc_s']) for d in ds if d['enc_s'] != ''])))
        if ct:
            print('       completion_tokens mean=%.1f min=%d max=%d | prompt_tokens mean=%.0f | http_err=%d'
                  % (statistics.mean(ct), min(ct), max(ct), statistics.mean(pt) if pt else -1, ne))
        eff = len(ds) / wall if wall > 0 else 0
        print('       effective throughput = %.2f calls/s (wall %.1fs)' % (eff, wall))
        return {'n': len(ds), 'wall': wall, 'mean': statistics.mean(ls), 'p50': pct(ls, .5),
                'p90': pct(ls, .9), 'ctok_mean': statistics.mean(ct) if ct else None,
                'http_err': ne, 'eff_calls_s': eff}

    s_seq = stats('seq/workers=1', [d for d in res if d['phase'] == 'seq'], seq_wall)
    s_conc = stats('conc/workers=%d' % WORKERS, [d for d in res if d['phase'] == 'conc'], conc_wall)

    summ = {'tag': TAG, 'served': SERVED, 'port': PORT, 'load_s': LOAD_S,
            'warmup': {'item': w['item'], 'latency_s': w['latency_s'],
                       'completion_tokens': w['completion_tokens']},
            'seq': s_seq, 'conc': s_conc, 'workers': WORKERS, 'out_csv': out}
    with io.open(os.path.join(OUTDIR, '%s_smoke_summary.json' % TAG), 'w', encoding='utf-8') as fh:
        json.dump(summ, fh, ensure_ascii=False, indent=2)
    print('  summary -> %s' % os.path.join(OUTDIR, '%s_smoke_summary.json' % TAG))
    print('SMOKE_DONE %s' % TAG)
    return 0


if __name__ == '__main__':
    sys.exit(main())
