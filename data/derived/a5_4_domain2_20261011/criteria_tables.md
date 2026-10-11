# Criteria table — second target-matched domain (rendered family, true zeros by construction)

Design: **1,000** rendered images over a parameter family whose size, blur and overlap settings are
disjoint from the corpora used elsewhere in this work, each with its **own** target word naming the object
actually drawn, and a frozen per-image sha256. Four builds were run under three response contracts:
**1,000 × 3 × 4 = 12,000** cells, all served with HTTP 200. One repetition per cell.
**100 of the 1,000 images (10%) contain no target at all** (`count_gt = 0`).

Because the pool contains true zeros, `P(true zero | answered zero)` **is identifiable in this domain**,
unlike the public-benchmark frame.

## Per build, `base` arm

| build | numeric replies | zero among those | zero rate among numeric | distinct images with a zero | true-zero images | `P(true zero \| answered zero)` | true-zero recall | median MAE | mean MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rec_b03 | 942 | 63 | 0.0669 | 63 | 100 | **1.000** | **0.63** | 7 | 21.87 |
| rec_b01 | 999 | 96 | 0.0961 | 96 | 100 | **1.000** | **0.96** | 5 | 11.11 |
| rec_b02 | 1000 | 100 | 0.1000 | 100 | 100 | **1.000** | **1.000** | 2 | 6.93 |
| rec_b04 | 1000 | 100 | 0.1000 | 100 | 100 | **1.000** | **1.000** | 8 | 17.85 |

Definitions: `P(true zero | answered zero)` = answered-zero items that are true zeros / answered-zero
items; true-zero recall = answered-zero items that are true zeros / true-zero images; true-zero images =
the 100 images constructed so that the asked target is absent.

## Scope statement that must accompany this table

The share of true-zero images (**10%**) is a property of the design and must be stated wherever a rate
from this table is quoted. Without it, this domain's higher zero rates would be misread as a property of
the models rather than of the pool.

## All cells served

Per build, 3,000 records; 12,000 in total; every record carries `http = 200` and there is no missing cell.

## Parsing note

Numeric replies are matched in the verbatim reply text, and `abstain`, `cannot_judge` and `no_people` are
treated as non-numeric outlets.
