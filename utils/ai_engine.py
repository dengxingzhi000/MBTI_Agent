"""
AI 引擎 + 三层缓存策略

调用链（每次 get_question）：
  ┌──────────────────────────────────────────────────┐
  │ 1. L1 命中？→ 从内存池取题，标记使用，异步预热   │
  │ 2. L1 未中  → 实时调 DeepSeek API               │
  │              → 写入 L1 内存池 + L2 SQLite        │
  │              → 异步预热触发（补充下一题）         │
  └──────────────────────────────────────────────────┘

预热时机（后台线程，不阻塞用户）：
  - 用户答完第 N 题 → 立即预生成第 N+1 题备用
  - 进程启动 → 若某 phase 池子不足 POOL_MIN_SIZE，批量补充
"""

import json
import os
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

from utils.db import (
    QuestionPool, persist_question, mark_question_used,
    _inc
)

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "xxx"),
    base_url="https://api.deepseek.com",
)
MODEL            = "deepseek-chat"
TOTAL_QUESTIONS  = 15

# 后台预热线程池（最多 2 个并发，不抢占主线程）
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="prefetch")

# ── 阶段配置 ───────────────────────────────────────────────────
PHASE_CONFIG = {
    0: {
        "name":   "热身阶段",
        "desc":   "互联网日常行为与习惯",
        "style":  "贴近生活，幽默，接地气，题目要像朋友聊天",
        "abstract_level": "低",
        "themes": ["刷手机习惯", "社交场合", "表情包使用", "评论区行为", "群聊风格",
                   "睡前仪式", "外卖点餐", "朋友圈行为", "打工人日常"],
    },
    1: {
        "name":   "觉醒阶段",
        "desc":   "价值观、处世态度与网络哲学",
        "style":  "开始带点哲理，但还是有梗，像知乎高赞回答一样",
        "abstract_level": "中",
        "themes": ["人生态度", "躺平or卷", "社交边界", "金钱观", "情绪处理",
                   "职场生存", "友情与孤独", "消费主义", "时间感知"],
    },
    2: {
        "name":   "飞升阶段",
        "desc":   "极度抽象的赛博存在主义与意识流",
        "style":  "完全抽象，意识流，存在主义，发疯文学，让人看了想emo又想笑",
        "abstract_level": "极高",
        "themes": ["虚无与意义", "身份认同", "赛博孤独", "混沌与秩序",
                   "时间的质感", "平行自我", "存在的重量", "数字灵魂"],
    },
}

# ── Prompts ─────────────────────────────────────────────────────
QUESTION_SYSTEM = """你是一个深度参与中国互联网文化的人格测试出题大师，同时精通存在主义哲学和网络亚文化。
你的题目融合以下元素（按需选用）：
【网络梗】打工人/社畜、i人e人、emo/发疯文学、废话文学、抽象话语、整活、草台班子、
         赛博、躺平/摆烂/卷王、清醒/不清醒、精神状态、宝子、嘴替、显眼包、发癫
【哲学流】虚无主义、存在先于本质、薛定谔的、平行宇宙、量子纠缠（玩梗用法）
【文化符号】二次元、00后、互联网原住民、电子榨菜、精神内耗

严格返回JSON，禁止任何额外文字：
{
  "question": "题目（可用emoji，20-50字，风格由阶段决定）",
  "theme": "主题标签（从给定主题中选一个）",
  "options": [
    {"id": "A", "text": "选项（15-35字）", "traits": ["维度标签1", "维度标签2"]},
    {"id": "B", "text": "选项（15-35字）", "traits": ["维度标签1"]},
    {"id": "C", "text": "选项（15-35字）", "traits": ["维度标签1", "维度标签2"]},
    {"id": "D", "text": "选项（15-35字）", "traits": ["维度标签1"]}
  ]
}

【七大测量维度标签】（每个选项选1-2个）：
E/I轴：社牛、社恐
抽象/具体轴：抽象派、实用派、形而上者、落地派
感性/理性轴：感性派、理智派、情绪动物、冷静分析师
躺/卷轴：躺平大师、卷王、摆烂艺术家、努力人、佛系
混沌/秩序轴：混沌中立、秩序卫士、随机应变者、规则制定者
网感轴：emo体质、快乐星球、哲学家、整活达人、清醒人、发疯预备役
存在轴：虚无感知者、意义建构者、活在当下派、未来主义者"""


