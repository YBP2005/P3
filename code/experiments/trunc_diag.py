#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trunc_diag.py — 判别"拒答"是真拒答还是被 max_tokens 截断

做法：从已有结果里挑出 parse_ok=0（我称之"拒答"）的样本，**用 max_tokens=512 重发**，
记录 finish_reason / completion_tokens / 完整文本，看：
  - finish_reason == 'length'  ⇒ 是被截断（我 max_tokens=64 的锅）
  - finish_reason == 'stop' 且是完整句子 ⇒ 真拒答
  - 512 下能否解析出人数 ⇒ 截断导致的假拒答占比
同时跑一批 parse_ok=1 的作对照。
"""
import base64, csv, io, json, os, re, sys, urllib.request

API = 'http://127.0.0.1:8000/v1/chat/completions'


def detect_model():
    """从 /v1/models 取当前服务的模型名——绝不写死，避免 404 被当成模型回答"""
    with urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=20) as r:
        d = json.loads(r.read().decode())
    names = [m['id'] for m in d.get('data', [])]
    want = os.environ.get('SERVED_MODEL', '')
    if want and want in names:
        return want
    if not names:
        raise SystemExit('服务里没有模型')
    return names[0]


MODEL = detect_model()
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
OUT = '/root/trunc_diag'
os.makedirs(OUT, exist_ok=True)

DIRS = {
 'st_a': '/root/dense/shanghaitech/images/part_A_test',
 'ucf': '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
 'visdrone': '/root/aerial/visdrone/images',
}


def call(im, mt, temp=0.0):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    p = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': PR}]}], 'temperature': temp, 'max_tokens': mt}
    req = urllib.request.Request(API, data=json.dumps(p).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    ch = d['choices'][0]
    return ch['message']['content'], ch.get('finish_reason'), d.get('usage', {}).get('completion_tokens')


def parse(raw):
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw.replace(',', ''), re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'\d+', raw.replace(',', ''))
    return int(m.group(1)) if m else None


def pick(fam, ds, want_bad, want_good):
    """从已有结果挑 budget=0 的行"""
    f = '/root/res_ctrl/%s/res_ctrl_%s.csv' % (fam, ds)
    if not os.path.exists(f):
        return []
    bad, good = [], []
    for r in csv.DictReader(open(f, encoding='utf-8-sig', newline='')):
        if int(float(r.get('budget') or 0)) != 0 or (r.get('http_err') or '0') == '1':
            continue
        it = r['item']
        p = os.path.join(DIRS[ds], it + '.jpg')
        if not os.path.exists(p):
            continue
        rec = (it, p, r.get('gt'), r.get('raw', ''))
        if (r.get('parse_ok') or '') == '1':
            if len(good) < want_good:
                good.append(rec)
        else:
            if len(bad) < want_bad:
                bad.append(rec)
    return bad, good


from PIL import Image
SUM = []
for fam in ['ivl', 'q32']:
    for ds in ['st_a', 'ucf', 'visdrone']:
        got = pick(fam, ds, 25, 8)
        if not got:
            continue
        bad, good = got
        if not bad and not good:
            continue
        print('\n===== %s / %s   拒答样本 %d，作答样本 %d =====' % (fam, ds, len(bad), len(good)))
        rows = []
        for tag, recs in [('REFUSED', bad), ('ANSWERED', good)]:
            for (it, p, gt, oldraw) in recs:
                try:
                    im = Image.open(p).convert('RGB')
                    for mt in [64, 512]:
                        txt, fin, ct = call(im, mt)
                        rows.append(dict(fam=fam, ds=ds, tag=tag, item=it, gt=gt, mt=mt,
                                         fin=fin, ct=ct, pred=parse(txt),
                                         txt=txt.replace('\n', ' ')))
                except Exception as ex:
                    rows.append(dict(fam=fam, ds=ds, tag=tag, item=it, gt=gt, mt=-1,
                                     fin='ERR', ct=0, pred=None, txt=str(ex)[:80]))
        # 汇总
        for tag in ['REFUSED', 'ANSWERED']:
            for mt in [64, 512]:
                s = [r for r in rows if r['tag'] == tag and r['mt'] == mt]
                if not s:
                    continue
                nfin = {}
                for r in s:
                    nfin[r['fin']] = nfin.get(r['fin'], 0) + 1
                nparse = sum(1 for r in s if r['pred'] is not None)
                ct = [r['ct'] for r in s if r['ct']]
                print('  %-8s max_tokens=%-4d n=%2d 可解析=%2d  finish=%s  completion_tokens中位=%s'
                      % (tag, mt, len(s), nparse, nfin, (sorted(ct)[len(ct) // 2] if ct else '-')))
        # 例子
        print('  --- 原判为拒答、在 max_tokens=512 下的完整输出（前 6 条）---')
        for r in [x for x in rows if x['tag'] == 'REFUSED' and x['mt'] == 512][:6]:
            print('   [%s] gt=%s fin=%s tok=%s pred=%s | %s' %
                  (r['item'][:16], r['gt'], r['fin'], r['ct'], r['pred'], r['txt'][:150]))
        print('  --- 原判为拒答、在 max_tokens=64 下的输出（前 3 条，看是否与 512 相同）---')
        for r in [x for x in rows if x['tag'] == 'REFUSED' and x['mt'] == 64][:3]:
            print('   [%s] fin=%s tok=%s pred=%s | %s' % (r['item'][:16], r['fin'], r['ct'], r['pred'], r['txt'][:150]))
        SUM += rows

with open(os.path.join(OUT, 'trunc_diag.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['fam', 'ds', 'tag', 'item', 'gt', 'mt', 'fin', 'ct', 'pred', 'txt'])
    w.writeheader()
    for r in SUM:
        w.writerow(r)
print('\n明细 -> %s/trunc_diag.csv (%d 行)' % (OUT, len(SUM)))
