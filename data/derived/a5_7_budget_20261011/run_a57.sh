#!/bin/bash
# run_a57.sh —— 实验 1「预算匹配预注册复验」的编排（★ 每 (alias, knob, level) 一次起服，共 3 次）
#
# ★ 本件**在云端由上级执行**：它不自己起任何本地服务，只在远端调用既有的
#    `/root/a51_work/start_a51.sh` + `/root/a51_work/runner_a51.py`（两者**不改动**）。
#
# 用法（在远端）：
#   bash /root/a57_work/run_a57.sh [--pool /root/a57_work/pool] [--only alias,knob,level] [--dry-run]
#   ★ 上机第一步建议 `--dry-run`：只打印全部 54 行命令，供上级逐行核对模型目录名与端口。
#
# 规模（预注册冻结）：3 家族 × 2 knob × 3 档 × 100 图 × 3 次起服 = **5,400 次调用 / 54 次起服**。
#
# 输出（与 analyze_a57.py 的读入约定一致）：
#   $ROOT/work/<alias>/<knob>/<level_label>/start<k>/run.jsonl
#   $ROOT/work/<alias>/<knob>/<level_label>/start<k>/cell_contracts_base.csv
#   $ROOT/work/<alias>/<knob>/<level_label>/start<k>/{start,run}.log
# 契约/图像在 $POOL（= $ROOT/pool，render_a57.py 的 out）；分析器读 $ROOT/manifest.csv
# 跑完每格打印 **唯一 200 数** 与每格读数（MAE / rho）。
set -u
export PATH=/usr/local/miniconda3/bin:$PATH
export PYTHONIOENCODING=utf-8

ROOT="${A57_ROOT:-/root/a57_work}"          # 分析根：manifest.csv 在这里、work/ 也在这里
POOL="${A57_POOL:-$ROOT/pool}"              # 渲染件（images/ + manifest.csv + contracts.csv）
A51="${A57_A51:-/root/a51_work}"
LANES="${A57_LANES:-8}"
MAXTOK="${A57_MAX_TOKENS:-1024}"
PORT="${A57_PORT:-8021}"
DRY=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --pool) POOL="$2"; shift 2;;
    --only) ONLY="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    *) echo "unknown arg: $1"; exit 2;;
  esac
done

# alias|模型目录|量化参数|knob|level_label
# ★ 模型目录名取自 A5-1/A5-2 既有件（前两个家族）；lov7b 的目录名**必须在上机前核对**。
CELLS="$(cat <<'EOF'
q32fp8|Qwen3-VL-32B-Instruct-FP8||density|24
q32fp8|Qwen3-VL-32B-Instruct-FP8||density|30
q32fp8|Qwen3-VL-32B-Instruct-FP8||density|36
q32fp8|Qwen3-VL-32B-Instruct-FP8||res|px640
q32fp8|Qwen3-VL-32B-Instruct-FP8||res|px704
q32fp8|Qwen3-VL-32B-Instruct-FP8||res|px832
ivl358b|InternVL3_5-8B||density|24
ivl358b|InternVL3_5-8B||density|30
ivl358b|InternVL3_5-8B||density|36
ivl358b|InternVL3_5-8B||res|px640
ivl358b|InternVL3_5-8B||res|px704
ivl358b|InternVL3_5-8B||res|px832
lov7b|llava-onevision-qwen2-7b-ov||density|24
lov7b|llava-onevision-qwen2-7b-ov||density|30
lov7b|llava-onevision-qwen2-7b-ov||density|36
lov7b|llava-onevision-qwen2-7b-ov||res|px640
lov7b|llava-onevision-qwen2-7b-ov||res|px704
lov7b|llava-onevision-qwen2-7b-ov||res|px832
EOF
)"

CONTRACTS="$POOL/contracts.csv"
HAVE_CONTRACTS=1
if [ ! -f "$CONTRACTS" ]; then
  HAVE_CONTRACTS=0
  if [ "$DRY" = "0" ]; then
    echo "!! 缺 $CONTRACTS（先在本地跑 render_a57.py 并把 pool/ 送上机）"
    exit 2
  fi
  echo "[a57] ⚠ dry-run：$CONTRACTS 尚未上机 ⇒ 跳过每格契约表生成，其余命令照打"
fi

echo "[a57] root=$ROOT ｜ pool=$POOL ｜ a51=$A51 ｜ lanes=$LANES ｜ max_tokens=$MAXTOK ｜ port=$PORT"
echo "[a57] 规模：3 家族 × 2 knob × 3 档 × 100 图 × 3 次起服 = 5400 次调用 / 54 次起服"
[ "$DRY" = "1" ] && echo "[a57] ★ DRY-RUN：只打印命令，不起服、不调用模型"

# 分析器读 $ROOT/manifest.csv；渲染件在 $POOL 下 ⇒ 若无则在根上放一份拷贝（不改内容）
if [ ! -f "$ROOT/manifest.csv" ] && [ -f "$POOL/manifest.csv" ]; then
  cp -f "$POOL/manifest.csv" "$ROOT/manifest.csv"
  echo "[a57] manifest -> $ROOT/manifest.csv（分析器读这一份）"
fi

