
import re
p = '/root/06_dense_vlm.py'
s = open(p, encoding='utf-8').read()
# 在 parse 里把 0 标记为弃权（返回 None 会丢数据，故保留数值但另存标记列）
if 'ABSTAIN_MARK' not in s:
    s = s.replace(
        "def parse(raw):",
        "ABSTAIN_MARK = True  # 0 且提示语含拒绝措辞 -> 记为弃权\n\n\ndef parse(raw):")
    s = s.replace(
        "                    wr.writerow([nm, gt[nm], pred if pred is not None else '',\n"
        "                                 1 if pred is not None else 0, nt, nraw, '%.2f' % (time.time() - t0)])",
        "                    abandon = 1 if (pred == 0 or (nraw and any(k in nraw.lower() for k in\n"
        "                              ['too many', '无法', '数不清', '难以', '众多']))) else 0\n"
        "                    wr.writerow([nm, gt[nm], pred if pred is not None else '',\n"
        "                                 1 if pred is not None else 0, nt, nraw, '%.2f' % (time.time() - t0), abandon])")
    s = s.replace("wr.writerow(['item', 'gt', 'pred', 'ntiles', 'parse_ok', 'raw', 'latency_s'])",
                  "wr.writerow(['item', 'gt', 'pred', 'ntiles', 'parse_ok', 'raw', 'latency_s', 'abstain'])")
    open(p, 'w', encoding='utf-8').write(s)
    print('已打补丁：新增 abstain 列')
else:
    print('已有补丁')
