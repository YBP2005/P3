#!/bin/bash
# 启动扩展实验（自己会等 exp.sh 结束）；同时停掉那条会失败到 /model 的下载
if pgrep -f 'h20_dl_extra' > /dev/null 2>&1; then
  pkill -9 -f 'h20_dl_extra' && echo "已停掉无效的 dl_extra（/model 只读）"
fi
if pgrep -f 'h20_exp_extra' > /dev/null 2>&1; then echo "扩展实验已在运行"; exit 0; fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/h20_exp_extra.sh < /dev/null > /root/logs/exp_extra_stdout.log 2>&1 &
echo "EXP_EXTRA_LAUNCHED pid=$!"
