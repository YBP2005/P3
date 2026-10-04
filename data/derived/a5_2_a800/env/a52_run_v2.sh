#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════════════
# ★ 本件是**修订版 v2**（由冻结原件 `a52_run.sh` **定点替换**生成，其余字节逐字相同）。
#   · 原件保留作 **provenance**：`a52_run.sh`（md5 a93ecd519341fba79bb7d993eb6641b8）
#   · **本轮（A5-2，2026-10-04）的正式运行用的是原件字节**，靠两处**外部规避**跑通：
#       R1：`cp -p` 出改名副本 `a52run.sh`（同 md5）后启动 —— 绕开缺陷 ① 的自匹配守门；
#       R4：外部看门狗 `_pidfix.sh` 每 4 s 把活服务 PID 写回 `$PIDF` —— 抵消缺陷 ③ 的清空。
#   · 本 v2 修复**3 处冻结件缺陷 + 1 处稳健性**（详见各 ★ 修 标注）：
#       ① 并发守门 `pids_with_name 'a52_run.sh'` 在 `$( … )` 子壳继承 argv ⇒ 自匹配 ⇒ 起不来
#       ② `stop_old_serve` 末尾无条件 `rm -f $PIDF` ⇒ 第二实例删掉共享 pid 文件
#       ③ `pids_with_port … || : > "$PIDF"`（函数返回 1）⇒ 把刚写入的 PID 清空 ⇒ 永不收服
#          ⇒ 每个构建跑完第 1 次起服必撞 `gpu_clear()`（实测：`grep -c 'pid='` = 0）
#       ④ 收服后轮询显存回落（实测 SIGTERM→0 MiB < 5 s，原 `sleep 8` 本够，改为轮询更稳）
#   ★ 判据件（`_a52_criteria_frozen.json` md5 758962a2…）与探针/生成器/分析器**均未改动**。
# ═══════════════════════════════════════════════════════════════════════════════════════
# a52_run.sh —— A5-2 编排（★ **只在拿到明确的 go 之后才允许执行**；本轮只备脚本，不跑）
#
# ── v2 设计（全部来自判据件 `_a52_criteria_frozen.json`，无一处"跑的时候再定"）──────────
#   · 仓位：`4 构建 × 3 合同 × 3 起服 = 36 格`，每格 **648 行** ⇒ 总 **23,328** 次
#   · ★ **单卡 80 GB 同一时刻只能服务一个构建**（FP8/BF16 的 32B 权重各 ~60+ GB）
#     ⇒ **外层按构建、内层按合同 × 起服**：
#         换构建 ⇒ 停旧服 → 起新服 → 探针自检 → 跑该构建的 3 合同 × 3 起服 → 关服
#     ⇒ **起服次数 = 4 构建 × 3 = 12 次**；**推理总量 23,328 次不变**
#   · **3 次独立起服**（每次全新进程 + 全新显存），用于估计服务栈方差（M.40 口径）
#   · 逐格落 `A52_<build>_<contract>_s<start>.csv`
#   · **可重入**：已存在且行数达标的格**直接跳过**（重跑不重复计费）——按 (build,contract,start) 重入
#   · 非 0 退出即写 `A52_ABORT_*` 并**停手**（不吞错；`set -o pipefail` —— 上一轮 `| tee` 吞过码）
#
# ── ★ 三条从既有脚本沿用的做法 ────────────────────────────────────────────────────────
#   ① **显式种子 + 一次落盘**：刺激由图生成器一次落盘、sha256 锁进 manifest，本脚本只**读**它
#      （`--manifest`）；绝不在运行时重渲染（旧生成器用 abs(hash(item)) 会在 PYTHONHASHSEED 下漂）
#   ② **gpu_clear() 守门**：起服前核目标卡；`> 2000 MiB` **拒跑**并写 `A52_ABORT_GPU_BUSY`
#      （沿用 P1-N 的守门）。AWQ 类常驻 ≈18–19 GiB 会命中此闸；如需在"已知 AWQ 常驻量"下开跑，
#      用 `A52_GPU_MEM_MIB=<n>` **显式放宽**（会落日志、须在判决书披露该次放宽值）
#   ③ **只按 PID 停自己的服务**（先核 `/proc/<pid>/cmdline` 含该构建的目标 `--port`）；
#      **绝不机器级 pkill、绝不用 `pkill -f`**；**绝不进 /root/cvpr_exp**
#
# ── ★ 构建 → 起服件映射（2026-10-04 A800 只读勘查实测；见方案 v2 §1）────────────────────
#   b0 = AWQ 4bit           /root/pf_serve_awq4bit_8013.sh  文件 md5 1eca04a1c22049e7a7ee077380387314
#                          model /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit  port 8013  served Qwen3-VL-32B-Instruct-AWQ   ✅齐备
#   b1 = FP8               ❌ **本机缺件**。反证：/root/models/Qwen3-VL-32B-Instruct-FP8 不存在
#                            （/root/p4_download.sh L45/L49 只**声明**该仓 19 文件/35.53 GB，从未落盘）；
#                            HF 缓存无 models--Qwen--Qwen3-VL-32B-Instruct-FP8；
#                            唯一 FP8-VL 服务件 pf_serve_fp8_tp2_8022.sh 服的是 **InternVL3_5-38B-FP8**（异族）且 **TP=2**（单卡不可用）。
#                            既有文档严禁用 `Qwen3-VL-32B-Thinking-FP8` 顶替 —— 不同变体，属造假。
#   b2 = BF16              /root/p3_serve_bf16_A.sh         文件 md5 7e291790a80646b3e0ba3a990282dd49
#                          model /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct  port 8012  served Qwen3-VL-32B-Instruct  ⚠️权重齐备
#   b3 = 第三方 4bit(GPTQ) ❌ **本机缺件**。反证：find /root /model -iname '*gptq*' 仅两件且均为**纯文本**
#                            （Qwen2.5-14B-Instruct-GPTQ-Int4=model_type qwen2、Qwen3.5-27b-GPTQ-Int4=model_type qwen3_5）；
#                            find -iname '*Qwen3-VL*GPTQ*' 为空（**无任何 VL 的 GPTQ 权重，也无 GPTQ 服务件**）。
# ★ 缺件处置**只由上级裁定**，本脚本不自动决定：
#     · 判据件 alias_rule 的合法处置 = 整体放弃重跑；
#     · 判据件 amendments[0].note 给的收缩路径 = 按 A52_BUILDS 收缩为实际可跑集合
#       ⇒ 默认 `A52_BUILDS` **只含本机可跑者**（b0,b2），并在判决书与披露项写明缺哪个。
# ★ **禁止**用 Thinking-FP8 顶 b1、用 38B-FP8/8B 顶 b1/b2、用 AWQ 件顶 b3。
# ★★ b3 的**特别禁令**：**不得**把 b0 的 `/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit` 换个 served-name 当 b3——
#     那是同一份权重（cyankiwi 仓）跑两遍 ⇒ "构建方差"退化，属**换标签冒充**。宁可收缩为 {b0,b2} 并如实披露。
#
# ── 用法（单卡；**先确认 GPU 空闲**）───────────────────────────────────────────────────
#   GPUID=0 bash /root/a52/a52_run.sh                      # 默认 A52_BUILDS="b0 b2"
#   GPUID=0 A52_BUILDS="b0 b2" bash /root/a52/a52_run.sh   # 显式收缩集（等价默认）
#   GPUID=0 A52_GPU_MEM_MIB=20000 bash /root/a52/a52_run.sh  # 上级批准后放宽显存闸门（须披露）
#   # 覆盖某构建的起服件（谨慎；只允许覆盖为**同类量化**的件，须在运行单记 md5）：
#   A52_SRV_b0=/root/xxx.sh A52_PORT_b0=8013 A52_SERVED_b0=... bash /root/a52/a52_run.sh
set -u
set -o pipefail
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
D=/root/a52
STIM=$D/stim
RES=$D/res
TAG=${TAG:-v2}
L=/root/logs/a52_${TAG}.log
PIDF=$D/a52_${TAG}.pid          # ★ 修 ②：按 TAG 隔离（原为共享 $D/a52.pid）
PROBE=$D/a52_probe.py
CRIT=$D/_a52_criteria_frozen.json
GPUID=${GPUID:-0}
N_IMG=${A52_N_IMG:-648}
THRESH_MIB=${A52_THRESH_MIB:-${A52_GPU_MEM_MIB:-2000}}
WORKERS=${A52_WORKERS:-4}
mkdir -p "$RES" /root/logs

