# -*- coding: utf-8 -*-
# A5 兼容垫片：从 transformers 4.57.1 的 models/pixtral/modeling_pixtral.py
# 取出的**原始实现**，仅用于补上 transformers 5.x 移除的符号。
import torch

def position_ids_in_meshgrid(patch_embeds_list, max_width):
    positions = []
    for patch in patch_embeds_list:
        height, width = patch.shape[-2:]
        mesh = torch.meshgrid(torch.arange(height), torch.arange(width), indexing="ij")
        h_grid, v_grid = torch.stack(mesh, dim=-1).reshape(-1, 2).chunk(2, -1)
        ids = h_grid * max_width + v_grid
        positions.append(ids[:, 0])
    return torch.cat(positions)
