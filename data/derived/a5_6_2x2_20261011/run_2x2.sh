#!/bin/bash
# ============================================================================
# A5-6（r20 评审 A5-第2条）「点名 0 × 弃答出口」2×2 正交实验 —— 编排脚本
#   ★ 一构建（一模型）一条件的编排：**同一构建内 4 条件共用同一次起服**，构建之间才换服。
#   ★ 复用上级既有资产（不重写、不改动它们）：
#        /root/a51_work/start_a51.sh       精确停旧服 → 起新服 → 轮询 /v1/models 200
#        /root/a51_work/runner_a51.py      客户端（text-first、PNG 原样、max_tokens=1024、不发 temperature）
#   ★ 每构建格数：4 条件 × 600 图 = **2,400 格**；每条件独立工作目录 work/<alias>/<cond>/run.jsonl
#
# 用法：
#   bash run_2x2.sh <alias> <模型目录名> <lanes> [量化参数...]
#   例：bash run_2x2.sh q32fp8   Qwen3-VL-32B-Instruct-FP8 16 --quantization fp8
#       bash run_2x2.sh ivl358b  InternVL3_5-8B             16
#       bash run_2x2.sh pixtral  Pixtral-Large-w4a16         4      # ★ 需 /root/venv_odt，见 PLAN.md
#
# 环境变量（全部可覆盖）：
#   BASE          工作根（默认 /root/a56_2x2）；run.jsonl 落在 $BASE/work/<alias>/<cond>/run.jsonl
#   POOL          图像/契约根（默认 /root/a56_2x2/pool；须含 images/t2x2_0001.png… 与 manifest.csv）
#   CONTRACTS     契约根（默认 /root/a56_2x2/contracts；须含 target_map_<cond>.csv）
#   A51_DIR       上级资产目录（默认 /root/a51_work；须含 start_a51.sh 与 runner_a51.py）
#   PORT          服务端口（默认 8021）
#   MAX_TOKENS    ★ 四条件共用同一 max_tokens（默认 1024，与 x01/A5-1 口径一致）
#   CONDS         条件顺序（默认 no_name0_no_exit,no_name0_exit,name0_no_exit,name0_exit）
#   LIMIT         只跑前 N 张图（冒烟；默认 0=全量 600）
#   RUNNER        期望的 runner 版本闸门（默认 a51；不匹配则**拒绝开跑**，避免用错 runner）
#   PIPY          取 python 解释器（默认 python3；pixtral 走 venv 时外部已 export）
#   SKIP_DONE     1=唯一 200 已满 2400 则跳过本构建（断点续跑；默认 1）
#   NO_STOP       1=跑完不停服（默认 0=收尾精确停服，读 /root/CURRENT_VLLM.pid）
#   DRYRUN        1=只打印将要执行的命令，不真跑（默认 0）
#   GEN_LOG       1=每次调用 runner 的原始输出另存 <cond>/runner.log（默认 1）
#
# ★ 停止规则（评审口径，详见 PLAN.md）：至少 4 个家族跑满（4×2400=9,600 格）即算达标；
#   6 家族为上限；到达上限即停。本脚本**一次只跑一个构建**，家族顺序由上级编排控制。
# 退出码：0=本构建四条件都达 2400；2=某条件未满（可重跑本件续跑）；3=起服未就绪；4=runner 版本闸门不过。
# ============================================================================
set +u
trap '' HUP
export PATH=/usr/local/miniconda3/bin:$PATH

ALIAS="${1:?用法: run_2x2.sh <alias> <模型目录名> <lanes> [量化参数...]}"
MODEL="${2:?缺模型目录名}"
LANES="${3:?缺 lanes}"; shift 3 || true
QUANT=("$@")

BASE="${BASE:-/root/a56_2x2}"
POOL="${POOL:-$BASE/pool}"
CONTRACTS="${CONTRACTS:-$BASE/contracts}"
A51_DIR="${A51_DIR:-/root/a51_work}"
PORT="${PORT:-8021}"
MAX_TOKENS="${MAX_TOKENS:-1024}"
CONDS="${CONDS:-no_name0_no_exit,no_name0_exit,name0_no_exit,name0_exit}"
LIMIT="${LIMIT:-0}"
RUNNER="${RUNNER:-a51}"
PIPY="${PIPY:-python3}"
SKIP_DONE="${SKIP_DONE:-1}"
NO_STOP="${NO_STOP:-0}"
DRYRUN="${DRYRUN:-0}"
GEN_LOG="${GEN_LOG:-1}"
PIDF="/root/CURRENT_VLLM.pid"
N_IMG=600
N_COND=4
CELLS=$((N_COND * N_IMG))