say(){ echo "[$(date +%F_%T)] $*" | tee -a "$L"; }
abort(){ say "!! $*"; echo "A52_ABORT_$1" >> "$L"; stop_old_serve; exit "${2:-5}"; }

# 手写行列计数（不依赖 /usr/bin/wc，也不靠 python 单行 heredoc 的续行——P1-N 曾在续行上翻车）
count_rows(){
  local f="$1" n=0
  [ -f "$f" ] || { echo 0; return; }
  while IFS= read -r _; do n=$((n+1)); done < "$f"
  echo $(( n>0 ? n-1 : 0 ))
}
parse_ok_of(){
  # 从表头定位 parse_ok 列，再逐行取值 —— 不做子串猜测（`,1,` 那种会被 raw 里的数字骗到）
  local f="$1"
  [ -f "$f" ] || { echo 0; return; }
  awk -F, 'NR==1{for(i=1;i<=NF;i++) if($i=="parse_ok") c=i; next} c && $c==1 {n++} END{print n+0}' "$f"
}

gpu_used(){ nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPUID" 2>/dev/null | tr -d ' \r'; }

# ★ 按 cmdline 找进程：**只读 /proc**，不依赖 pgrep/pkill（远端与本机都稳；也避开"模式杀进程"）
pids_with_port(){           # $1 = 端口
  local port="$1" p
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    [ -r "/proc/$p/cmdline" ] || continue
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- "--port $port"; then echo "$p"; fi
  done
  return 0                 # ★ 修 ③：显式 return 0。原函数返回值=循环最后一次迭代状态（多为 1）
}
pids_with_name(){           # $1 = 脚本名（如 a52_run.sh）
  local nm="$1" p
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    [ -r "/proc/$p/cmdline" ] || continue
    tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- "$nm" && echo "$p"
  done
}

# ★ 当前构建的目标端口（用于停服时核 cmdline）；由 start_serve 设置
CUR_PORT=""
PIDF_MINE=0                       # ★ 修 ②：仅当本实例写过才允许删

stop_old_serve(){
  # ★ 只停**本脚本 PID 文件里**、且命令行含**当前构建目标端口**的进程；绝不机器级 pkill、绝不用 pkill -f
  [ -f "$PIDF" ] || return 0
  local p port="${CUR_PORT:-}"
  for p in $(cat "$PIDF" 2>/dev/null); do
    if [ -n "$port" ] && tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "--port $port"; then
      kill "$p" 2>/dev/null; say "  已停本脚本服务 pid=$p（已核 --port $port）"
    elif tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "--port "; then
      # 端口未记录但确是本脚本起过的 vllm：核到命令行含 --port 才停（仍按 PID，不做模式匹配杀进程）
      kill "$p" 2>/dev/null; say "  已停本脚本服务 pid=$p（已核 cmdline 含 --port）"
    else
      say "  跳过 pid=$p（命令行不含 --port ⇒ 不是本脚本的服务）"
    fi
  done
  # ★ 修 ②c：PID 文件已按 TAG 隔离，且仅"本实例写过"时才删
  if [ "${PIDF_MINE:-0}" = "1" ]; then rm -f "$PIDF"; PIDF_MINE=0; fi
  # ★ 修 ④（稳健性）：不再死等 8 s，改为轮询显存回落到闸门阈值以下（最多 13×3 = 39 s）
  local _i _u
  for _i in $(seq 1 13); do
    sleep 3
    _u=$(gpu_used)
    [ -n "$_u" ] && [ "$_u" -le "$THRESH_MIB" ] && break
  done
}

gpu_clear(){
  # ★ 沿用 P1-N 的守门逻辑：目标卡 > 阈值就**不抢卡**（先清自己的旧服，再看卡）
  local used
  stop_old_serve
  used=$(gpu_used)
  if [ -z "$used" ]; then abort BAD_GPU 7; fi
  if [ "$used" -gt "$THRESH_MIB" ]; then
    say "!! GPU$GPUID 已用 ${used} MiB > 阈值 ${THRESH_MIB} MiB ⇒ 不抢卡，停手"
    abort GPU_BUSY 6
  fi
  say "  gpu_clear：GPU$GPUID = ${used} MiB（阈值 ${THRESH_MIB}）⇒ 可以起服"
}

start_serve(){
  # $1 = build 别名（日志/map 用）, $2 = 起服脚本绝对路径, $3 = served-name, $4 = 目标端口, $5 = 模型目录（仅记日志）
  local b="$1" srv="$2" sname="$3" port="$4" mpath="${5:-}"
  CUR_PORT="$port"
  stop_old_serve
  gpu_clear
  [ -f "$srv" ] || abort "NO_SRV_${b}" 3
  say "  起服 $b：srv=$srv（md5 $(md5sum "$srv" | awk '{print $1}')）port=$port served=$sname"
  say "         model=$mpath"
  echo "$b|$srv|$(md5sum "$srv" | awk '{print $1}')|$mpath|$port|$sname" >> "$D/a52_builds.map"
  CUDA_VISIBLE_DEVICES=$GPUID GMEM_UTIL=${GMEM_UTIL:-0.85} setsid nohup bash "$srv" \
    > "/root/logs/a52_serve_${TAG}_$(echo "$sname" | tr -c 'A-Za-z0-9._-' '_').log" 2>&1 </dev/null &
  sleep 20
  # 只记**我们刚起的这批** vllm 的 PID：按目标端口从 /proc 抓（起服脚本 exec 后 cmdline 保留 --port）
  # ★ 修 ③b：原写法 `|| : > "$PIDF"` 在函数返回 1 时把**刚写进去的 PID 清空**（实测 size 5→0）
  pids_with_port "$port" > "$PIDF" 2>/dev/null || true
  PIDF_MINE=1
  local ok=0 i
  for i in $(seq 1 90); do
    sleep 10
    curl -sS -m 5 "http://127.0.0.1:$port/v1/models" 2>/dev/null | grep -q "$sname" && { ok=1; break; }
  done
  [ $ok -eq 1 ] || { say "  !! 起服未就绪（等待 $((i*10))s）"; return 1; }
  say "  起服就绪（等待 $((i*10))s）｜ served=$sname ｜ GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  return 0
}

# ── 构建目录表：`起服脚本|端口|served-name|模型目录`（★ 用 `|` 分隔，不用 `:`——
#    路径里可能含 `:`（Windows 盘符 / 带冒号的目录名），冒号分隔会把脚本路径截断）
#    ★ 本表 = 2026-10-04 A800 **只读勘查实测**（详见方案 v2 §1）；跑前冻结，跑时不得改。
#      b1 缺件反证：/root/models/Qwen3-VL-32B-Instruct-FP8 不存在（p4_download.sh L45/L49 只声明未落盘）；
#                    HF 缓存无 models--Qwen--Qwen3-VL-32B-Instruct-FP8；
#                    唯一 FP8-VL 服务件 pf_serve_fp8_tp2_8022.sh 服的是 InternVL3_5-38B-FP8 且 TP=2。
#      b3 缺件反证：find /root /model -iname '*gptq*' 仅得两件纯文本模型
#                    （Qwen2.5-14B-Instruct-GPTQ-Int4=model_type qwen2、Qwen3.5-27b-GPTQ-Int4=model_type qwen3_5）；
#                    find -iname '*Qwen3-VL*GPTQ*' 为空。
#      ★★ **严禁顶替**：b1 不得用 Qwen3-VL-32B-Thinking-FP8（不同变体）/ 38B-FP8 / 8B；
#                    **b3 尤其不得复用 b0 的 /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit**
#                    （那是同一份权重换文件名 ⇒ "构建方差"退化成"同一构建跑两遍"，属换标签冒充）。
build_spec(){
  case "$1" in
    b0) echo "/root/pf_serve_awq4bit_8013.sh|8013|Qwen3-VL-32B-Instruct-AWQ|/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit" ;;
    b1) echo "|8014|Qwen3-VL-32B-Instruct-FP8|" ;;                       # ❌ 本机缺件（禁顶替）
    b2) echo "/root/p3_serve_bf16_A.sh|8012|Qwen3-VL-32B-Instruct|/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct" ;;
    b3) echo "|8015|Qwen3-VL-32B-Instruct-GPTQ|" ;;                       # ❌ 本机缺件（★ 禁拿 b0 的 AWQ 件顶）
    *)  echo "" ;;
  esac
}