RESULT_SYSTEM = """你是一个融合互联网梗文化与存在主义哲学的人格分析大师。
根据用户15道题的深度回答，生成专属人格档案。

人格称号规则：
- 必须原创，不能用"赛博哲学家""快乐摆烂王"等烂大街词汇
- 4-8字，押韵或有节奏感加分
- 可以是"XX的XX"结构，可以是造词，可以是四字梗

严格返回JSON，禁止任何额外文字：
{
  "meme_title": "专属人格称号（4-8字）",
  "meme_subtitle": "副标题（15-25字，像一句诗或话总结）",
  "description": "深度人格描述（200-250字，分3段：现象观察→深层逻辑→存在状态，第二人称）",
  "traits": ["标签1","标签2","标签3","标签4","标签5"],
  "famous_quote": "你最可能说出的话（25-45字，废话文学或哲学感悟）",
  "same_type_meme": "同类型互联网人格原型（详细描述）",
  "energy_level": 整数1-100,
  "chaos_index": 整数1-100,
  "internet_age": "互联网冲浪段位描述",
  "dimension_ei": "社牛 or 社恐 or 薛定谔社交人",
  "dimension_ap": "抽象派 or 实用派 or 量子叠加态",
  "dimension_sr": "感性派 or 理智派 or 情绪化理性人",
  "dimension_lc": "躺平 or 卷王 or 躺着卷",
  "life_philosophy": "你的人生哲学（30-50字）",
  "weak_point": "你的人格弱点（20-30字，要戳心）",
  "peak_state": "你精神状态最好的时刻（20-30字）"
}"""


# ══════════════════════════════════════════════════════════════
#  底层 API 调用
# ══════════════════════════════════════════════════════════════

def _call_deepseek(system: str, user: str, max_tokens: int = 900, temp: float = 0.92) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temp,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def _build_question_prompt(phase_idx: int, q_index: int,
                            history: list[dict], hint_theme: str = "") -> str:
    phase = PHASE_CONFIG[phase_idx]
    used_questions = [h["question"] for h in history]
    used_str = "\n".join(f"- {q}" for q in used_questions) if used_questions else "无"

    trait_portrait = Counter(
        t for h in history for t in h.get("answer_traits", [])
    )
    portrait_str = "、".join(
        f"{t}(×{c})" for t, c in trait_portrait.most_common(6)
    ) or "暂无"

    theme_hint = f"本题主题方向：{hint_theme}" if hint_theme else \
                 f"推荐主题方向（可选一个）：{'、'.join(phase['themes'])}"

    return f"""当前阶段：{phase['name']} —— {phase['desc']}
题目风格要求：{phase['style']}
抽象程度：{phase['abstract_level']}
{theme_hint}

这是第 {q_index + 1} 道题（共{TOTAL_QUESTIONS}题）。
用户已有画像特征：{portrait_str}
已出过的题目（严禁重复或高度相似）：
{used_str}

请生成一道全新的、符合当前阶段风格的题目。"""


# ══════════════════════════════════════════════════════════════
#  核心出题接口（带三层缓存）
# ══════════════════════════════════════════════════════════════

def get_question(pool: QuestionPool,
                 history: list[dict],
                 q_index: int) -> tuple[dict, bool]:
    """
    返回 (question_dict, from_cache: bool)
    from_cache=True  → L1 命中，无 API 调用
    from_cache=False → API 实时生成
    """
    phase_idx   = _phase_of(q_index)
    used_texts  = {h["question"] for h in history}

    # ── L1：内存池命中 ─────────────────────────────────────
    cached = pool.pop(phase_idx, used_texts)
    if cached:
        mark_question_used(cached["question"])
        _inc("cache_hits")
        logger.info(f"[Cache] L1 命中 Q{q_index+1} phase={phase_idx}")

        # 答完此题后，异步预热下一题
        _trigger_prefetch(pool, history + [{"question": cached["question"],
                                            "answer_traits": []}],
                          q_index + 1)
        return cached, True

    # ── L2/L3：API 实时生成 ────────────────────────────────
    logger.info(f"[Cache] 未命中，调用 API Q{q_index+1} phase={phase_idx}")
    _inc("api_calls")

    prompt = _build_question_prompt(phase_idx, q_index, history)
    q = _call_deepseek(QUESTION_SYSTEM, prompt, max_tokens=700)

    # 写入 L1 + L2
    pool.put(phase_idx, q)
    persist_question(phase_idx, q["question"], q["options"], q.get("theme", ""))

    # 异步预热：趁用户读题时，后台生成备用题
    _trigger_prefetch(pool, history, q_index + 1)

    return q, False


