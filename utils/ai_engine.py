"""
AI 引擎：DeepSeek 出题 + 人格分析
- 15 道题，按阶段递进，越来越抽象
- 支持 7 大维度测量
"""

import json
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-6236dc74154f4d029f027f004c42ac3d"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-chat"
TOTAL_QUESTIONS = 15

# ─── 题目阶段划分 ────────────────────────────────────────────────
# 前5题：热身，接地气的互联网日常
# 中5题：价值观与处世哲学，开始抽象
# 后5题：极度抽象，赛博哲学，意识流，存在主义
PHASE_CONFIG = {
    0: {
        "name": "热身阶段",
        "desc": "互联网日常行为与习惯",
        "style": "贴近生活，幽默，接地气，题目要像朋友聊天",
        "abstract_level": "低",
        "themes": ["刷手机习惯", "社交场合", "表情包使用", "评论区行为", "群聊风格"],
    },
    1: {
        "name": "觉醒阶段",
        "desc": "价值观、处世态度与网络哲学",
        "style": "开始带点哲理，但还是有梗，像知乎问题一样",
        "abstract_level": "中",
        "themes": ["人生态度", "躺平or卷", "社交边界", "金钱观", "情绪处理"],
    },
    2: {
        "name": "飞升阶段",
        "desc": "极度抽象的赛博存在主义与意识流",
        "style": "完全抽象，意识流，存在主义，发疯文学，哲学，让人看了想emo又想笑",
        "abstract_level": "极高",
        "themes": ["时间感知", "虚无与意义", "身份认同", "赛博孤独", "混沌与秩序"],
    },
}

# ─── Prompt 模板 ─────────────────────────────────────────────────

QUESTION_SYSTEM = """你是一个深度参与中国互联网文化的人格测试出题大师，同时精通存在主义哲学和网络亚文化。
你的题目融合以下元素（按需选用）：
【网络梗】打工人/社畜、i人e人、emo/发疯文学、废话文学、抽象话语、整活、草台班子、小丑竟是我自己、
         赛博、躺平/摆烂/卷王、清醒/不清醒、精神状态、宝子、嘴替、显眼包、发癫
【哲学流】虚无主义、存在先于本质、薛定谔的、平行宇宙、量子纠缠（玩梗用法）
【文化符号】二次元、00后、互联网原住民、电子榨菜、精神内耗

严格返回JSON，禁止任何额外文字：
{
  "question": "题目（可用emoji，20-50字，风格由阶段决定）",
  "theme": "主题标签",
  "options": [
    {"id": "A", "text": "选项（15-35字）", "traits": ["维度标签"]},
    {"id": "B", "text": "选项（15-35字）", "traits": ["维度标签"]},
    {"id": "C", "text": "选项（15-35字）", "traits": ["维度标签"]},
    {"id": "D", "text": "选项（15-35字）", "traits": ["维度标签"]}
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
- 可以是"XX的XX"结构，可以是四字成语梗，可以是造词

严格返回JSON，禁止任何额外文字：
{
  "meme_title": "专属人格称号（4-8字）",
  "meme_subtitle": "副标题（15-25字，像一句诗或一句话总结）",
  "description": "深度人格描述（200-250字，分3段：现象观察→深层逻辑→存在状态，第二人称，有梗有共鸣）",
  "traits": ["标签1","标签2","标签3","标签4","标签5"],
  "famous_quote": "你最可能说出的话（25-45字，可以是废话文学或哲学感悟）",
  "same_type_meme": "同类型互联网人格原型（详细描述，不只是名字）",
  "energy_level": 整数1-100,
  "chaos_index": 整数1-100,
  "internet_age": "互联网冲浪段位描述",
  "dimension_ei": "社牛 or 社恐 or 薛定谔社交人",
  "dimension_ap": "抽象派 or 实用派 or 量子叠加态",
  "dimension_sr": "感性派 or 理智派 or 情绪化理性人",
  "dimension_lc": "躺平 or 卷王 or 躺着卷",
  "life_philosophy": "你的人生哲学（30-50字，可以很抽象）",
  "weak_point": "你的人格弱点（20-30字，要戳心）",
  "peak_state": "你精神状态最好的时刻（20-30字）"
}"""


# ─── 核心调用 ────────────────────────────────────────────────────

def _call_deepseek(system: str, user: str, max_tokens: int = 900, temp: float = 0.92) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temp,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def generate_question(history: list[dict], q_index: int) -> dict:
    """生成第 q_index 道题（0-based）"""
    # 确定阶段
    if q_index < 5:
        phase = PHASE_CONFIG[0]
    elif q_index < 10:
        phase = PHASE_CONFIG[1]
    else:
        phase = PHASE_CONFIG[2]

    # 已用过的题目（避免重复）
    used_questions = [h["question"] for h in history]
    used_str = "\n".join(f"- {q}" for q in used_questions) if used_questions else "无"

    # 已展现的 traits 画像
    trait_portrait = {}
    for h in history:
        for t in h.get("answer_traits", []):
            trait_portrait[t] = trait_portrait.get(t, 0) + 1
    portrait_str = "、".join(
        f"{t}(×{c})" for t, c in sorted(trait_portrait.items(), key=lambda x: -x[1])
    ) or "暂无"

    user_prompt = f"""当前阶段：{phase['name']} —— {phase['desc']}
题目风格要求：{phase['style']}
抽象程度：{phase['abstract_level']}
推荐主题方向（可选一个）：{'、'.join(phase['themes'])}

这是第 {q_index + 1} 道题（共15题）。
已展现的用户画像特征：{portrait_str}
已出过的题目（严禁重复或相似）：
{used_str}

请生成一道符合当前阶段风格的新题目，要针对用户已有画像做更深度的探测。"""

    return _call_deepseek(QUESTION_SYSTEM, user_prompt, max_tokens=700)


def generate_result(history: list[dict]) -> dict:
    """根据15道题的完整回答生成人格结果"""
    choice_summary = "\n".join(
        f"Q{i+1}[{h.get('phase','?')}]: {h['question']} → {h['answer_text']} (traits: {', '.join(h.get('answer_traits',[]))})"
        for i, h in enumerate(history)
    )
    all_traits = [t for h in history for t in h.get("answer_traits", [])]
    from collections import Counter
    top_traits = Counter(all_traits).most_common(8)
    trait_str = "、".join(f"{t}(×{c})" for t, c in top_traits)

    user_prompt = f"""用户完成了全部15道题，以下是完整回答记录：

{choice_summary}

用户核心特质频次统计：{trait_str}

请综合分析，生成这位互联网人格的完整档案。
注意：15道题跨越3个阶段（热身→觉醒→飞升），请结合三个阶段的表现给出立体分析。"""

    return _call_deepseek(RESULT_SYSTEM, user_prompt, max_tokens=1200, temp=0.88)