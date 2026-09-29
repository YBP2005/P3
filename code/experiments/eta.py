
import re, sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
log = open('/root/logs/install.log', encoding='utf-8', errors='ignore').read()
log = log.replace('\r', '\n')

# 1) 所有待下文件的声明大小（pip: "Downloading name-1.2.3.whl (123.4 MB)"）
decl = {}
for m in re.finditer(r'Downloading (\S+?)\s+\(([\d.]+) ([kMG]?B)\)', log):
    name, val, unit = m.group(1), float(m.group(2)), m.group(3)
    mult = {'B': 1, 'kB': 1e3, 'KB': 1e3, 'MB': 1e6, 'GB': 1e9}.get(unit, 1)
    decl[name] = val * mult

# 2) 已完成的（进度条 100% 行： "  123.4/123.4 MB 1.2 MB/s 0:01:40"）
done = {}
cur = None
for line in log.split('\n'):
    m = re.search(r'^\s*([\d.]+)/([\d.]+) (k?M?G?B)\s+([\d.]+) (k?M?G?B)/s', line.strip())
    if m:
        frac = float(m.group(1)) / max(float(m.group(2)), 1e-9)
        key = cur
        if key:
            done[key] = max(done.get(key, 0), frac)
    m2 = re.search(r'Downloading (\S+?)\s+\(', line)
    if m2:
        cur = m2.group(1)

total = sum(decl.values())
got = sum(decl.get(k, 0) * v for k, v in done.items())
rate = 0.0
for m in re.finditer(r'([\d.]+) (k?M?G?B)/s', log):
    v, u = float(m.group(1)), m.group(2)
    mult = {'B': 1, 'kB': 1e3, 'KB': 1e3, 'MB': 1e6, 'GB': 1e9}.get(u, 1)
    rate = v * mult      # 取最后一个

print('已声明文件数: %d, 总大小: %.2f GB' % (len(decl), total / 1e9))
print('完成度: %.1f%% (已下 %.2f GB)' % (100 * got / max(total, 1), got / 1e9))
print('最近速率: %.2f MB/s' % (rate / 1e6))
rem = max(0.0, total - got)
if rate > 1000:
    print('剩余: %.2f GB  预计还需 %.0f 分钟' % (rem / 1e9, rem / rate / 60))
else:
    print('剩余: %.2f GB  速率未知' % (rem / 1e9))
print()
print('--- 尚未完成的文件一览 ---')
pending = [(k, v) for k, v in sorted(decl.items(), key=lambda x: -x[1]) if done.get(k, 0) < 0.999]
for k, v in pending[:12]:
    print('   %-58s %8.1f MB  已完成 %.0f%%' % (k[:58], v / 1e6, done.get(k, 0) * 100))
print()
print('--- 日志尾部 ---')
print('\n'.join([l for l in log.split('\n') if l.strip()][-6:]))
print('--- pip 进程 ---')
print(os.popen('pgrep -af "pip install" | head -2').read())
print('--- 磁盘 ---')
print(os.popen('df -h / | tail -1').read())
