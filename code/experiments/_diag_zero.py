
import base64, io, json, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

API = 'http://127.0.0.1:8000/v1/chat/completions'
def call(im, prompt, extra=None):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model':'qwen3-vl-32b-awq','messages':[{'role':'user','content':[
        {'type':'image_url','image_url':{'url':url}},
        {'type':'text','text':prompt}]}],'temperature':0.0,'max_tokens':64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.loads(r.read().decode())
    return j

PR = '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。'

CASES = [
    ('ST-A 失败样本', '/root/dense/shanghaitech/images/part_A_test/IMG_106.jpg'),
    ('ST-A 成功样本', '/root/dense/shanghaitech/images/part_A_test/IMG_102.jpg'),
    ('UCF 失败样本',  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test/img_0012.jpg'),
]
for tag, p in CASES:
    if not os.path.exists(p):
        print(tag, '文件不存在', p); continue
    im = Image.open(p).convert('RGB')
    W, H = im.size
    print('=== %s ===' % tag)
    print('  路径 %s' % os.path.basename(p))
    print('  原始尺寸 %dx%d = %.2f Mpx' % (W, H, W*H/1e6))
    # ① 原尺寸直接送（若 <1Mpx）；② 统一缩到 0.7Mpx；③ 缩到 0.25Mpx
    variants = [('原尺寸', im)]
    for name, target in [('缩到1Mpx', 1048576), ('缩到0.7Mpx', 700000), ('缩到0.25Mpx', 250000)]:
        s = (target / float(W*H)) ** 0.5
        variants.append((name, im.resize((max(1,int(W*s)), max(1,int(H*s))))))
    for name, v in variants:
        try:
            j = call(v, PR)
            out = j['choices'][0]['message']['content']
            u = j.get('usage', {})
            fr = j['choices'][0].get('finish_reason')
            print('  [%s] %dx%d -> 回答 %s | tokens=%s finish=%s' % (
                name, v.size[0], v.size[1], out[:60], u.get('prompt_tokens'), fr))
        except Exception as ex:
            print('  [%s] 失败 %s' % (name, str(ex)[:80]))
    print()
