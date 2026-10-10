# A5-1 target-word pairing: released-file map (v0667)

The supplement reports a target-word pairing experiment on **300 FSC-147 images**, under **two
target-word conditions side by side**: the original *people* wording, and the **per-image target
class** taken from the dataset's own class list. Each condition was evaluated under the **three
response contracts** `base`, `permit`, `channel`, with **three independent service starts per cell**
(300 x 4 builds x 2 conditions x 3 arms x 3 starts = **21,600** served cells).

The per-call records are released under **neutral build names**; the mapping to the served
implementations is given below. Nothing in the released bytes was altered.

| released file prefix | served implementation |
|---|---|
| `rec_b01` | `InternVL3_5-8B` |
| `rec_b02` | `InternVL3_5-38B-FP8` |
| `rec_b03` | `llava-onevision-qwen2-7b-ov` |
| `rec_b04` | `Qwen3-VL-32B-Instruct-FP8` |

File names are `<build>_<condition>_rep<n>.jsonl`, one file per build x condition x start;
each file holds all three arms of that cell (`arm` field, 300 items per arm).

| field | meaning |
|---|---|
| `arm` | response contract: `base` (number only), `permit` (number or an abstention token), `channel` (a three-option reply) |
| `cond` | target-word condition: `people` (fixed wording) or `class` (per-image target class) |
| `rep` | independent service start, 1-3 |
| `class_name` | the frozen per-image target class used in the `class` condition |
| `gt` | the dataset's own point-annotation count for that image |
| `raw` | the verbatim reply; `pred`/`abstain`/`parse_ok` are the first-pass parse of it |
| `http` | transport status of the call; only `200` rows enter the analysis |

`target_map.csv` is the **frozen instrument**: per image, the target class, the ground-truth count
and the six prompt strings (2 conditions x 3 contracts). `criteria_a51.py` regenerates
`A5-1_判据表.md` / `A5-1_判据表.csv` from `raw/*.jsonl` alone, and running it on the released files
reproduces the released tables byte for byte. `reparse_a51.py` re-derives the per-cell numeric /
abstention counts from the stored `raw` replies without any new model call.

One cell's item is a degenerate repeat (`finish = length`) and is retained as missing rather than
imputed; it is named in the criteria table.
