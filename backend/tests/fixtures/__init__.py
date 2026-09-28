"""题池 fixture（v0.5 §3 题库基础 + 反马太判据 D-47）。

- questions_tier_demo.json — D-47 #1 固定测试章节 fixture（D/C/B/A 各档示例）
- questions_pool.jsonl   — D-47 #2 大池（一题一行 JSONL，diff 干净）

Schema 匹配 backend/app/models/academic.py Question 模型：
- difficulty: 'D' | 'C' | 'B' | 'A' (QuestionDifficulty enum)
- type:       'choice' | 'fill' | 'subjective' (QuestionType enum)
- chapter_ref / knowledge_points[] — loader 解析为 FK + M2M
- owner: 单文件内全部题目的归属用户（loader 创建）
"""
