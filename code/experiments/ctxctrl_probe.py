# -*- coding: utf-8 -*-
"""w1_fsc_probe.py — W1d：FSC-147 上的**示例（少样本）臂**探针。

设计要点
  ① **不复制提示词**：base/permit 直接从 /root/19e_probe_multi.py importlib 取 `P`、`parse()`、
     `b64_of()`、`call_img()`；19e 本体零改动（md5 03edb14c98ff）。
  ② 新增两个臂（提示词**逐字**取自冻结判据 w1_prereg.json，不得在此擅自改写）：
       exemplar3       给出 3 个示例框（官方 box_examples_coordinates，归一化到 0-1000），要求数出同类目标总数
       exemplar3permit 同上，但允许 abstain（检验"给了示例后出口是否仍被使用"）
  ③ **不画框、不改图**：示例框只以文本坐标给出。原因：画框会改变输入张量本身，
     使得与既有 base 臂（同图同尺度）不可比；文本坐标只改提示，是干净的对照。
  ④ 图像尺寸：FSC 的标注坐标在 `images_384_VarV2`（最长边缩放）坐标系里，故归一化用
     **该图实际宽高**（PIL 读出的 w,h），除以它再乘 1000。
  ⑤ 输出 schema 与 E2/E3/19g 完全一致，命名 `fsc_<model>_<arm>.csv`，
     写入 /root/w1_results/fsc —— 便于 w1_judge.py 的 P6 直接读。

用法：python3 w1_fsc_probe.py --model <served-name> --arms base,permit,exemplar3,exemplar3permit [--n 300]
"""
import argparse
import csv
import importlib.util
import io
import json
import os
import queue
import sys
import threading
import time

sys.stdout.reconfigure(encoding='utf-8')
FSC = '/root/fsc147'
OUTD = None   # ★ 相对冻结版**只改这一处语义**：输出目录改为命令行参数 --outd
              #   （服务栈对照需要 3 构建 × 2 上下文 × 3 次起服 = 18 个互不覆盖的目录）
P19E = '/root/19e_probe_multi.py'

spec = importlib.util.spec_from_file_location('p19e', P19E)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
assert hasattr(E, 'P') and hasattr(E, 'parse') and hasattr(E, 'call_img'), '19e 结构不符，停止'
print('仪器：复用 19e 的 P/parse/call_img/b64_of（19e 未改动）')

# ★ 冻结提示词（与 w1_prereg.json arms.frozen_new_prompts 逐字一致）
P_NEW = {
    'exemplar3': ('请参考图中给出的 3 个示例目标的框（左上与右下坐标，已归一化到 0-1000）：{boxes}。'
                  '请数出整幅图中与这些示例**同类**目标的总数，不要遗漏、不要重复。'
                  '以JSON格式输出：{{"count": 数量}}，只输出JSON。'),
    'exemplar3permit': ('请参考图中给出的 3 个示例目标的框（左上与右下坐标，已归一化到 0-1000）：{boxes}。'
                        '请数出整幅图中与这些示例**同类**目标的总数；如果你无法逐个确证，请回答 abstain，'
                        '而不要猜测。以JSON格式输出：{{"count": 数量}} 或 {{"count": "abstain"}}，只输出JSON。'),
}


def load_gt_and_boxes():
    ann = json.load(io.open(os.path.join(FSC, 'annotation_FSC147_384.json'), encoding='utf-8'))
    gt, boxes = {}, {}
    for k, v in ann.items():
        pts = v.get('points') or []
        gt[k] = len(pts) if pts else int(sum(b.get('count', 0) for b in (v.get('boxes') or [])))
        boxes[k] = v.get('box_examples_coordinates') or []
    return gt, boxes


def fmt_boxes(ex, w, h):
    out = []
    for b in ex[:3]:
        xs = [p[0] for p in b]; ys = [p[1] for p in b]
        x1, x2 = min(xs), max(xs); y1, y2 = min(ys), max(ys)
        out.append('(%d,%d,%d,%d)' % (round(1000 * x1 / w), round(1000 * y1 / h),
                                      round(1000 * x2 / w), round(1000 * y2 / h)))
    return '、'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--arms', default='base,permit,exemplar3,exemplar3permit')
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--outd', required=True, help='输出目录（本对照必需）')
    A = ap.parse_args()
    global OUTD
    OUTD = A.outd
    os.makedirs(OUTD, exist_ok=True)
    gt, boxes = load_gt_and_boxes()
    ids = [x.strip() for x in io.open(os.path.join(FSC, 'sample_test_ids.txt')) if x.strip()][:A.n]
    from PIL import Image
    for arm in A.arms.split(','):
        outp = os.path.join(OUTD, 'fsc_%s_%s.csv' % (A.model.replace('/', '_'), arm))
        done = set()
        if os.path.exists(outp):
            with io.open(outp, encoding='utf-8-sig') as f:
                done = {r['item'] for r in csv.DictReader(f)}
        todo = [i for i in ids if i not in done]
        if not todo:
            print('  [%s] 已完成，跳过' % arm); continue
        q = queue.Queue()
        for i in todo:
            q.put(i)
        lock = threading.Lock()
        fh = io.open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if not done:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])

        def work():
            while True:
                try:
                    it = q.get_nowait()
                except Exception:
                    return
                p = os.path.join(FSC, 'images', it)
                t0 = time.time()
                try:
                    im = Image.open(p).convert('RGB')
                    if arm in P_NEW:
                        prompt = P_NEW[arm].format(boxes=fmt_boxes(boxes.get(it, []), im.width, im.height))
                    else:
                        prompt = E.P[arm]
                    raw = E.call_img(E.b64_of(im), prompt, A.model)
                    v = E.parse(raw)
                    ok = 1 if v is not None else 0
                except Exception as ex:
                    raw, v, ok = 'ERR:%s' % str(ex)[:150], None, 0
                with lock:
                    w.writerow([it, gt.get(it, ''), '' if v is None else v, ok, raw[:800],
                                round(time.time() - t0, 2)])
                    fh.flush()
        ths = [threading.Thread(target=work) for _ in range(A.workers)]
        [t.start() for t in ths]; [t.join() for t in ths]
        fh.close()
        rows = list(csv.DictReader(io.open(outp, encoding='utf-8-sig')))
        z = sum(1 for r in rows if str(r.get('pred', '')).strip() in ('0', '0.0'))
        print('  [%s] %d 行；答 0 的 %d 个；-> %s' % (arm, len(rows), z, outp))


if __name__ == '__main__':
    main()
