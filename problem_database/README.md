# Math Competition Problem Database

A collection of math competition problems from various sources.

## Structure

```
problem_database/
├── books/          # Problems extracted from PDF books
│   ├── volume1/    # 不等式的秘密 第1卷 (309 problems)
│   ├── volume2/    # 不等式的秘密 第2卷 (113 problems)
│   ├── tip4/       # 小蓝本 卷4 (134 problems)
│   ├── tip9/       # 小蓝本 卷9 (102 problems)
│   └── all_books.json
├── aops/           # Problems from AoPS Wiki
│   ├── imo.json    # IMO problems (384)
│   ├── cmo.json    # CMO problems (8)
│   └── all_aops.json
├── datasets/       # Large datasets
│   ├── aops_hf_split/      # 80,661 problems (81 batch files)
│   │   ├── batch_0000/problems.json
│   │   ├── batch_0001/problems.json
│   │   └── ... (81 batches total)
│   └── olympiadbench.json   # 7,430 problems
└── index.json
```

## Total: ~89,000+ problems

## Sources

- **Books**: 不等式的秘密, 小蓝本
- **AoPS Wiki**: https://artofproblemsolving.com/wiki/
- **AI-MO/aops**: https://huggingface.co/datasets/AI-MO/aops
- **OlympiadBench**: https://huggingface.co/datasets/Hothan/OlympiadBench
