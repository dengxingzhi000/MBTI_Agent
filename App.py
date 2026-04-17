"""
互联网梗人格测试 Agent
Streamlit + DeepSeek + SQLite + ChromaDB + 三层题目缓存
"""

import streamlit as st
import time
from utils.db import (
    POOL_MIN_SIZE
)

st.set_page_config(
    page_title="互联网人格测试",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 数据层 & AI 引擎 ─────────────────────────────────────────────
from utils.db import (
    QuestionPool, init_sqlite,
    create_session, save_answer, save_result,
    get_recent_results, get_trait_distribution, get_stats,
    get_cache_pool_status, get_cache_api_stats,
    store_personality_vector, find_similar_personalities, get_cluster_stats,
)
from utils.ai_engine import (
    get_question, generate_result, warmup_pool,
    TOTAL_QUESTIONS, PHASE_CONFIG,
)

# ══════════════════════════════════════════════════════════════
#  L1 内存池：全进程单例（st.cache_resource）
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_pool() -> QuestionPool:
    """
    进程启动时执行一次：
    1. 从 SQLite 加载已有题目到内存
    2. 若各 phase 不足 POOL_MIN_SIZE，异步预热补充
    """
    pool = QuestionPool()
    pool.load_from_db()

    from utils.db import POOL_MIN_SIZE
    for phase_idx in range(3):
        deficit = POOL_MIN_SIZE - pool.size(phase_idx)
        if deficit > 0:
            warmup_pool(pool, phase_idx, count=min(deficit, 4))

    return pool


# ══════════════════════════════════════════════════════════════
#  初始化
# ══════════════════════════════════════════════════════════════
init_sqlite()
pool = get_pool()


# ── 全局 CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&family=Noto+Sans+SC:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans SC', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 720px; }
.stApp { background: #0E0E16; }

.hero-title {
    font-family: 'ZCOOL XiaoWei', serif;
    font-size: 2.8rem;
    background: linear-gradient(135deg, #C084FC, #9B7FE8, #60A5FA);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-align: center; line-height: 1.2; margin-bottom: 0.3rem;
}
.hero-sub { text-align: center; color: #8B8BA8; font-size: 0.95rem; margin-bottom: 2rem; }

.tag-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 1rem 0 2rem; }
.tag-pill {
    padding: 4px 14px; border-radius: 999px;
    background: rgba(155,127,232,0.12); border: 1px solid rgba(155,127,232,0.3);
    color: #C084FC; font-size: 0.82rem;
}

.progress-wrap { display: flex; align-items: center; gap: 12px; margin-bottom: 1.5rem; }
.progress-track { flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 999px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #9B7FE8, #C084FC); border-radius: 999px; transition: width 0.4s ease; }
.progress-label { color: #8B8BA8; font-size: 0.82rem; white-space: nowrap; }

.phase-badge { display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; margin-bottom: 1rem; }
.phase-0 { background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.3); color: #60A5FA; }
.phase-1 { background: rgba(251,191,36,0.1);  border: 1px solid rgba(251,191,36,0.3);  color: #FBBF24; }
.phase-2 { background: rgba(240,100,100,0.1); border: 1px solid rgba(240,100,100,0.3); color: #F06464; }

/* 缓存标记 */
.cache-badge {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 0.7rem; margin-left: 8px; vertical-align: middle;
    background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3); color: #4ADE80;
}
.api-badge {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 0.7rem; margin-left: 8px; vertical-align: middle;
    background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3); color: #FBBF24;
}

.question-box {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(155,127,232,0.2);
    border-radius: 16px; padding: 1.5rem 1.8rem; margin-bottom: 1.5rem;
    font-size: 1.1rem; line-height: 1.7; color: #E8E6F0;
}

div[data-testid="stRadio"] > label { display: none; }
div[data-testid="stRadio"] > div { display: flex; flex-direction: column; gap: 10px; }
div[data-testid="stRadio"] > div > label {
    background: rgba(255,255,255,0.03) !important; border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important; padding: 14px 18px !important; cursor: pointer !important;
    transition: all 0.2s !important; color: #E8E6F0 !important; font-size: 0.95rem !important; line-height: 1.5 !important;
}
div[data-testid="stRadio"] > div > label:hover {
    border-color: rgba(155,127,232,0.5) !important; background: rgba(155,127,232,0.08) !important;
}

.result-hero {
    background: linear-gradient(135deg, rgba(155,127,232,0.12), rgba(96,165,250,0.08));
    border: 1px solid rgba(155,127,232,0.25); border-radius: 20px;
    padding: 2rem; margin-bottom: 1.2rem; text-align: center;
}
.result-title {
    font-family: 'ZCOOL XiaoWei', serif; font-size: 2.4rem;
    background: linear-gradient(135deg, #C084FC, #9B7FE8, #60A5FA);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
}
.result-sub { color: #A8A8C8; font-size: 0.95rem; margin-bottom: 1.2rem; }
.result-desc { color: #D0CEEA; font-size: 0.92rem; line-height: 1.85; text-align: left; }

.dim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 1rem 0; }
.dim-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px; }
.dim-label { font-size: 0.72rem; color: #6B6B88; margin-bottom: 4px; }
.dim-val { font-size: 0.92rem; color: #C084FC; font-weight: 500; }

.quote-box {
    background: rgba(155,127,232,0.06); border-left: 3px solid #9B7FE8;
    border-radius: 0 12px 12px 0; padding: 14px 16px; margin: 1rem 0;
    color: #C8C6E0; font-size: 0.92rem; font-style: italic; line-height: 1.7;
}

.metric-row { display: flex; gap: 12px; margin: 1rem 0; }
.metric-card { flex: 1; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px; text-align: center; }
.metric-val { font-size: 1.6rem; font-weight: 500; color: #C084FC; }
.metric-lbl { font-size: 0.72rem; color: #6B6B88; margin-top: 4px; }

.traits-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin: 1rem 0; }
.trait-chip { padding: 5px 14px; border-radius: 999px; background: rgba(155,127,232,0.12); border: 1px solid rgba(155,127,232,0.3); color: #C084FC; font-size: 0.82rem; }

.similar-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
.section-title { color: #8B8BA8; font-size: 0.78rem; letter-spacing: 0.1em; text-transform: uppercase; margin: 1.4rem 0 0.6rem; }

/* 缓存面板 */
.cache-stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
.cache-stat-label { color: #A8A8C8; font-size: 0.88rem; }
.cache-stat-val { color: #4ADE80; font-size: 0.88rem; font-weight: 500; }
.cache-stat-val.warn { color: #FBBF24; }

.hit-rate-bar { height: 8px; background: rgba(255,255,255,0.06); border-radius: 999px; overflow: hidden; margin-top: 4px; }
.hit-rate-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #4ADE80, #22D3EE); }

div[data-testid="stButton"] > button {
    width: 100%; background: linear-gradient(135deg, #9B7FE8, #7C5FD4) !important;
    color: white !important; border: none !important; border-radius: 12px !important;
    padding: 0.75rem 1.5rem !important; font-size: 1rem !important;
    font-weight: 500 !important; transition: opacity 0.2s !important;
}
div[data-testid="stButton"] > button:hover { opacity: 0.88 !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  Session State 初始化
# ══════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "phase": "welcome",
        "session_id": None,
        "history": [],
        "current_q": None,
        "current_q_from_cache": False,
        "q_index": 0,
        "result": None,
        "cache_log": [],   # [(q_index, from_cache), ...]
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

PHASE_NAMES = ["🌱 热身", "⚡ 觉醒", "🌀 飞升"]
PHASE_DESCS = ["互联网日常", "价值观与哲学", "赛博存在主义"]


def _phase_idx(q_index: int) -> int:
    return 0 if q_index < 5 else (1 if q_index < 10 else 2)


# ══════════════════════════════════════════════════════════════
#  欢迎页
# ══════════════════════════════════════════════════════════════
def render_welcome():
    st.markdown('<div class="hero-title">你是哪种互联网人格？</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">基于中国互联网梗文化 · 15 道渐进式灵魂拷问</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="tag-row">
      <span class="tag-pill">🌐 赛博玄学鉴定</span>
      <span class="tag-pill">😶‍🌫️ emo 体质检测</span>
      <span class="tag-pill">🛋️ 躺平指数评估</span>
      <span class="tag-pill">🎭 发疯预备役认证</span>
      <span class="tag-pill">🌀 存在主义测试</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="question-box" style="font-size:0.92rem; color:#A8A8C8;">
    <strong style="color:#C084FC;">三阶段 · 共 15 道题</strong><br><br>
    🌱 <strong style="color:#60A5FA;">热身</strong>（1-5题）&nbsp;&nbsp;互联网日常，轻松上手<br>
    ⚡ <strong style="color:#FBBF24;">觉醒</strong>（6-10题）&nbsp;价值观哲学，开始发人深省<br>
    🌀 <strong style="color:#F06464;">飞升</strong>（11-15题）极度抽象，赛博存在主义，慎入
    </div>
    """, unsafe_allow_html=True)

    # 池子状态简报
    pool_stats = pool.stats()
    total_cached = sum(pool_stats.values())
    status_color = "#4ADE80" if total_cached >= 6 else "#FBBF24"
    st.markdown(f"""
    <div style="text-align:center; color:#6B6B88; font-size:0.78rem; margin-bottom:1rem;">
    题目缓存池 &nbsp;
    <span style="color:{status_color};">phase0: {pool_stats.get('phase_0',0)} · phase1: {pool_stats.get('phase_1',0)} · phase2: {pool_stats.get('phase_2',0)}</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 开始灵魂拷问", use_container_width=True):
            st.session_state.session_id  = create_session()
            st.session_state.phase       = "testing"
            st.session_state.history     = []
            st.session_state.q_index     = 0
            st.session_state.current_q   = None
            st.session_state.cache_log   = []
            st.rerun()

    stats = get_stats()
    if stats["total_completions"] > 0:
        st.markdown(f"""
        <div style="text-align:center; margin-top:1rem; color:#6B6B88; font-size:0.8rem;">
        已有 <span style="color:#C084FC;">{stats['total_completions']}</span> 位赛博人完成测试
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  测试页
# ══════════════════════════════════════════════════════════════
def render_testing():
    qi        = st.session_state.q_index
    phase_idx = _phase_idx(qi)
    pct       = int((qi / TOTAL_QUESTIONS) * 100)

    st.markdown(f"""
    <div class="phase-badge phase-{phase_idx}">{PHASE_NAMES[phase_idx]} · {PHASE_DESCS[phase_idx]}</div>
    <div class="progress-wrap">
      <div class="progress-track"><div class="progress-fill" style="width:{pct}%"></div></div>
      <span class="progress-label">{qi}/{TOTAL_QUESTIONS}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── 取题（三层缓存）────────────────────────────────────────
    if st.session_state.current_q is None:
        spinner_msg = "⚡ 从缓存池取题…" if not pool.needs_refill(phase_idx) else "🤖 AI 出题中…"
        with st.spinner(spinner_msg):
            try:
                q, from_cache = get_question(pool, st.session_state.history, qi)
                st.session_state.current_q             = q
                st.session_state.current_q_from_cache  = from_cache
                st.session_state.cache_log.append((qi, from_cache))
            except Exception as e:
                st.error(f"出题失败：{e}")
                if st.button("重试"):
                    st.rerun()
                return

    q          = st.session_state.current_q
    from_cache = st.session_state.current_q_from_cache

    # ── 缓存标记 ─────────────────────────────────────────────
    badge = '<span class="cache-badge">⚡ 缓存</span>' if from_cache \
            else '<span class="api-badge">🤖 AI生成</span>'
    st.markdown(f'<div class="question-box">{q["question"]}{badge}</div>', unsafe_allow_html=True)

    options = [f'{opt["id"]}. {opt["text"]}' for opt in q["options"]]
    chosen  = st.radio("选择你的答案", options, index=None, key=f"radio_{qi}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_label = "✅ 确认" if qi < TOTAL_QUESTIONS - 1 else "🎯 提交答卷"
        if st.button(btn_label, disabled=(chosen is None), use_container_width=True):
            chosen_id    = chosen[0]
            selected_opt = next(o for o in q["options"] if o["id"] == chosen_id)
            phase_name   = PHASE_NAMES[phase_idx]

            st.session_state.history.append({
                "question":     q["question"],
                "answer_id":    chosen_id,
                "answer_text":  selected_opt["text"],
                "answer_traits": selected_opt.get("traits", []),
                "phase":        phase_name,
            })
            save_answer(
                st.session_state.session_id, qi,
                q["question"], chosen_id,
                selected_opt["text"], selected_opt.get("traits", []),
            )

            st.session_state.q_index   += 1
            st.session_state.current_q  = None

            if st.session_state.q_index >= TOTAL_QUESTIONS:
                st.session_state.phase = "generating"
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  生成结果（过渡页）
# ══════════════════════════════════════════════════════════════
def render_generating():
    st.markdown('<div class="hero-title" style="font-size:2rem;">🌀 正在分析你的精神状态</div>', unsafe_allow_html=True)
    msgs = ["正在解析你的赛博DNA…", "量子纠缠你的回答中…", "草台班子AI紧急会议中…", "分析你的emo体质…"]
    ph   = st.empty()
    for i, msg in enumerate(msgs[:3]):
        ph.markdown(f'<div style="text-align:center;color:#8B8BA8;padding:1rem;">{msg}</div>', unsafe_allow_html=True)
        time.sleep(0.7)
    try:
        result = generate_result(st.session_state.history)
        st.session_state.result = result
        save_result(st.session_state.session_id, result)
        try:
            store_personality_vector(st.session_state.session_id, result, st.session_state.history)
        except Exception:
            pass
        st.session_state.phase = "result"
        st.rerun()
    except Exception as e:
        st.error(f"分析失败：{e}")
        if st.button("重试"):
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  结果页
# ══════════════════════════════════════════════════════════════
def render_result():
    r = st.session_state.result
    if not r:
        st.session_state.phase = "welcome"
        st.rerun()

    st.markdown(f"""
    <div class="result-hero">
      <div class="result-title">{r.get('meme_title','???')}</div>
      <div class="result-sub">{r.get('meme_subtitle','')}</div>
      <div class="result-desc">{r.get('description','').replace(chr(10),'<br>')}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">人格维度</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="dim-grid">
      <div class="dim-card"><div class="dim-label">社交能量 E/I</div><div class="dim-val">{r.get('dimension_ei','—')}</div></div>
      <div class="dim-card"><div class="dim-label">思维模式</div><div class="dim-val">{r.get('dimension_ap','—')}</div></div>
      <div class="dim-card"><div class="dim-label">决策风格</div><div class="dim-val">{r.get('dimension_sr','—')}</div></div>
      <div class="dim-card"><div class="dim-label">能量状态 躺/卷</div><div class="dim-val">{r.get('dimension_lc','—')}</div></div>
    </div>
    """, unsafe_allow_html=True)

    energy = r.get('energy_level', 50)
    chaos  = r.get('chaos_index', 50)
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-card">
        <div class="metric-val">{energy}</div>
        <div class="metric-lbl">精神能量值</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{chaos}</div>
        <div class="metric-lbl">混沌指数</div>
      </div>
      <div class="metric-card">
        <div class="metric-val" style="font-size:0.85rem;padding-top:6px;">{r.get('internet_age','—')}</div>
        <div class="metric-lbl">冲浪段位</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">人格标签</div>', unsafe_allow_html=True)
    chips = "".join(f'<span class="trait-chip">{t}</span>' for t in r.get("traits", []))
    st.markdown(f'<div class="traits-wrap">{chips}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">你最可能说出的话</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="quote-box">"{r.get("famous_quote","")}"</div>', unsafe_allow_html=True)

    with st.expander("📖 深度解读"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🧬 人生哲学**")
            st.markdown(f"> {r.get('life_philosophy','—')}")
            st.markdown("**👥 同类型人格原型**")
            st.markdown(r.get('same_type_meme','—'))
        with c2:
            st.markdown("**⚠️ 人格弱点**")
            st.markdown(f"> {r.get('weak_point','—')}")
            st.markdown("**✨ 高光时刻**")
            st.markdown(f"> {r.get('peak_state','—')}")

    # ── 本次测试缓存统计 ────────────────────────────────────
    cache_log = st.session_state.get("cache_log", [])
    if cache_log:
        hits = sum(1 for _, c in cache_log if c)
        total = len(cache_log)
        st.markdown('<div class="section-title">本次测试缓存表现</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:rgba(74,222,128,0.06);border:1px solid rgba(74,222,128,0.2);
                    border-radius:12px;padding:14px 16px;font-size:0.88rem;">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="color:#A8A8C8;">缓存命中</span>
            <span style="color:#4ADE80;">{hits}/{total} 题 &nbsp;({round(hits/total*100)}%)</span>
          </div>
          <div class="hit-rate-bar">
            <div class="hit-rate-fill" style="width:{round(hits/total*100)}%"></div>
          </div>
          <div style="color:#6B6B88;font-size:0.75rem;margin-top:8px;">
            {'⚡ 缓存命中=无 API 延迟 &nbsp;·&nbsp; ' if hits>0 else ''}🤖 AI 生成={total-hits} 次调用
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 相似人格 ─────────────────────────────────────────────
    st.markdown('<div class="section-title">🔍 与你相似的灵魂</div>', unsafe_allow_html=True)
    try:
        similar = find_similar_personalities(st.session_state.session_id, top_k=3)
        if similar:
            for s in similar:
                trait_str = " ".join(f"`{t}`" for t in s["traits"][:3] if t)
                st.markdown(f"""
                <div class="similar-card">
                  <span style="color:#C084FC;font-weight:500;">{s['meme_title']}</span>
                  <span style="color:#9B7FE8;font-size:0.85rem;">相似度 {s['similarity']}%</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6B6B88;font-size:0.85rem;">暂无足够数据，你是先行者 👾</div>', unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 再测一次", use_container_width=True):
            for k in ["history","current_q","q_index","result","session_id","cache_log"]:
                st.session_state[k] = [] if k in ("history","cache_log") else (0 if k=="q_index" else None)
            st.session_state.phase = "welcome"
            st.rerun()
    with c2:
        if st.button("📊 数据面板", use_container_width=True):
            st.session_state.phase = "dashboard"
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  数据面板（含缓存监控）
# ══════════════════════════════════════════════════════════════
def render_dashboard():
    st.markdown('<div class="hero-title" style="font-size:1.8rem;">📊 数据面板</div>', unsafe_allow_html=True)

    # ── 全局统计 ─────────────────────────────────────────────
    stats = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("总测试次数", stats["total_sessions"])
    c2.metric("完成测试",   stats["total_completions"])

    # ── 缓存命中率面板 ────────────────────────────────────────
    st.markdown('<div class="section-title">⚡ 题目缓存监控</div>', unsafe_allow_html=True)

    api_stats  = get_cache_api_stats()
    pool_stats = get_cache_pool_status()
    mem_stats  = pool.stats()

    hit_rate = api_stats["hit_rate"]
    hr_color = "#4ADE80" if hit_rate >= 60 else ("#FBBF24" if hit_rate >= 30 else "#F06464")

    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                border-radius:16px;padding:1.2rem 1.4rem;margin-bottom:1rem;">

      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <span style="color:#A8A8C8;font-size:0.88rem;">总体缓存命中率</span>
        <span style="font-size:1.4rem;font-weight:500;color:{hr_color};">{hit_rate}%</span>
      </div>
      <div class="hit-rate-bar" style="margin-bottom:16px;">
        <div class="hit-rate-fill" style="width:{hit_rate}%;"></div>
      </div>

      <div class="cache-stat-row">
        <span class="cache-stat-label">⚡ 缓存命中次数</span>
        <span class="cache-stat-val">{api_stats['cache_hits']}</span>
      </div>
      <div class="cache-stat-row">
        <span class="cache-stat-label">🤖 API 调用次数</span>
        <span class="cache-stat-val warn">{api_stats['api_calls']}</span>
      </div>
      <div class="cache-stat-row" style="border:none;">
        <span class="cache-stat-label">🔄 后台预热次数</span>
        <span class="cache-stat-val">{api_stats['prefetch_count']}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 各 Phase 题目池 ──────────────────────────────────────
    phase_labels = {0: "🌱 热身", 1: "⚡ 觉醒", 2: "🌀 飞升"}
    st.markdown('<div class="section-title">题目池状态</div>', unsafe_allow_html=True)

    for p_idx in range(3):
        db_info  = pool_stats.get(f"phase_{p_idx}", {"count": 0, "total_used": 0})
        mem_size = mem_stats.get(f"phase_{p_idx}", 0)
        db_count = db_info["count"]
        used     = db_info["total_used"]

        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:12px 14px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="color:#C8C6E0;font-size:0.9rem;">{phase_labels[p_idx]}</span>
            <span style="color:#6B6B88;font-size:0.78rem;">SQLite: {db_count}题 · 内存: {mem_size}题 · 累计用 {used}次</span>
          </div>
          <div class="hit-rate-bar">
            <div style="height:100%;width:{min(db_count/POOL_MIN_SIZE*100,100):.0f}%;
                        background:linear-gradient(90deg,#9B7FE8,#C084FC);border-radius:999px;"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 最近结果 ─────────────────────────────────────────────
    st.markdown('<div class="section-title">最近完成的测试</div>', unsafe_allow_html=True)
    for row in get_recent_results(6):
        st.markdown(f"""
        <div class="similar-card">
          <span style="color:#C084FC;font-weight:500;">{row['meme_title']}</span>
          <span style="color:#6B6B88;font-size:0.78rem;">{row['created_at'][:10]}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── 人格标签分布 ─────────────────────────────────────────
    st.markdown('<div class="section-title">人格标签分布</div>', unsafe_allow_html=True)
    dist  = get_trait_distribution()
    if dist:
        total = sum(dist.values())
        for tag, count in sorted(dist.items(), key=lambda x: -x[1])[:10]:
            pct = count / total
            st.markdown(f"""
            <div style="margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                <span style="color:#C8C6E0;font-size:0.85rem;">{tag}</span>
                <span style="color:#9B7FE8;font-size:0.82rem;">{count}</span>
              </div>
              <div class="hit-rate-bar">
                <div style="height:100%;width:{pct*100:.0f}%;background:linear-gradient(90deg,#9B7FE8,#C084FC);border-radius:999px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── ChromaDB ─────────────────────────────────────────────
    st.markdown('<div class="section-title">🧠 向量库聚类</div>', unsafe_allow_html=True)
    try:
        cluster = get_cluster_stats()
        st.caption(f"向量库共 {cluster['total']} 条人格向量")
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


# ══════════════════════════════════════════════════════════════
#  路由
# ══════════════════════════════════════════════════════════════
phase = st.session_state.phase
if   phase == "welcome":    render_welcome()
elif phase == "testing":    render_testing()
elif phase == "generating": render_generating()
elif phase == "result":     render_result()
elif phase == "dashboard":  render_dashboard()
else:
    st.session_state.phase = "welcome"
    st.rerun()