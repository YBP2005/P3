
import csv, glob, os, re, statistics as st
def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
print('%-30s %-9s %5s %6s %6s %9s %9s' % ('model','arm','n','非数值','数值0','pred/gt中位','偏差中位'))
for p in sorted(glob.glob('/root/e1_results/e1_*.csv')):
    b = os.path.basename(p)[:-4]
    m = re.match(r'e1_(.+)_(st_a|ucf)_(\w+)$', b)
    model, ds, arm = m.group(1), m.group(2), m.group(3)
    rows = load(p)
    num, nonnum, zero = [], 0, 0
    for r in rows:
        v = (r.get('pred') or '').strip()
        raw = r.get('raw') or ''
        if re.search(r'abstain|cannot_judge|no_people', raw):
            nonnum += 1
        try:
            x = float(v)
            num.append(x)
            if x == 0: zero += 1
        except Exception:
            if not re.search(r'abstain|cannot_judge|no_people', raw):
                nonnum += 1
    rat = [x / float(r['gt']) for x, r in zip(num, [r for r in rows if (r.get('pred') or '').strip().replace('.','',1).isdigit()]) if float(r['gt']) > 0]
    dev = [(x / float(r['gt']) - 1) for x, r in zip(num, [r for r in rows if (r.get('pred') or '').strip().replace('.','',1).isdigit()]) if float(r['gt']) > 0]
    print('%-30s %-9s %5d %6d %6d %9s %9s' % (model[:30], ds+'/'+arm, len(rows), nonnum, zero,
          ('%.3f' % st.median(rat)) if rat else '-', ('%+.1f%%' % (100*st.median(dev))) if dev else '-'))
