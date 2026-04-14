"""
互联网梗人格测试 Agent
"""

import streamlit as st
import time

# ─── 页面配置（必须最先调用）─────────────────────────────────────
st.set_page_config(
    page_title="互联网人格测试",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

from utils.ai_engine import generate_question, generate_result, TOTAL_QUESTIONS
from utils.db import (
    init_sqlite, create_session, save_answer, save_result,
    get_recent_results, get_trait_distribution, get_stats,
    store_personality_vector, find_similar_personalities, get_cluster_stats,
)

# ─── 初始化数据库 ────────────────────────────────────────────────
init_sqlite()

# ─── 全局 CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── 字体 & 全局 ── */
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&family=Noto+Sans+SC:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans SC', sans-serif;
}

/* ── 隐藏 Streamlit 默认元素 ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 720px; }

/* ── 背景 ── */
.stApp { background: #0E0E16; }

/* ── 标题字体 ── */
.hero-title {
    font-family: 'ZCOOL XiaoWei', serif;
    font-size: 2.8rem;
    background: linear-gradient(135deg, #C084FC, #9B7FE8, #60A5FA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    line-height: 1.2;
    margin-bottom: 0.3rem;
}
.hero-sub {
    text-align: center;
    color: #8B8BA8;
    font-size: 0.95rem;
    margin-bottom: 2rem;
}

/* ── 标签胶囊 ── */
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 1rem 0 2rem; }
.tag-pill {
    padding: 4px 14px;
    border-radius: 999px;
    background: rgba(155,127,232,0.12);
    border: 1px solid rgba(155,127,232,0.3);
    color: #C084FC;
    font-size: 0.82rem;
}

/* ── 进度条容器 ── */
.progress-wrap {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 1.5rem;
}
.progress-track {
    flex: 1; height: 6px; background: rgba(255,255,255,0.08);
    border-radius: 999px; overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #9B7FE8, #C084FC);
    border-radius: 999px;
    transition: width 0.4s ease;
}
.progress-label { color: #8B8BA8; font-size: 0.82rem; white-space: nowrap; }

/* ── 题目区 ── */
.phase-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    margin-bottom: 1rem;
}
.phase-0 { background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.3); color: #60A5FA; }
.phase-1 { background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3); color: #FBBF24; }
.phase-2 { background: rgba(240,100,100,0.1); border: 1px solid rgba(240,100,100,0.3); color: #F06464; }

.question-box {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(155,127,232,0.2);
    border-radius: 16px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
    font-size: 1.1rem;
    line-height: 1.7;
    color: #E8E6F0;
}

/* ── 选项按钮覆盖 ── */
div[data-testid="stRadio"] > label {
    display: none;
}
div[data-testid="stRadio"] > div {
    display: flex; flex-direction: column; gap: 10px;
}
div[data-testid="stRadio"] > div > label {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    color: #E8E6F0 !important;
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
}
div[data-testid="stRadio"] > div > label:hover {
    border-color: rgba(155,127,232,0.5) !important;
    background: rgba(155,127,232,0.08) !important;
}

/* ── 结果卡片 ── */
.result-hero {
    background: linear-gradient(135deg, rgba(155,127,232,0.12), rgba(96,165,250,0.08));
    border: 1px solid rgba(155,127,232,0.25);
    border-radius: 20px;
    padding: 2rem;
    margin-bottom: 1.2rem;
    text-align: center;
}
.result-title {
    font-family: 'ZCOOL XiaoWei', serif;
    font-size: 2.4rem;
    background: linear-gradient(135deg, #C084FC, #9B7FE8, #60A5FA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
}
.result-sub { color: #A8A8C8; font-size: 0.95rem; margin-bottom: 1.2rem; }
.result-desc { color: #D0CEEA; font-size: 0.92rem; line-height: 1.85; text-align: left; }

.dim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 1rem 0; }
.dim-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px 14px;
}
.dim-label { font-size: 0.72rem; color: #6B6B88; margin-bottom: 4px; }
.dim-val { font-size: 0.92rem; color: #C084FC; font-weight: 500; }

.quote-box {
    background: rgba(155,127,232,0.06);
    border-left: 3px solid #9B7FE8;
    border-radius: 0 12px 12px 0;
    padding: 14px 16px;
    margin: 1rem 0;
    color: #C8C6E0;
    font-size: 0.92rem;
    font-style: italic;
    line-height: 1.7;
}

.metric-row { display: flex; gap: 12px; margin: 1rem 0; }
.metric-card {
    flex: 1;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
}
.metric-val { font-size: 1.6rem; font-weight: 500; color: #C084FC; }
.metric-lbl { font-size: 0.72rem; color: #6B6B88; margin-top: 4px; }

.traits-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin: 1rem 0; }
.trait-chip {
    padding: 5px 14px; border-radius: 999px;
    background: rgba(155,127,232,0.12);
    border: 1px solid rgba(155,127,232,0.3);
    color: #C084FC; font-size: 0.82rem;
}

.similar-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 8px;
    display: flex; justify-content: space-between; align-items: center;
}

.section-title {
    color: #8B8BA8; font-size: 0.78rem; letter-spacing: 0.1em;
    text-transform: uppercase; margin: 1.4rem 0 0.6rem;
}

/* ── 主按钮 ── */
div[data-testid="stButton"] > button {
    width: 100%;
    background: linear-gradient(135deg, #9B7FE8, #7C5FD4) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 1.5rem !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    transition: opacity 0.2s !important;
}
div[data-testid="stButton"] > button:hover { opacity: 0.88 !important; }

/* ── 侧边栏统计 ── */
.stat-item { display: flex; justify-content: space-between; padding: 8px 0;
             border-bottom: 1px solid rgba(255,255,255,0.06); color: #C8C6E0; font-size: 0.88rem; }
.stat-val { color: #C084FC; font-weight: 500; }

/* ── 加载动画 ── */
.loading-text {
    text-align: center; color: #8B8BA8; font-size: 0.9rem; padding: 1rem;
    animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:.5} 50%{opacity:1} }
</style>
""", unsafe_allow_html=True)


# ─── Session State 初始化 ────────────────────────────────────────
def init_state():
    defaults = {
        "phase": "welcome",      # welcome | testing | result | dashboard
        "session_id": None,
        "history": [],
        "current_q": None,
        "q_index": 0,
        "result": None,
        "selected_option": None,
        "loading": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─── 阶段辅助 ────────────────────────────────────────────────────
def get_phase_index(q_index: int) -> int:
    if q_index < 5: return 0
    if q_index < 10: return 1
    return 2

PHASE_NAMES = ["🌱 热身", "⚡ 觉醒", "🌀 飞升"]
PHASE_DESCS = ["互联网日常", "价值观与哲学", "赛博存在主义"]


# ════════════════════════════════════════════════════════════════
#  欢迎页
# ════════════════════════════════════════════════════════════════
def render_welcome():
    st.markdown('<div class="hero-title">你是哪种互联网人格？</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">基于中国互联网梗文化 · AI 实时生成 · 15 道渐进式灵魂拷问</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="tag-row">
      <span class="tag-pill">🌐 赛博玄学鉴定</span>
      <span class="tag-pill">😶‍🌫️ emo 体质检测</span>
      <span class="tag-pill">🛋️ 躺平指数评估</span>
      <span class="tag-pill">🎭 发疯预备役认证</span>
      <span class="tag-pill">🌀 存在主义测试</span>
      <span class="tag-pill">💬 废话文学鉴赏</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="question-box" style="font-size:0.92rem; color:#A8A8C8;">
    <strong style="color:#C084FC;">测试包含三个阶段 · 共 15 道题</strong><br><br>
    🌱 <strong style="color:#60A5FA;">热身阶段</strong>（1-5题）&nbsp;&nbsp;互联网日常行为，轻松上手<br>
    ⚡ <strong style="color:#FBBF24;">觉醒阶段</strong>（6-10题）&nbsp;价值观与处世哲学，开始发人深省<br>
    🌀 <strong style="color:#F06464;">飞升阶段</strong>（11-15题）极度抽象，赛博存在主义，慎入<br><br>
    <span style="color:#6B6B88; font-size:0.82rem;">AI 会根据你的回答动态调整后续题目 · 每次结果都不同</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 开始灵魂拷问", use_container_width=True):
            st.session_state.session_id = create_session()
            st.session_state.phase = "testing"
            st.session_state.history = []
            st.session_state.q_index = 0
            st.session_state.current_q = None
            st.rerun()

    # 全局统计简报
    stats = get_stats()
    if stats["total_completions"] > 0:
        st.markdown(f"""
        <div style="text-align:center; margin-top:1.5rem; color:#6B6B88; font-size:0.8rem;">
        已有 <span style="color:#C084FC;">{stats['total_completions']}</span> 位赛博人完成测试
        · 共 <span style="color:#C084FC;">{stats['total_sessions']}</span> 次灵魂拷问开启
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
#  测试页
# ════════════════════════════════════════════════════════════════
def render_testing():
    qi = st.session_state.q_index
    phase_idx = get_phase_index(qi)

    # 进度条
    pct = int((qi / TOTAL_QUESTIONS) * 100)
    phase_class = f"phase-{phase_idx}"
    st.markdown(f"""
    <div class="phase-badge {phase_class}">{PHASE_NAMES[phase_idx]} · {PHASE_DESCS[phase_idx]}</div>
    <div class="progress-wrap">
      <div class="progress-track">
        <div class="progress-fill" style="width:{pct}%"></div>
      </div>
      <span class="progress-label">{qi}/{TOTAL_QUESTIONS}</span>
    </div>
    """, unsafe_allow_html=True)

    # 如果还没题目，先生成
    if st.session_state.current_q is None:
        with st.spinner("🤖 AI 正在出题中…"):
            try:
                q = generate_question(st.session_state.history, qi)
                st.session_state.current_q = q
                st.session_state.selected_option = None
            except Exception as e:
                st.error(f"出题失败：{e}")
                if st.button("重试"):
                    st.rerun()
                return

    q = st.session_state.current_q
    if not q:
        return

    # 题目显示
    st.markdown(f'<div class="question-box">{q["question"]}</div>', unsafe_allow_html=True)

    # 选项
    options = [f'{opt["id"]}. {opt["text"]}' for opt in q["options"]]
    chosen = st.radio(
        "选择你的答案",
        options,
        index=None,
        key=f"radio_{qi}",
    )

    # 确认按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_label = "✅ 确认" if qi < TOTAL_QUESTIONS - 1 else "🎯 提交答卷"
        if st.button(btn_label, disabled=(chosen is None), use_container_width=True):
            # 解析选择
            chosen_id = chosen[0]
            selected_opt = next(o for o in q["options"] if o["id"] == chosen_id)

            # 记录 history
            phase_name = PHASE_NAMES[phase_idx]
            st.session_state.history.append({
                "question": q["question"],
                "answer_id": chosen_id,
                "answer_text": selected_opt["text"],
                "answer_traits": selected_opt.get("traits", []),
                "phase": phase_name,
            })

            # 存 SQLite
            save_answer(
                st.session_state.session_id, qi,
                q["question"], chosen_id,
                selected_opt["text"],
                selected_opt.get("traits", []),
            )

            st.session_state.q_index += 1
            st.session_state.current_q = None

            if st.session_state.q_index >= TOTAL_QUESTIONS:
                st.session_state.phase = "generating"
            st.rerun()


# ════════════════════════════════════════════════════════════════
#  生成结果页（过渡）
# ════════════════════════════════════════════════════════════════
def render_generating():
    st.markdown('<div class="hero-title" style="font-size:2rem;">🌀 正在分析你的精神状态</div>', unsafe_allow_html=True)

    messages = [
        "正在解析你的赛博DNA…",
        "量子纠缠你的回答中…",
        "向薛定谔请教人格边界…",
        "草台班子AI紧急会议中…",
        "正在为你的emo体质建档…",
        "分析你的躺平指数…",
        "解构你的存在主义倾向…",
    ]

    placeholder = st.empty()
    for i, msg in enumerate(messages[:4]):
        icon = '🔄' if i % 2 == 0 else '⚙️'
        placeholder.markdown(f'<div class="loading-text">{icon} {msg}</div>', unsafe_allow_html=True)
        time.sleep(0.6)

    try:
        result = generate_result(st.session_state.history)
        st.session_state.result = result

        # 存 SQLite
        save_result(st.session_state.session_id, result)

        # 存 ChromaDB 向量
        try:
            store_personality_vector(
                st.session_state.session_id,
                result,
                st.session_state.history,
            )
        except Exception:
            pass  # 向量存储失败不影响主流程

        st.session_state.phase = "result"
        st.rerun()

    except Exception as e:
        st.error(f"分析失败：{e}")
        if st.button("重试"):
            st.session_state.phase = "generating"
            st.rerun()


# ════════════════════════════════════════════════════════════════
#  结果页
# ════════════════════════════════════════════════════════════════
def render_result():
    r = st.session_state.result
    if not r:
        st.session_state.phase = "welcome"
        st.rerun()

    # ── 人格主卡 ──────────────────────────────────────────────
    st.markdown(f"""
    <div class="result-hero">
      <div class="result-title">{r.get('meme_title','???')}</div>
      <div class="result-sub">{r.get('meme_subtitle','')}</div>
      <div class="result-desc">{r.get('description','').replace(chr(10),'<br>')}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── 四维雷达（文字版）───────────────────────────────────────
    st.markdown('<div class="section-title">人格维度</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="dim-grid">
      <div class="dim-card"><div class="dim-label">社交能量 E/I</div><div class="dim-val">{r.get('dimension_ei','—')}</div></div>
      <div class="dim-card"><div class="dim-label">思维模式 抽象/具体</div><div class="dim-val">{r.get('dimension_ap','—')}</div></div>
      <div class="dim-card"><div class="dim-label">决策风格 感性/理性</div><div class="dim-val">{r.get('dimension_sr','—')}</div></div>
      <div class="dim-card"><div class="dim-label">能量状态 躺/卷</div><div class="dim-val">{r.get('dimension_lc','—')}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── 数值指标 ─────────────────────────────────────────────
    energy = r.get('energy_level', 50)
    chaos = r.get('chaos_index', 50)
    energy_bar = "🔥" * (energy // 25) + "💤" * (4 - energy // 25)
    chaos_bar = "🌀" * (chaos // 25) + "😴" * (4 - chaos // 25)

    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-card">
        <div class="metric-val">{energy}</div>
        <div style="font-size:1rem;margin:2px 0;">{energy_bar}</div>
        <div class="metric-lbl">精神能量值</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{chaos}</div>
        <div style="font-size:1rem;margin:2px 0;">{chaos_bar}</div>
        <div class="metric-lbl">混沌指数</div>
      </div>
      <div class="metric-card">
        <div class="metric-val" style="font-size:0.85rem;padding-top:4px;">{r.get('internet_age','—')}</div>
        <div class="metric-lbl" style="margin-top:8px;">冲浪段位</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 人格标签 ─────────────────────────────────────────────
    st.markdown('<div class="section-title">你的人格标签</div>', unsafe_allow_html=True)
    chips = "".join(f'<span class="trait-chip">{t}</span>' for t in r.get("traits", []))
    st.markdown(f'<div class="traits-wrap">{chips}</div>', unsafe_allow_html=True)

    # ── 你最可能说的话 ───────────────────────────────────────
    st.markdown('<div class="section-title">你最可能说出的话</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="quote-box">"{r.get("famous_quote","")}"</div>', unsafe_allow_html=True)

    # ── 深度解读 ─────────────────────────────────────────────
    with st.expander("📖 深度解读（点击展开）"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**🧬 人生哲学**")
            st.markdown(f"> {r.get('life_philosophy','—')}")
            st.markdown("**🎯 同类型人格原型**")
            st.markdown(r.get('same_type_meme', '—'))
        with col_b:
            st.markdown("**⚠️ 人格弱点**")
            st.markdown(f"> {r.get('weak_point','—')}")
            st.markdown("**✨ 你的高光时刻**")
            st.markdown(f"> {r.get('peak_state','—')}")

    # ── 相似人格检索（ChromaDB）─────────────────────────────
    st.markdown('<div class="section-title">🔍 与你相似的灵魂</div>', unsafe_allow_html=True)
    try:
        similar = find_similar_personalities(st.session_state.session_id, top_k=3)
        if similar:
            for s in similar:
                trait_str = "  ".join(f"`{t}`" for t in s["traits"][:3] if t)
                st.markdown(f"""
                <div class="similar-card">
                  <div>
                    <span style="color:#C084FC;font-weight:500;">{s['meme_title']}</span>
                    <span style="color:#6B6B88;font-size:0.78rem;margin-left:8px;">{trait_str}</span>
                  </div>
                  <span style="color:#9B7FE8;font-size:0.85rem;">相似度 {s['similarity']}%</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6B6B88;font-size:0.85rem;">暂无足够数据，你是第一批赛博探索者 👾</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div style="color:#6B6B88;font-size:0.85rem;">向量检索暂不可用</div>', unsafe_allow_html=True)

    # ── 操作按钮 ─────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 再测一次", use_container_width=True):
            for k in ["history", "current_q", "q_index", "result", "session_id", "selected_option"]:
                st.session_state[k] = [] if k == "history" else None if k != "q_index" else 0
            st.session_state.phase = "welcome"
            st.rerun()
    with col2:
        if st.button("📊 查看数据面板", use_container_width=True):
            st.session_state.phase = "dashboard"
            st.rerun()


# ════════════════════════════════════════════════════════════════
#  数据面板
# ════════════════════════════════════════════════════════════════
def render_dashboard():
    st.markdown('<div class="hero-title" style="font-size:1.8rem;">📊 赛博人格数据面板</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">所有测试数据的聚合分析</div>', unsafe_allow_html=True)

    # ── 全局统计 ─────────────────────────────────────────────
    stats = get_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("总测试次数", stats["total_sessions"])
    with col2:
        st.metric("完成测试", stats["total_completions"])

    # ── 最近结果 ─────────────────────────────────────────────
    st.markdown('<div class="section-title">最近完成的测试</div>', unsafe_allow_html=True)
    recent = get_recent_results(8)
    if recent:
        for row in recent:
            st.markdown(f"""
            <div class="similar-card">
              <div>
                <span style="color:#C084FC;font-weight:500;">{row['meme_title']}</span>
                <span style="color:#8B8BA8;font-size:0.8rem;margin-left:8px;">{row.get('meme_subtitle','')[:20]}…</span>
              </div>
              <span style="color:#6B6B88;font-size:0.78rem;">{row['created_at'][:10]}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("暂无完成记录")

    # ── 人格标签分布 ─────────────────────────────────────────
    st.markdown('<div class="section-title">人格标签分布</div>', unsafe_allow_html=True)
    dist = get_trait_distribution()
    if dist:
        import streamlit as st2
        items = sorted(dist.items(), key=lambda x: -x[1])
        total = sum(dist.values())
        for tag, count in items[:10]:
            pct = count / total
            st.markdown(f"""
            <div style="margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                <span style="color:#C8C6E0;font-size:0.85rem;">{tag}</span>
                <span style="color:#9B7FE8;font-size:0.82rem;">{count}</span>
              </div>
              <div style="height:4px;background:rgba(255,255,255,0.06);border-radius:999px;">
                <div style="height:100%;width:{pct*100:.0f}%;background:linear-gradient(90deg,#9B7FE8,#C084FC);border-radius:999px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("暂无标签数据")

    # ── ChromaDB 向量库统计 ──────────────────────────────────
    st.markdown('<div class="section-title">🧠 向量库人格聚类</div>', unsafe_allow_html=True)
    try:
        cluster = get_cluster_stats()
        st.markdown(f'<div style="color:#8B8BA8;font-size:0.85rem;margin-bottom:8px;">向量库共 {cluster["total"]} 条人格向量</div>', unsafe_allow_html=True)
        for title, count in cluster.get("titles", {}).items():
            st.markdown(f"""
            <div class="similar-card" style="padding:8px 14px;">
              <span style="color:#C8C6E0;font-size:0.88rem;">{title}</span>
              <span style="color:#9B7FE8;font-size:0.82rem;">×{count}</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"向量库读取失败：{e}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← 返回首页", use_container_width=True):
        st.session_state.phase = "welcome"
        st.rerun()


# ════════════════════════════════════════════════════════════════
#  路由
# ════════════════════════════════════════════════════════════════
phase = st.session_state.phase

if phase == "welcome":
    render_welcome()
elif phase == "testing":
    render_testing()
elif phase == "generating":
    render_generating()
elif phase == "result":
    render_result()
elif phase == "dashboard":
    render_dashboard()
else:
    st.session_state.phase = "welcome"
    st.rerun()