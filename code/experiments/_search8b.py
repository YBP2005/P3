
import json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
def get(u):
    req = urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())
for q in ['Qwen3-VL-8B-Instruct-AWQ', 'Qwen3-VL-8B-AWQ', 'Qwen3-VL-8B-Instruct']:
    try:
        j = get('https://huggingface.co/api/models?search=%s&limit=10' % q.replace('/', '-'))
        print('[%s]' % q)
        for m in j[:8]:
            print('   ', m['id'], 'downloads=', m.get('downloads'))
    except Exception as ex:
        print('[%s] 失败 %s' % (q, str(ex)[:60]))
