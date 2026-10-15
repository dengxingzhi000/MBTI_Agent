<div align="center">

# 🎭 互联网梗人格测试 Agent

### 15 道渐进式灵魂拷问，测出你的互联网人格画像。

**Streamlit + DeepSeek API + SQLite + ChromaDB。**
数据双库持久化，向量检索找出和你最像的历史测试者。

[![Python](https://img.shields.io/badge/python-3.8%2B-blue?labelColor=black&style=flat-square&logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white&style=flat-square)](https://streamlit.io/)

[快速开始](#快速开始) · [三种模式](#三种模式) · [人格维度](#七大人格维度) · [数据层](#数据层) · [FAQ](#faq)

<code>streamlit run App.py</code>

</div>

> [!WARNING]
> **仓库里的两个文件名有拼写问题，照 README 抄命令会直接失败。**
>
> - 依赖清单叫 **`Requirememts`**（少一个 `s`），不是 `requirements.txt`，
>   所以 `pip install -r requirements.txt` 会报文件不存在。
> - 主程序叫 **`App.py`**（大写 A），不是 `app.py`。Windows 上大小写不敏感可以
>   蒙混过关，**Linux / macOS 上 `streamlit run app.py` 会直接失败**。
>
> 另外 README 旧版提到的 `.streamlit/config.toml`（深色紫调主题）并不在仓库里。

---

正经的 MBTI 测试要答 90 道题、做完四组字母轴，出来一个缩写。这个项目换了个思路：
用 15 道越问越抽象的互联网梗题，测出的不是 E/I 而是「社牛还是薛定谔社交人」。

题目分三个阶段渐进：热身阶段接地气，觉醒阶段开始有哲理，飞升阶段直接上存在主义。
AI 会读取你前几题的回答画像，**动态调整**后续出题方向。最后把你的人格向量写入
ChromaDB，用余弦相似度找出历史上最像你的测试者。

结果仅供娱乐。

## 快速开始

### 前置依赖

- **Python 3.8+**
- **DeepSeek API Key** —— 必填

### 安装与运行

```bash
# 1. 安装依赖（注意文件名拼写）
pip install -r Requirememts

# 2. 配置 DeepSeek API Key
export DEEPSEEK_API_KEY="sk-xxxxxxxx"

# 3. 启动（注意是大写的 App.py）
streamlit run App.py
# → http://localhost:7860
```

> [!NOTE]
> 依赖只有三个：`streamlit>=1.35.0`、`openai>=1.0.0`、`chromadb>=0.5.0`。
> SQLite 走 Python 标准库，embedding 用 ChromaDB 的默认实现。

## 三种模式

| 阶段    | 题目  | 风格             | 主题                         |
| ------- | ----- | ---------------- | ---------------------------- |
| 🌱 热身 | 1-5   | 接地气，日常化   | 刷手机习惯、社交行为、表情包 |
| ⚡ 觉醒 | 6-10  | 开始哲理，有梗   | 人生态度、躺平/卷、金钱观    |
| 🌀 飞升 | 11-15 | 极度抽象，意识流 | 存在主义、赛博孤独、虚无感   |

会话状态机按 `welcome → testing → generating → result → dashboard` 推进，
状态存放在 Streamlit Session State 中。

## 七大人格维度

| 维度        | 极值 A     | 极值 B     | 中间态       |
| ----------- | ---------- | ---------- | ------------ |
| E/I 社交轴  | 社牛       | 社恐       | 薛定谔社交人 |
| 抽象/具体轴 | 抽象派     | 实用派     | 量子叠加态   |
| 感性/理性轴 | 感性派     | 理智派     | 情绪化理性人 |
| 躺/卷轴     | 躺平大师   | 卷王       | 躺着卷       |
| 混沌/秩序轴 | 混沌中立   | 秩序卫士   | 随机应变者   |
| 网感轴      | emo 体质   | 快乐星球   | —            |
| 存在轴      | 虚无感知者 | 意义建构者 | 活在当下派   |

## 数据层

```text
mbti_streamlit/
├── App.py                   # Streamlit 主程序（UI + 路由 + 状态机）
├── Requirememts             # 依赖清单（文件名拼写有误，见上方警告）
├── utils/
│   ├── ai_engine.py         # DeepSeek 调用 + Prompt 工程
│   │     ├── generate_question()   按阶段出题，携带历史 context
│   │     └── generate_result()     15 题综合分析，返回结构化 JSON
│   └── db.py                # SQLite + ChromaDB 数据层
└── data/                    # 已随仓库提交，含预置数据
    ├── mbti_meme.db         # SQLite 数据库
    └── chroma_store/        # ChromaDB 向量持久化目录
```

### SQLite Schema

```sql
test_sessions        -- 每次测试会话（session_id, started_at, is_complete）
question_answers     -- 每道题的具体回答（q_index, option, traits）
personality_results  -- 最终人格档案（meme_title, 7 维度, energy_level...）
question_cache       -- 出过的题目缓存（避免重复，可扩展为预生成题库）
global_stats         -- 全局计数器（total_sessions, total_completions）
```

### ChromaDB 向量库

每次测试完成后存入以下内容：

- 所有回答文本 + 选择的人格 traits
- 人格称号 + 维度标签

由此支持**相似人格检索**（余弦相似度找出最像的历史测试者）与
**聚类分析**（数据面板展示人格类型分布）。

> [!NOTE]
> `data/` 目录**已随仓库提交**，包含一个预置的 `mbti_meme.db` 和一个
> ChromaDB 向量库。如果你想要干净的起始状态，删除 `data/` 后重启即可重建。

## 扩展方向

| 功能           | 实现思路                                   |
| -------------- | ------------------------------------------ |
| 人格雷达图     | `plotly` 绘制七维雷达图嵌入结果页          |
| 结果分享图     | `Pillow` 生成 1080×1080 分享卡片           |
| 题目预生成     | 定时任务预生成题库，减少出题延迟           |
| 用户系统       | 加入昵称/邮箱，持久化个人历史              |
| 多语言         | 繁中/英文版 prompt                         |
| embedding 升级 | 接入 `text-embedding-3-small` 替换默认模型 |

## FAQ

<details>
<summary><strong>为什么 <code>pip install -r requirements.txt</code> 会失败？</strong></summary>

因为仓库里的依赖清单文件名是 `Requirememts`，不是 `requirements.txt`。
这是仓库根目录的一个拼写错误。用 `pip install -r Requirememts` 即可，
或者把文件重命名为 `requirements.txt` 并一并修正本文档。

</details>

<details>
<summary><strong><code>streamlit run app.py</code> 在 Linux 上报错？</strong></summary>

主程序文件名是 `App.py`（大写 A）。Windows 文件系统大小写不敏感所以本地能跑，
Linux 和 macOS 上必须严格写成 `streamlit run App.py`。

</details>

<details>
<summary><strong>仓库里怎么已经有数据了？</strong></summary>

`data/mbti_meme.db` 和 `data/chroma_store/` 是随仓库一起提交的预置数据，
克隆下来就有现成的人格记录和向量索引。想从零开始的话，删掉 `data/` 目录后
重新运行即可。

</details>

---

_由 DeepSeek API 驱动 · 数据存储于本地 SQLite + ChromaDB · 结果仅供娱乐_