mkdir -p "$BASE/work/$ALIAS" "$BASE/logs"
OUT="$BASE/logs/run_2x2_${ALIAS}.out"
log(){ echo "[2x2 $(date -u +%H:%M:%SZ)] $*" | tee -a "$OUT"; }

# ---------------------------------------------------------------- 前置校验（缺件即停，不猜）
for f in "$POOL/manifest.csv" "$A51_DIR/start_a51.sh" "$A51_DIR/runner_a51.py"; do
  [ -e "$f" ] || { log "FAIL 缺件：$f"; exit 2; }
done
if [ -d "$POOL/images" ]; then
  IMGDIR="$POOL/images"
elif [ -d "$(dirname "$POOL")/images" ]; then
  # ★ 容错：若 POOL 直接指向 images 目录，自动改用其父目录
  IMGDIR="$(dirname "$POOL")/images"
else
  log "FAIL 缺图像目录：$POOL/images（先跑 render_2x2.py）"; exit 2
fi
IFS=',' read -r -a CONDARR <<< "$CONDS"
for c in "${CONDARR[@]}"; do
  [ -e "$CONTRACTS/target_map_$c.csv" ] || { log "FAIL 缺契约 map：$CONTRACTS/target_map_$c.csv（先跑 make_contracts_2x2.py）"; exit 2; }
done

# ★ runner 版本闸门：既有 runner 的 self-report 协议串是 'a51 targetmatch'；换过 runner 就不许静默开跑
if [ "$RUNNER" = "a51" ]; then
  if ! grep -q "a51 targetmatch" "$A51_DIR/runner_a51.py"; then
    log "FAIL runner 版本闸门：$A51_DIR/runner_a51.py 内找不到 'a51 targetmatch'（被人改过？）—— 拒绝开跑"
    exit 4
  fi
fi

count_uniq200(){ # $1 = run.jsonl
  [ -f "$1" ] || { echo 0; return; }
  "$PIPY" - "$1" <<'PYEOF'
import json,sys
s=set()
for ln in open(sys.argv[1],encoding='utf-8',errors='replace'):
    try: r=json.loads(ln)
    except Exception: continue
    if r.get('http')==200: s.add(r.get('key'))
print(len(s))
PYEOF
}

stats(){ # $1 = run.jsonl → 打印：唯一200 / 行数 / 真零答零 / 真零弃答 / 非零准确 / GT=48 正确
  "$PIPY" - "$1" <<'PYEOF'
import json,sys
p=sys.argv[1]
try: lines=open(p,encoding='utf-8',errors='replace').read().splitlines()
except Exception: lines=[]
keys=set(); n200=0; tz=0; tz_zero=0; tz_ab=0; nz=0; nz_hit=0
for ln in lines:
    ln=ln.strip()
    if not ln: continue
    try: r=json.loads(ln)
    except Exception: continue
    if r.get('http')!=200: continue
    n200+=1; keys.add(r.get('key'))
    try: t=int(r.get('gt') if r.get('gt') not in (None,'') else r.get('gt_count'))
    except Exception: t=None
    if t is None: continue
    pred=r.get('pred'); ab=bool(r.get('abstain'))
    if t==0:
        tz+=1
        if pred==0: tz_zero+=1
        if ab or pred is None: tz_ab+=1
    else:
        nz+=1
        if pred==t: nz_hit+=1
def pct(a,b): return '-1' if not b else '%.3f'%(float(a)/b)
print('ROWS=%d UNIQ200=%d TRUEZERO_N=%d TZERO_ANS0=%d TZERO_ANS0_RATE=%s TZERO_ABSTAIN_OR_NULL=%d NONZERO_N=%d NONZERO_HIT=%d NONZERO_ACC=%s'
      % (len(lines),len(keys),tz,tz_zero,pct(tz_zero,tz),tz_ab,nz,nz_hit,pct(nz_hit,nz)))
PYEOF
}

build_uniq(){ # 本构建四条件唯一 200 求和
  local s=0
  for c in "${CONDARR[@]}"; do s=$((s + $(count_uniq200 "$BASE/work/$ALIAS/$c/run.jsonl"))); done
  echo "$s"
}

log "=== A5-6 2×2 构建开始 alias=$ALIAS model=$MODEL lanes=$LANES quant='${QUANT[*]:-<none>}' 端口=$PORT ==="
log "BASE=$BASE POOL=$POOL CONTRACTS=$CONTRACTS | 条件=${CONDARR[*]} | 每条件 $N_IMG 图 ⇒ 本构建 $CELLS 格 | max_tokens=$MAX_TOKENS（四条件共用）"

DONE=$(build_uniq)
if [ "$SKIP_DONE" = "1" ] && [ "$DONE" -ge "$CELLS" ]; then
  log "DONE-SKIP $ALIAS 本构建已完成（唯一 200 = $DONE / $CELLS）"
  for c in "${CONDARR[@]}"; do log "  [$c] $(stats "$BASE/work/$ALIAS/$c/run.jsonl")"; done; exit 0
