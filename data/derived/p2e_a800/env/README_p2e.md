# P2-E 脚本包 —— 怎么用（README）

> 目的：补齐 §M.43 那张表缺的**两行**（`detector` 与 `density regression`），使 "ordering 稳健" 落在论文自己
> §F.2 的**完整六 knob** 上。**全程不训练**，只做推理 + 后处理 + 算术。
> 上游决定（2026-10-02）：**整幅，不做平铺**；**density 主口径 = 官方 DM-Count**。
> 方案与判据：`..\_p2e_p1d_实验方案_预注册版_20261002.md`。

## 0 一页流

```
G0 自检   → G1 约定锁定 → density（官方 DM-Count）→ detector（yolo11n 整幅）→ analyze
（不过就停）（不过就停）
```

* **G0 `p2e_selfcheck_m43.py`**：用本包共用的估计器**逐档**复现 §M.43 四行
  （343.55 / 1561.94 / 14.56 / 31.65，容差 0.05 pp）。**不逐档复现就退出**——那说明估计器或记录集与印值不同源。
  ✅ **已跑通（G0_PASS，四行逐档复现，各档 n=182）**。记录来源：机上 `/root/g56_res/` 的四个长表
  （`g56_arms.csv` = K3+K4、`g56_tile.csv` = K5、`g56_budget.csv` = K6、`g56_noise.csv` = 噪声底），
  已填进 `m43_records.json` 并取回本地副本 `ref/`。
  ★ 第一次跑时抓出**两个口径错误**（都已修，详见方案 §2.7）：① 必须用**每档自己 182 项的池化**口径
  （A39 的"各档交集"口径是给校准用的，混用会把 n 压到 53–118 且数全错）；② **不过滤任何行**
  （`filters` 已清空）；③ 档位顺序按**印值声明序**对位。
* **G1 `p2e_protocol_check.py`**：把"输入尺度"约定**实测锁死**在既有 CSRNet ladder 上。
  ✅ **已在本机跑过并通过**：`mult v ⇒ 两边 ×v`；`short v ⇒ min(W,H)=v`——两条各 **100%** 命中全部档位
  （对 `csrsta_ladder_st_a.csv` 的 `in_w/in_h` 逐行比，容差 1 px）。⇒ 两支口径可比。
* **`p2e_density_run.py`**：官方 DM-Count（`vgg19()` + 裸 `state_dict`，`outputs.sum()`；ImageNet 归一化、`BICUBIC`）
  在 st_a 182 图上跑 `mult` 五档（副口径：六档 + `short` 四档）。输出列与既有 ladder **完全同构**。
* **`p2e_detector_run.py`**：`yolo11n.pt` **整幅** × `imgsz ∈ {640,896,1024,1280,1536}`，**保留每张图 top-300 原始检测的
  score/label** ⇒ 任何 τ 都是**事后**算，不需重推理；输出 τ×imgsz 汇总（列与既有 VisDrone ladder 同构）。
* **`p2e_analyze.py`**：出两行（五档 `dev` + span）＋ 六 knob 排序 ＋ 判据；写 `out/p2e_rows.json` 与 `out/p2e_verdict.md`。

## 1 上机怎么跑

```bash
# ① 上传（本机执行；注意 MSYS_NO_PATHCONV=1，否则 /root/... 会被改写成 Windows 路径）
cd E:\Edu_workplace\_p3r7_v0624_prelaunch
set MSYS_NO_PATHCONV=1
python -B _a800.py "mkdir -p /root/p3r8_p2e/p2e/out"
for f in p2e/*.py p2e/*.json p2e/*.sh; do python -B _a800.py --putb64 "$f" "/root/p3r8_p2e/p2e/$(basename $f)"; done

# ② 起跑（后台；先确认卡空！另一侧的交接说明要求先打招呼）
python -B _a800.py --bg "bash /root/p3r8_p2e/p2e/p2e_run_all.sh"
python -B _a800.py --tail /root/logs/p2e.log 40
```

## 2 前置数据与权重（都已在机上）

| 件 | 路径 | 备注 |
|---|---|---|
| st_a 182 张原图 | `/root/dense/shanghaitech/images/part_A_test` | |
| gt（st_a 测试） | `/root/dense/shanghaitech/gt_st_a_test.csv` | 若路径不同，改 `p2e_*_run.py` 顶部的常量 |
| 官方 DM-Count 权重 | `/root/p3r8_p2e/weights/dmcount_official/model_sh_A.pth` | sha256 `810ea89b…`；另三件 `model_{qnrf,sh_B,nwpu}.pth` |
| 官方 DM-Count 代码 | `/root/p3r8_p2e/code/dmcount_repo` | codeload tar.gz；**仓库自带 `model_qnrf/nwpu.pth` 与我从 Drive 下的逐字节相同** ⇒ 双源互证 |
| yolo11n 权重 | `/root/p3r8_p2e/weights/yolo11n.pt` | sha256 `0ebbc80d…`；另有 yolo12n/12s、RetinaNet/Faster R-CNN |
| 既有 CSRNet/st_a ladder | 作者树 `analysis\data\pod_mirror\A\csrsta_ladder_st_a.csv` | G1 的参照，也是零调用交叉核对支 |

## 3 口径红线（**必须随结果一起报**，写在判据件 `caliber_red_lines` 里）

1. 这两行**不是** §M.43 四行的同一次 serving session ⇒ 用到时必须标注，且 **§M.43 的 3.01 pp 同 session 噪声底不可跨用**。
2. **不替代、不代理**：driven 不了就仍写 not measured。
3. density 行**必须带口径**（official DM-Count / CSRNet 分报，§D.1 的要求）。
4. **整幅**；若将来跑平铺，那是另一个分层，**绝不与本口径并池**。

## 4 已知待补

* ~~G0 的四份逐项件~~ ⇒ ✅ **已定位并填实**（`m43_records.json`，本地副本在 `ref/`）。
  遗留的只是**论文侧**的一条：§M.43 那句复现语仍不给文件名 ⇒ **v0629 候选**（补上这四个文件名，或把四件放行）。
* `p2e_density_run.py` 里 `ucf` 的图片/gt 路径是**按常见布局填的**，执行前请 `ls` 核对一次。
* 若 st_a 的 gt CSV 列名不是 `item,gt`，改 `p2e_*_run.py` 顶部的 `gtcsv` 与列名常量。
