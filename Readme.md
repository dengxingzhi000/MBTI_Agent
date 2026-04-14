# 🎭 互联网梗人格测试 Agent v2

**Streamlit + DeepSeek API + SQLite + ChromaDB**

15 道渐进式灵魂拷问，数据双库持久化，向量相似人格检索。

---

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API Key
export DEEPSEEK_API_KEY="sk-xxxxxxxx"

# 3. 启动
streamlit run app.py
# → http://localhost:7860
```

---

## 项目结构

```
mbti_streamlit/
├── app.py                  # Streamlit 主程序（UI + 路由）
├── requirements.txt
├── .streamlit/
│   └── config.toml         # 主题配置（深色紫调）
├── utils/
│   ├── ai_engine.py        # DeepSeek 调用 + Prompt 工程
│   └── db.py               # SQLite + ChromaDB 数据层
└── data/                   # 运行时自动生成
    ├── mbti_meme.db        # SQLite 数据库
    └── chroma_store/       # ChromaDB 向量持久化目录
```

---

## 系统架构

```
用户操作
   │
   ▼
Streamlit Session State（状态机）
   │  phase: welcome → testing → generating → result → dashboard
   │
   ├─ ai_engine.py
   │    ├── generate_question()   按阶段出题，携带历史 context
   │    └── generate_result()     15题综合分析，返回结构化 JSON
   │
   └─ db.py
        ├── SQLite               结构化存储
        │    ├── test_sessions   会话记录
        │    ├── question_answers 每道题回答
        │    ├── personality_results 人格结果
        │    └── question_cache  题目缓存
        │
        └── ChromaDB（向量库）
             ├── store_personality_vector()  存入人格向量
             └── find_similar_personalities() 相似度检索
```

---

## 15 道题三阶段设计

| 阶段 | 题目 | 风格 | 主题 |
|------|------|------|------|
| 🌱 热身 | 1-5 | 接地气，日常化 | 刷手机习惯、社交行为、表情包 |
| ⚡ 觉醒 | 6-10 | 开始哲理，有梗 | 人生态度、躺平/卷、金钱观 |
| 🌀 飞升 | 11-15 | 极度抽象，意识流 | 存在主义、赛博孤独、虚无感 |

AI 会根据用户前几道题的回答画像，**动态调整**后续题目方向。

---

## 七大人格维度

| 维度 | 极值A | 极值B | 中间态 |
|------|-------|-------|--------|
| E/I 社交轴 | 社牛 | 社恐 | 薛定谔社交人 |
| 抽象/具体轴 | 抽象派 | 实用派 | 量子叠加态 |
| 感性/理性轴 | 感性派 | 理智派 | 情绪化理性人 |
| 躺/卷轴 | 躺平大师 | 卷王 | 躺着卷 |
| 混沌/秩序轴 | 混沌中立 | 秩序卫士 | 随机应变者 |
| 网感轴 | emo体质 | 快乐星球 | — |
| 存在轴 | 虚无感知者 | 意义建构者 | 活在当下派 |

---

## 数据库 Schema（SQLite）

```sql
test_sessions        -- 每次测试会话（session_id, started_at, is_complete）
question_answers     -- 每道题的具体回答（q_index, option, traits）
personality_results  -- 最终人格档案（meme_title, 7维度, energy_level...）
question_cache       -- 出过的题目缓存（避免重复，可扩展为预生成题库）
global_stats         -- 全局计数器（total_sessions, total_completions）
```

## 向量库（ChromaDB）

每次测试完成后，将以下内容向量化存入 ChromaDB：
- 所有回答文本 + 选择的人格 traits
- 人格称号 + 维度标签

支持：
- **相似人格检索**：找到与你最像的历史测试者（余弦相似度）
- **聚类分析**：数据面板展示人格类型分布

---

## 扩展方向

| 功能 | 实现思路 |
|------|----------|
| 人格雷达图 | `plotly` 绘制七维雷达图嵌入结果页 |
| 结果分享图 | `Pillow` 生成 1080×1080 分享卡片 |
| 题目预生成 | 定时任务预生成题库，减少出题延迟 |
| 用户系统 | 加入昵称/邮箱，持久化个人历史 |
| 多语言 | 繁中/英文版 prompt |
| embedding 升级 | 接入 `text-embedding-3-small` 替换默认模型 |

---

*由 DeepSeek API 驱动 · 数据存储于本地 SQLite + ChromaDB · 结果仅供娱乐*