fi

# ---------------------------------------------------------------- ① 起服（本构建只起一次）
ASUM=$(md5sum "$A51_DIR/runner_a51.py" 2>/dev/null | cut -c1-12)
log "起服：bash $A51_DIR/start_a51.sh $ALIAS $MODEL $PORT ${QUANT[*]:-}  ｜ runner md5[12]=${ASUM:-NA}"
if [ "$DRYRUN" = "1" ]; then
  log "[DRYRUN] 跳过起服与推理"
else
  bash "$A51_DIR/start_a51.sh" "$ALIAS" "$MODEL" "$PORT" "${QUANT[@]}" >> "$OUT" 2>&1
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/models" 2>/dev/null)
  [ "$CODE" = "200" ] || { log "FAIL 起服未就绪（http=$CODE）—— 看 /root/a51_serve_${ALIAS}.log 尾部"; exit 3; }
  log "起服就绪 http=200 pid=$(cat $PIDF 2>/dev/null | tr -dc '0-9')"
fi

# ---------------------------------------------------------------- ② 四条件顺序跑（同一台服）
FAILED=0
for c in "${CONDARR[@]}"; do
  W="$BASE/work/$ALIAS/$c"
  mkdir -p "$W"
  RUN="$W/run.jsonl"
  HAVE=$(count_uniq200 "$RUN")
  if [ "$HAVE" -ge "$N_IMG" ]; then
    log "SKIP  [$c] 已完成（唯一 200 = $HAVE / $N_IMG）"
    log "      [$c] $(stats "$RUN")"
    continue
  fi
  log "START [$c] 已有唯一 200 = $HAVE / $N_IMG ⇒ 续跑缺口 $((N_IMG - HAVE))"
  CMD=("$PIPY" "$A51_DIR/runner_a51.py")
  ENVV=(A51_TARGETMAP="$CONTRACTS/target_map_$c.csv" A51_IMG_DIR="$IMGDIR"
        A51_WORK="$W" A51_MODEL="$MODEL" A51_ALIAS="$ALIAS" A51_COND=b A51_REP=1
        A51_ARMS="$c" A51_PORT="$PORT" A51_LANES="$LANES" A51_MAX_TOKENS="$MAX_TOKENS" A51_LIMIT="$LIMIT")
  log "      env ${ENVV[*]}"
  if [ "$DRYRUN" = "1" ]; then
    log "      [DRYRUN] env ${ENVV[*]} ${CMD[*]}"
  else
    if [ "$GEN_LOG" = "1" ]; then
      env "${ENVV[@]}" "${CMD[@]}" >> "$W/runner.log" 2>&1
    else
      env "${ENVV[@]}" "${CMD[@]}" >> "$OUT" 2>&1
    fi
  fi
  ST=$(stats "$RUN")
  log "DONE  [$c] $ST"
  U=$(count_uniq200 "$RUN")
  [ "$U" -ge "$N_IMG" ] || { log "WARN  [$c] 唯一 200 = $U < $N_IMG ⇒ 本构建未满"; FAILED=1; }
done

# ---------------------------------------------------------------- ③ 收尾汇报
log "--- 本构建逐条件 ---"
TOT=0
for c in "${CONDARR[@]}"; do
  U=$(count_uniq200 "$BASE/work/$ALIAS/$c/run.jsonl")
  TOT=$((TOT + U))
  log "  [$c] $(stats "$BASE/work/$ALIAS/$c/run.jsonl")"
done
log "=== 构建汇总 alias=$ALIAS 唯一 200 合计 = $TOT / $CELLS ==="
if [ "$TOT" -ge "$CELLS" ]; then log "构建达标 ✅（$ALIAS：4 条件 × 600 图全部唯一 200）"; else log "构建未达标 ❌（缺 $((CELLS - TOT)) 格，可重跑本件断点续跑）"; fi

if [ "$NO_STOP" != "1" ] && [ "$DRYRUN" != "1" ] && [ -f "$PIDF" ]; then
  P=$(cat "$PIDF" | tr -dc '0-9')
  if [ -n "${P:-}" ] && kill -0 "$P" 2>/dev/null; then
    log "收尾：精确停服 pid=$P"
    kill -TERM "$P" 2>/dev/null
    for i in $(seq 1 20); do kill -0 "$P" 2>/dev/null || break; sleep 2; done
    kill -0 "$P" 2>/dev/null && { log "收尾：KILL pid=$P"; kill -9 "$P" 2>/dev/null; }
  fi
fi
[ "$FAILED" = "1" ] && exit 2 || exit 0
