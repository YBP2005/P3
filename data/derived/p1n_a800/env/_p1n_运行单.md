# P1-N 单卡运行单（名词替换版 P1-D 补测）

## §0 上机第一件事（不碰 GPU）
```
python3 /root/p1n/p1n_integrity.py      # 与基线比对；缺件/变号即停下报告
```
（基线含：判据件、p1n_probe.py、pf_p0_probe.py md5 `e7a65fd47345c2fe040fa4d05a3b1d86`、
`/root/p1d/data/{sample_mtdc.csv,sample_gwhd.csv}`、`/root/mtdc/images`、`/root/p1d/data/gwhd/images`、
模型目录、起服脚本 `pf_serve_awq4bit_8013.sh` md5 `1eca04a1c22049e7a7ee077380387314`。）

## §1 预检卡空
`nvidia-smi` 查目标卡（单卡模式预期 0）；`used > 2000 MiB` 则等，不抢卡。

## §2 起服 + smoke
起一次服务 → `p1n_probe.py --domain mtdc --budget 0 --limit 20` ⇒ 检查点：20 行、多数 parse_ok=1、
**prompt 自检通过**（可逆性断言没拒跑）；记 items/min 与 `Running/Waiting`。

## §3 并发
沿用 P1-D 的跑前规则（w4 vs w12 各 200 项；w12 快 ≥20% 且 `Waiting≈0` 才换）。**本轮到目前仍是 w4。**

## §4 全量
3 次全新起服 × 11 档 × 2 域 × 250 项 = **16,500 次**（约 1 小时；单卡 A800、AWQ-4bit）。
**档位与 item 集必须与 P1-D 逐项相同**（同 11 档、同 `random.Random(20261002)` 抽样），否则对照无效。

## §5 分析
- 每档在自己 250 项上池化 `dev = 100(Σpred−Σgt)/Σgt`；span = max−min；
- C1（250 行/格）、C5（parse_ok ≥95%）、**C2 全零格数**、**C3 span 是否进 [7.04, 28.15]**、
  **C4 与 P1-D 的逐档配对差**；
- 判决书须含"两种结果各自的处置"（见判据件 `criteria_addendum.disposition`）。

## §6 收工
逐件 md5 双验取回 `_a800_p1n\`；确认卡回 0 MiB；写判决书与 `_p1n_run.log`。
**纪律**：只用指定卡；不机器级 pkill、不用 `-f` 模式匹配；不进 `/root/cvpr_exp`；大件分块上传。