say "===== A5-2 启动（单卡 GPU$GPUID；按构建分阶段：外层构建 × 内层合同×起服；$N_IMG 图/格）====="

# ★ 已跑完/已在跑就不重复起（最贵的错误是"两条编排同时抢同一张卡"）
#   注意：**调用者自己的 cmdline 里也会有脚本名**（如 `bash /root/a52/a52_run.sh`），
#   故必须排除 $$ 与 $PPID，否则会把自己的启动命令误判成"已有实例在跑"。
if grep -q '^A52_ALL_DONE' "$L" 2>/dev/null; then
  # ★ 收缩过的那轮也算"完成"，但**不得**让它掩盖"四构建从未跑过"这一事实：
  #   若上一轮是收缩集而本次要跑更大的构建集 ⇒ 必须显式停手，由人决定是否归档日志重跑。
  PREV_SHRUNK=0
  grep -q '^A52_ALL_DONE_SHRUNK' "$L" 2>/dev/null && PREV_SHRUNK=1
  if [ "$PREV_SHRUNK" -eq 1 ]; then
    say "!! 日志里已有 A52_ALL_DONE**且上一轮是收缩集**（A52_ALL_DONE_SHRUNK）"
    say "   ⇒ 本轮**不自动跳过**：本次构建集若含上一轮缺的构建，请先归档 $L 再开跑；"
    say "      若确认只需收缩集结果，则本轮无需重跑。**停手等裁定**。"
    echo "A52_ABORT_PREV_SHRUNK_NEEDS_RULING" >> "$L"; exit 9
  fi
  say "日志里已有 A52_ALL_DONE ⇒ 本轮视为已完成，跳过（要重跑请先归档日志）"; exit 0
