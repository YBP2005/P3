
p = '/root/10_aerial_vlm.py'
s = open(p, encoding='utf-8').read()
if 'AER_OUT' not in s:
    s = s.replace("OUT = '/root/aerial_results'", "OUT = os.environ.get('AER_OUT', '/root/aerial_results')")
    open(p, 'w', encoding='utf-8').write(s)
    print('已加 AER_OUT')
else:
    print('已有 AER_OUT')