# ══════════════════════════════════════════════════════════════
#  后台预热（非阻塞）
# ══════════════════════════════════════════════════════════════

def _phase_of(q_index: int) -> int:
    if q_index < 5:  return 0
    if q_index < 10: return 1
    return 2


def _trigger_prefetch(pool: QuestionPool, history: list[dict], next_q_index: int):
    """
    提交后台预热任务（不等待结果）。
    条件：下一题还在测试范围内，且对应 phase 池子不足。
    """
    if next_q_index >= TOTAL_QUESTIONS:
        return
    phase_idx = _phase_of(next_q_index)
    if not pool.needs_refill(phase_idx):
        return

    # 快照 history（避免主线程修改影响子线程）
    history_snapshot = list(history)

    def _prefetch():
        try:
            logger.info(f"[Prefetch] 后台生成 phase={phase_idx} 第{next_q_index+1}题备用")
            prompt = _build_question_prompt(phase_idx, next_q_index, history_snapshot)
            q = _call_deepseek(QUESTION_SYSTEM, prompt, max_tokens=700)
            pool.put(phase_idx, q)
            persist_question(phase_idx, q["question"], q["options"], q.get("theme", ""))
            _inc("prefetch_count")
            logger.info(f"[Prefetch] 完成，phase={phase_idx} 池大小={pool.size(phase_idx)}")
        except Exception as e:
            logger.warning(f"[Prefetch] 失败：{e}")

    _executor.submit(_prefetch)


def warmup_pool(pool: QuestionPool, phase_idx: int, count: int = 3):
    """
    主动批量预热（进程启动时调用）。
    为指定 phase 生成 count 道题入池。
    """
    def _batch():
        generated = 0
        for _ in range(count):
            try:
                prompt = _build_question_prompt(phase_idx, phase_idx * 5, [])
                q = _call_deepseek(QUESTION_SYSTEM, prompt, max_tokens=700)
                is_new = persist_question(phase_idx, q["question"], q["options"], q.get("theme", ""))
                if is_new:
                    pool.put(phase_idx, q)
                    generated += 1
                    _inc("prefetch_count")
            except Exception as e:
                logger.warning(f"[Warmup] phase={phase_idx} 第{generated+1}条失败：{e}")
        logger.info(f"[Warmup] phase={phase_idx} 预热完成，新增 {generated} 道")

    _executor.submit(_batch)


# ══════════════════════════════════════════════════════════════
#  结果生成（不缓存，个性化强）
# ══════════════════════════════════════════════════════════════

def generate_result(history: list[dict]) -> dict:
    choice_summary = "\n".join(
        f"Q{i+1}[{h.get('phase','?')}]: {h['question']} → {h['answer_text']}"
        f" (traits: {', '.join(h.get('answer_traits',[]))})"
        for i, h in enumerate(history)
    )
    all_traits = [t for h in history for t in h.get("answer_traits", [])]
    top_traits = Counter(all_traits).most_common(8)
    trait_str  = "、".join(f"{t}(×{c})" for t, c in top_traits)

    user_prompt = f"""用户完成了全部{TOTAL_QUESTIONS}道题，以下是完整回答记录：

{choice_summary}

用户核心特质频次统计：{trait_str}

请综合分析，生成这位互联网人格的完整档案。
注意：题目跨越3个阶段（热身→觉醒→飞升），请结合三阶段表现给出立体分析。"""

    return _call_deepseek(RESULT_SYSTEM, user_prompt, max_tokens=1200, temp=0.88)