fi
# ★ 修 ①：原写法用 `pids_with_name 'a52_run.sh'` 扫 /proc，而 bash 为 `$( … )` fork 的子壳
#        **继承同一 argv**（/proc/<sub>/cmdline = "bash …/a52_run.sh"），它们既不是 $$ 也不是 $PPID
#        ⇒ 守门必然抓到自己 ⇒ **永远起不来**（本轮实测：full_list=[self, ppid, 子壳, 子壳]）。
#        改为**原子锁目录**：持有者 PID + kill -0 存活校验 + 陈旧锁清理 + EXIT trap 释放。
LOCKD=$D/a52.lock
mkdir -p "$D"
if ! mkdir "$LOCKD" 2>/dev/null; then
  OLD=""
  [ -f "$LOCKD/pid" ] && OLD=$(cat "$LOCKD/pid" 2>/dev/null || true)
  if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
    say "!! 已有实例在跑（锁 $LOCKD，pid $OLD）⇒ 不并发开跑，停手"
    echo "A52_ABORT_ALREADY_RUNNING" >> "$L"; exit 8
  fi
  say "  发现陈旧锁（pid '${OLD:-空}' 已不存在）⇒ 清理后继续"
  rm -rf "$LOCKD"                      # 只删本脚本自己的锁目录
  mkdir "$LOCKD" 2>/dev/null || { say "!! 锁竞争失败 ⇒ 停手"; echo "A52_ABORT_ALREADY_RUNNING" >> "$L"; exit 8; }
