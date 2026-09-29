
import base64, io, json, os, sys, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
API = 'http://127.0.0.1:8000/v1/chat/completions'

PROMPTS = {
 'A_base_原样': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
 'B_over原样':  '请数出图片中的人数。为避免漏数，请把所有可能存在的目标都计入（包括被遮挡、距离较远、画面模糊、只露出部分的个体）；宁可多算，不可漏算。以JSON格式输出：{"count": 数量}，只输出JSON。',
 'C_极简':      '图中有多少人？只输出一个阿拉伯数字。',
 'D_同义改写':  '请统计图中的人数，以JSON格式输出：{"count": 数量}，只输出JSON。',
 'E_去括号':    '请数出图片中的人数，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
 'F_英文':      'Count the number of people in this image. Output JSON: {"count": N}',
}

def call(im, prompt, seed=None):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model':'qwen3-vl-32b-awq','messages':[{'role':'user','content':[
        {'type':'image_url','image_url':{'url':url}},
        {'type':'text','text':prompt}]}],'temperature':0.0,'max_tokens':64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.loads(r.read().decode())
    return j['choices'][0]['message']['content'], j.get('usage',{}), time.time()-t0

CASES = [('ST-A IMG_106 (GT 1232)', '/root/dense/shanghaitech/images/part_A_test/IMG_106.jpg'),
         ('UCF img_0012 (GT 434)',  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test/img_0012.jpg'),
         ('ST-A IMG_102 (GT 223, 曾成功)', '/root/dense/shanghaitech/images/part_A_test/IMG_102.jpg')]

for tag, p in CASES:
    im = Image.open(p).convert('RGB')
    print('=== %s  %dx%d ===' % (tag, im.size[0], im.size[1]))
    for name, pr in PROMPTS.items():
        try:
            out, u, dt = call(im, pr)
            print('   %-12s -> %-24s (%.1fs, ptok=%s)' % (name, out.replace(chr(10),' ')[:24], dt, u.get('prompt_tokens')))
        except Exception as ex:
            print('   %-12s -> 失败 %s' % (name, str(ex)[:60]))
    print()
