
import csv, os
ROOT = '/root/aerial'
EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.JPG', '.PNG')
for ds in ('aitod', 'visdrone'):
    idir = os.path.join(ROOT, ds, 'images')
    with open(os.path.join(ROOT, 'gt_%s.csv' % ds), encoding='utf-8-sig') as f:
        gt = {r['item']: int(r['gt']) for r in csv.DictReader(f)}
    def p(n):
        for e in EXTS:
            q = os.path.join(idir, n + e)
            if os.path.exists(q):
                return q
        return None
    hit = [n for n in gt if p(n)]
    print('%-10s gt=%d 命中图像=%d' % (ds, len(gt), len(hit)))
