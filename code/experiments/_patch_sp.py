
import sys, shutil, os
sys.path.insert(0, '/root/vllm312/lib/python3.12/site-packages')
import sentencepiece.sentencepiece_model_pb2 as pb

P = '/root/models/InternVL2_5-8B-AWQ/tokenizer.model'
BAK = P + '.orig'

if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print('已备份 ->', BAK)
else:
    print('备份已存在，跳过')

mp = pb.ModelProto()
mp.ParseFromString(open(P, 'rb').read())
print('总 piece 数:', len(mp.pieces))

bad = [(i, p.piece, p.type, round(p.score, 3)) for i, p in enumerate(mp.pieces) if chr(0) in p.piece]
print('含 NUL 的 piece:', bad)

existing = {p.piece for p in mp.pieces}
PH = '<|NULPLACEHOLDER|>'
while PH in existing:
    PH += '_'
print('选用占位串:', PH, ' 是否与现有词冲突:', PH in existing)

for i, piece, typ, sc in bad:
    mp.pieces[i].piece = PH

open(P, 'wb').write(mp.SerializeToString())
print('已写回，新大小:', os.path.getsize(P))

# 校验
import sentencepiece as spm, importlib.metadata as m
print('sentencepiece 版本:', m.version('sentencepiece'))
try:
    s = spm.SentencePieceProcessor(model_file=P)
    print('加载成功！vocab =', s.get_piece_size())
    print('编码测试:', s.encode('请数出图片中的人数', out_type=int))
    print('往返:', s.decode(s.encode('请数出图片中的人数', out_type=int)))
    print('id354 ->', repr(s.id_to_piece(354)))
except Exception as e:
    print('仍失败:', type(e).__name__, e)