fail=0
while IFS='|' read -r ALIAS MODELDIR QUANT KNOB LVLAB; do
  [ -z "${ALIAS:-}" ] && continue
  if [ -n "$ONLY" ]; then
    case ",$ONLY," in *",$ALIAS,$KNOB,$LVLAB,"*) ;; *) continue;; esac
  fi
  CELLD="$ROOT/work/$ALIAS/$KNOB/$LVLAB"
  mkdir -p "$CELLD"

  # 本格的契约表（含 image 列 ⇒ runner_a51.find_img 会在 A51_IMG_DIR=$POOL 下命中）
  if [ "$HAVE_CONTRACTS" = "1" ]; then
  python3 - "$CONTRACTS" "$CELLD/cell_contracts_base.csv" "$KNOB" "$LVLAB" <<'PYEOF'
import csv, io, sys
src, dst, knob, lab = sys.argv[1:5]
rows = [r for r in csv.DictReader(io.open(src, encoding='utf-8-sig'))
        if r['knob'] == knob and r['level'] == lab]
assert rows, 'empty cell %s/%s' % (knob, lab)
with io.open(dst, 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['item', 'image', 'gt_count', 'class_name',
                                       'cond_a_base', 'cond_b_base'])
    w.writeheader()
    for r in rows:
        w.writerow(dict(item=r['item'], image=r['item'], gt_count=r['count_gt'],
                        class_name=r['target_word'], cond_a_base=r['prompt'],
                        cond_b_base=r['prompt']))
print('  [cell] 契约 %s/%s -> %d 行' % (knob, lab, len(rows)))
PYEOF
  fi

  for K in 1 2 3; do
    W="$CELLD/start$K"
    mkdir -p "$W"
    if [ "$DRY" = "1" ]; then
      echo "[dry] bash $A51/start_a51.sh $ALIAS $MODELDIR $PORT ${QUANT}"
      echo "[dry] A51_TARGETMAP=$CELLD/cell_contracts_base.csv A51_IMG_DIR=$POOL A51_MODEL=$MODELDIR A51_ALIAS=$ALIAS A51_COND=base A51_REP=$K A51_PORT=$PORT A51_LANES=$LANES A51_MAX_TOKENS=$MAXTOK A51_ARMS=base A51_WORK=$W python3 $A51/runner_a51.py"
      continue
    fi
    echo "[a57] ===== $ALIAS / $KNOB / $LVLAB / start$K  $(date -u +%H:%M:%SZ)"
    # ★ 三次起服**互相独立**：每一格都重新走 pidfile 精确停 → 起服 → 放量
    # shellcheck disable=SC2086
    if ! bash "$A51/start_a51.sh" "$ALIAS" "$MODELDIR" "$PORT" $QUANT > "$W/start.log" 2>&1; then
      echo "  !! 起服失败，见 $W/start.log"
      fail=1
      continue
    fi
    if ! A51_TARGETMAP="$CELLD/cell_contracts_base.csv" A51_IMG_DIR="$POOL" \
         A51_MODEL="$MODELDIR" A51_ALIAS="$ALIAS" A51_COND=base A51_REP="$K" \
         A51_PORT="$PORT" A51_LANES="$LANES" A51_MAX_TOKENS="$MAXTOK" A51_ARMS=base \
         A51_WORK="$W" python3 "$A51/runner_a51.py" > "$W/run.log" 2>&1; then
      echo "  !! 放量失败，见 $W/run.log"
      fail=1
    fi
    python3 - "$W/run.jsonl" "$KNOB" "$LVLAB" "$K" <<'PYEOF'
import io, json, sys
p, knob, lab, k = sys.argv[1:5]
rows, keys200, bad = [], set(), 0
try:
    fh = io.open(p, encoding='utf-8', errors='replace')
except IOError:
    print('  [cell] %s/%s start%s：**run.jsonl 不存在**' % (knob, lab, k))
    raise SystemExit(0)
for ln in fh:
    ln = ln.strip()
    if not ln:
        continue
    try:
        r = json.loads(ln)
    except Exception:
        bad += 1
        continue
    rows.append(r)
    if r.get('http') == 200:
        keys200.add(r.get('key'))
ok = [r for r in rows if r.get('http') == 200 and r.get('pred') is not None]
preds = [float(r['pred']) for r in ok]
gts = [float(r['gt']) for r in ok]
mae = (sum(abs(a - b) for a, b in zip(preds, gts)) / len(preds)) if preds else float('nan')
rho = (100.0 * (sum(preds) - sum(gts)) / sum(gts)) if gts and sum(gts) else float('nan')
print('  [cell] %s/%s start%s：行=%d 唯一200=%d 可解析=%d 坏JSON=%d ｜ MAE=%.4f rho=%+.4f'
      % (knob, lab, k, len(rows), len(keys200), len(ok), bad, mae, rho))
PYEOF
  done
done <<< "$CELLS"

if [ "$DRY" = "0" ]; then
  echo "[a57] 全部格子跑完（3 家族 × 2 knob × 3 档 × 3 起服 = 54 次起服），失败标记=$fail"
  echo "[a57] 下一步：python3 analyze_a57.py --out $ROOT --results $ROOT/results"
fi
exit "$fail"