fi
echo $$ > "$LOCKD/pid"
trap 'rm -rf "$LOCKD" 2>/dev/null' EXIT

say "判据件 md5=$(md5sum "$CRIT" 2>/dev/null | awk '{print $1}')"
say "探针 md5=$(md5sum "$PROBE" 2>/dev/null | awk '{print $1}')"
say "刺激 manifest md5=$(md5sum "$STIM/manifest.csv" 2>/dev/null | awk '{print $1}')"

# ── 预检①：判据件/探针/刺激齐备，且探针自检通过（可逆性/唯一性/语法）──────────────
[ -f "$CRIT" ] || abort NO_CRIT 3
[ -f "$PROBE" ] || abort NO_PROBE 3
[ -f "$STIM/manifest.csv" ] || abort NO_STIM 3
$PY -B "$PROBE" --selftest >> "$L" 2>&1 || abort PROBE_SELFTEST 3
say "  探针自检通过（提示词可逆/解析器 12 条用例/判据一致）"

# ── 预检②：刺激覆盖（648 图 / 81 格 / sha256 齐；C1 分母 = 78 格，3 格预注册排除）─────
$PY -B "$PROBE" --show-prompts >> "$L" 2>&1 || true
NCELL=$($PY -B - "$STIM/manifest.csv" "$STIM/_unrealizable.csv" <<'PYEOF'
import csv, io, os, sys
rows = list(csv.DictReader(io.open(sys.argv[1], encoding='utf-8-sig', newline='')))
cells = {r['cell_id'] for r in rows}
unreal = set()
p2 = sys.argv[2]
if os.path.isfile(p2):
    for r in csv.DictReader(io.open(p2, encoding='utf-8-sig', newline='')):
        v = r.get('cell_id') or r.get('cell') or ''
        if v: unreal.add(v)
print(len(rows), len(cells), sum(1 for r in rows if len(r.get('sha256','')) == 64), len(cells - unreal))
PYEOF
)
say "  刺激：行/格/sha256齐/非空格 = $NCELL（应 $N_IMG 81 $N_IMG 78）"
[ "${NCELL%% *}" = "$N_IMG" ] || abort STIM_ROWS 3
# C1 分母断言：81 − 预注册排除 = 78（排除件缺失即停手，防"事后剔除"）
NREAL=${NCELL##* }
[ "$NREAL" = "${A52_N_REAL:-78}" ] || abort STIM_CELLS 3

# ── 构建清单：默认只含**本机实测可跑者**（b0 AWQ4bit、b2 BF16）────────────────────────
#    ★ b1(FP8)/b3(GPTQ) 本机缺件；判据件 amendments[0].note 允许收缩，但**须上级裁定**
BUILDS=${A52_BUILDS:-"b0 b2"}
CONTRACTS=${A52_CONTRACTS:-"base strict permit"}
STARTS=${A52_STARTS:-"1 2 3"}
NB=0; for _b in $BUILDS; do NB=$((NB+1)); done
NS=0;   for _s in $STARTS;   do NS=$((NS+1)); done
NC=0;   for _c in $CONTRACTS; do NC=$((NC+1)); done
TOTAL_CELLS=$(( NB * NC * NS ))
say "构建集 = [$BUILDS]（$NB 个）｜合同 = [$CONTRACTS]｜起服 = [$STARTS] ⇒ 格数 = $TOTAL_CELLS；起服次数 = $(( NB * NS ))"
if [ "$NB" -lt 4 ]; then
  say "!! ★ 构建集 < 4：按判据件 amendments[0].note 的**收缩路径**运行 ⇒ 判决书与披露项**必须**写明缺哪个构建（缺 b1=FP8、b3=GPTQ）"
  echo "A52_BUILDS_SHRUNK builds=[$BUILDS] missing=b1(FP8),b3(GPTQ)" >> "$L"
fi

# ── 主循环：**外层构建** → 起服（每构建 NS 次）→ 内层合同（每起服一次）──────────────
DONE_CELLS=0
: > "$D/a52_builds.map"
for B in $BUILDS; do
  SPEC=$(build_spec "$B")
  [ -n "$SPEC" ] || abort "UNKNOWN_BUILD_${B}" 3
  # 用 `|` 拆字段（路径里可能有 `:`；也**不用 eval**，避免把值当代码执行）
  SRV=${SPEC%%|*}; rest=${SPEC#*|}
  PORT=${rest%%|*}; rest=${rest#*|}
  SNAME=${rest%%|*}; MPATH=${rest#*|}
  # 逐项允许 `A52_<FIELD>_<build>` 覆盖（用 `-` 而非 `:-`：空值也算"显式给了空"，但这一层只做覆盖）
  eval "SRV=\${A52_SRV_${B}-\$SRV}"
  eval "PORT=\${A52_PORT_${B}-\$PORT}"
  eval "SNAME=\${A52_SERVED_${B}-\$SNAME}"
  eval "MPATH=\${A52_MODEL_${B}-\$MPATH}"
  say "===== 构建 $B：srv='$SRV' port=$PORT served=$SNAME model='$MPATH' ====="
  [ -f "$SRV" ] || { say "!! 构建 $B 缺起服件 '$SRV'（本机实测缺件）⇒ 停手"; abort "NO_SRV_${B}" 3; }
  for S in $STARTS; do
    say "----- $B 起服 $S / $NS -----"
    start_serve "$B" "$SRV" "$SNAME" "$PORT" "$MPATH" || abort "SERVE_${B}_s${S}" 4
    # ★ 每构建每次起服后跑探针自检（证明"换构建没换尺子"）
    $PY -B "$PROBE" --selftest >> "$L" 2>&1 || abort "PROBE_SELFTEST_${B}_s${S}" 3
    say "  探针自检通过（$B/s$S）"
    for CT in $CONTRACTS; do
      OUT=$RES/A52_${B}_${CT}_s${S}.csv
      n=$(count_rows "$OUT")
      # ★ 满格判据 = 648 行（= 648 张图/格）；任务书里的"250 行齐"是对既有小池（253 项）口径的串写，
      #   本项目 A5-2 的每格满行数以判据件为准 = 648 ⇒ 这里用 N_IMG。
      if [ "$n" -ge "$N_IMG" ]; then
        say "  跳过（已存在且达标）：$B/$CT/s$S = $n 行"
        DONE_CELLS=$((DONE_CELLS+1)); continue
      fi
      say "  开跑 $B/$CT/s$S（期望 $N_IMG 行；port=$PORT）"
      $PY -u "$PROBE" --api "http://127.0.0.1:${PORT}/v1/chat/completions" \
          --model "$SNAME" --served-model "$SNAME" \
          --grid "$STIM" --manifest "$STIM/manifest.csv" \
          --build "$B" --contract "$CT" --start "$S" \
          --out "$OUT" --workers "$WORKERS" >> "$L" 2>&1
      rc=$?
      [ $rc -ne 0 ] && abort "PROBE_RC_${B}_${CT}_s${S}" 5
      n=$(count_rows "$OUT")
      ok=$(parse_ok_of "$OUT")
      say "  结束 $B/$CT/s$S -> $n 行（parse_ok=$ok）｜ md5 $(md5sum "$OUT" | awk '{print $1}')"
      if [ "$n" -lt "$(( N_IMG * 95 / 100 ))" ]; then
        say "  !! 行数偏少（<95%）"; echo "A52_COUNT_LOW_${B}_${CT}_s${S} rows=$n" >> "$L"
        abort COUNT_LOW 5
      fi
      if [ "$(( ok * 100 ))" -lt "$(( n * 95 ))" ]; then
        say "  !! parse_ok < 95% ⇒ 停手（判据 C2）"; echo "A52_PARSE_LOW_${B}_${CT}_s${S}" >> "$L"
        abort PARSE_LOW 5
      fi
      DONE_CELLS=$((DONE_CELLS+1))
    done
    stop_old_serve
    say "  $B 起服 $S 已收服；GPU 现 = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  done
  say "===== 构建 $B 完成（$NC 合同 × $NS 起服）====="
done

stop_old_serve
say "--- 产物 ---"
for f in "$RES"/A52_*.csv; do
  [ -f "$f" ] || continue
  say "  $(md5sum "$f" | awk '{print $1}')  $(count_rows "$f") 行  $f"
done
say "收尾 GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
say "完成格数 = $DONE_CELLS / $TOTAL_CELLS"
[ "$DONE_CELLS" -eq "$TOTAL_CELLS" ] || abort INCOMPLETE 5
if [ "$NB" -lt 4 ]; then
  say "!! 完成但**构建集已收缩**（$NB/4）⇒ 判决书与披露项须写明缺 b1(FP8)/b3(GPTQ)"
  echo "A52_ALL_DONE_SHRUNK builds=$NB/$TOTAL_CELLS cells=$TOTAL_CELLS" >> "$L"
fi
echo A52_ALL_DONE >> "$L"
say "===== A5-2 结束（$(( N_IMG * TOTAL_CELLS )) 次）====="
