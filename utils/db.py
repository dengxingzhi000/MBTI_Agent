"""
数据层：SQLite（结构化）+ ChromaDB（向量语义）
- SQLite  → 存储每次测试的完整记录、题目库、人格结果
- ChromaDB → 向量化用户回答，支持相似人格检索、聚类分析
"""

import sqlite3
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
import chromadb
from chromadb.config import Settings

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SQLITE_PATH = DATA_DIR / "mbti_meme.db"
CHROMA_PATH = DATA_DIR / "chroma_store"


# ─────────────────────────── SQLite ────────────────────────────

def get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite():
    """建表（幂等）"""
    conn = get_sqlite_conn()
    cur = conn.cursor()

    # 测试会话主表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_sessions (
        session_id   TEXT PRIMARY KEY,
        started_at   TEXT NOT NULL,
        finished_at  TEXT,
        total_qs     INTEGER DEFAULT 0,
        is_complete  INTEGER DEFAULT 0,
        user_tag     TEXT
    )""")

    # 每道题的回答
    cur.execute("""
    CREATE TABLE IF NOT EXISTS question_answers (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id   TEXT NOT NULL,
        q_index      INTEGER NOT NULL,
        question     TEXT NOT NULL,
        option_id    TEXT NOT NULL,
        option_text  TEXT NOT NULL,
        traits       TEXT NOT NULL,
        answered_at  TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
    )""")

    # 最终人格结果
    cur.execute("""
    CREATE TABLE IF NOT EXISTS personality_results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      TEXT NOT NULL UNIQUE,
        meme_title      TEXT,
        meme_subtitle   TEXT,
        description     TEXT,
        traits          TEXT,
        famous_quote    TEXT,
        same_type_meme  TEXT,
        energy_level    INTEGER,
        internet_age    TEXT,
        chaos_index     INTEGER,
        dimension_ei    TEXT,
        dimension_ap    TEXT,
        dimension_sr    TEXT,
        dimension_lc    TEXT,
        created_at      TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
    )""")

    # 题目缓存库（避免重复 AI 出题）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS question_cache (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        question_hash TEXT UNIQUE,
        question_text TEXT NOT NULL,
        options_json  TEXT NOT NULL,
        theme_tag     TEXT,
        used_count    INTEGER DEFAULT 0,
        created_at    TEXT NOT NULL
    )""")

    # 全局统计
    cur.execute("""
    CREATE TABLE IF NOT EXISTS global_stats (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")

    conn.commit()
    conn.close()


# ─── Session 操作 ───────────────────────────────────────────────

def create_session(user_tag: str = "") -> str:
    sid = str(uuid.uuid4())
    conn = get_sqlite_conn()
    conn.execute(
        "INSERT INTO test_sessions (session_id, started_at, user_tag) VALUES (?,?,?)",
        (sid, datetime.now().isoformat(), user_tag)
    )
    conn.commit()
    conn.close()
    _increment_stat("total_sessions")
    return sid


def save_answer(session_id: str, q_index: int, question: str,
                option_id: str, option_text: str, traits: list[str]):
    conn = get_sqlite_conn()
    conn.execute("""
        INSERT INTO question_answers
        (session_id, q_index, question, option_id, option_text, traits, answered_at)
        VALUES (?,?,?,?,?,?,?)
    """, (session_id, q_index, question, option_id, option_text,
          json.dumps(traits, ensure_ascii=False), datetime.now().isoformat()))
    conn.execute(
        "UPDATE test_sessions SET total_qs=? WHERE session_id=?",
        (q_index + 1, session_id)
    )
    conn.commit()
    conn.close()


def save_result(session_id: str, result: dict):
    conn = get_sqlite_conn()
    conn.execute("""
        INSERT OR REPLACE INTO personality_results
        (session_id, meme_title, meme_subtitle, description, traits,
         famous_quote, same_type_meme, energy_level, internet_age,
         chaos_index, dimension_ei, dimension_ap, dimension_sr, dimension_lc, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        session_id,
        result.get("meme_title"), result.get("meme_subtitle"),
        result.get("description"),
        json.dumps(result.get("traits", []), ensure_ascii=False),
        result.get("famous_quote"), result.get("same_type_meme"),
        result.get("energy_level", 50), result.get("internet_age", ""),
        result.get("chaos_index", 50),
        result.get("dimension_ei", "中间派"),
        result.get("dimension_ap", "中间派"),
        result.get("dimension_sr", "中间派"),
        result.get("dimension_lc", "中间派"),
        datetime.now().isoformat()
    ))
    conn.execute(
        "UPDATE test_sessions SET finished_at=?, is_complete=1 WHERE session_id=?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()
    _increment_stat("total_completions")


def get_recent_results(limit: int = 10) -> list[dict]:
    conn = get_sqlite_conn()
    rows = conn.execute("""
        SELECT r.meme_title, r.meme_subtitle, r.energy_level,
               r.chaos_index, r.dimension_ei, r.created_at
        FROM personality_results r
        ORDER BY r.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trait_distribution() -> dict:
    """统计最常见的人格标签"""
    conn = get_sqlite_conn()
    rows = conn.execute(
        "SELECT traits FROM personality_results"
    ).fetchall()
    conn.close()
    from collections import Counter
    counter = Counter()
    for row in rows:
        tags = json.loads(row["traits"] or "[]")
        counter.update(tags)
    return dict(counter.most_common(12))


def get_stats() -> dict:
    conn = get_sqlite_conn()
    stats = {}
    for key in ("total_sessions", "total_completions"):
        row = conn.execute(
            "SELECT value FROM global_stats WHERE key=?", (key,)
        ).fetchone()
        stats[key] = int(row["value"]) if row else 0
    conn.close()
    return stats


def _increment_stat(key: str):
    conn = get_sqlite_conn()
    conn.execute("""
        INSERT INTO global_stats (key, value) VALUES (?,1)
        ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
    """, (key,))
    conn.commit()
    conn.close()


# ─── 题目缓存 ────────────────────────────────────────────────────

def cache_question(question_text: str, options: list, theme_tag: str = ""):
    h = hashlib.md5(question_text.encode()).hexdigest()
    conn = get_sqlite_conn()
    try:
        conn.execute("""
            INSERT INTO question_cache (question_hash, question_text, options_json, theme_tag, created_at)
            VALUES (?,?,?,?,?)
        """, (h, question_text, json.dumps(options, ensure_ascii=False),
              theme_tag, datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


# ─────────────────────────── ChromaDB ──────────────────────────

_chroma_client = None
_collection = None


def get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _chroma_client.get_or_create_collection(
            name="personality_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def store_personality_vector(session_id: str, result: dict, history: list[dict]):
    """
    将人格结果向量化存入 ChromaDB
    文本特征 = 所有回答 + traits + 人格称号，用于相似度检索
    注：生产环境应使用 embedding model（如 text-embedding-3-small），
        此处用 ChromaDB 默认的 all-MiniLM-L6-v2 本地模型
    """
    # 构建语义文档
    answers_text = " | ".join(
        f"{h['question']} → {h['answer_text']}" for h in history
    )
    traits_text = " ".join(result.get("traits", []))
    doc = f"{result.get('meme_title', '')} {traits_text} {answers_text}"

    metadata = {
        "session_id": session_id,
        "meme_title": result.get("meme_title", ""),
        "energy_level": result.get("energy_level", 50),
        "chaos_index": result.get("chaos_index", 50),
        "dimension_ei": result.get("dimension_ei", ""),
        "dimension_ap": result.get("dimension_ap", ""),
        "traits": ",".join(result.get("traits", [])),
        "created_at": datetime.now().isoformat(),
    }

    col = get_chroma_collection()
    col.upsert(
        documents=[doc],
        metadatas=[metadata],
        ids=[session_id],
    )


def find_similar_personalities(session_id: str, top_k: int = 3) -> list[dict]:
    """检索与当前用户最相似的历史人格"""
    col = get_chroma_collection()
    total = col.count()
    if total < 2:
        return []

    # 先取当前用户的 embedding
    try:
        current = col.get(ids=[session_id], include=["documents"])
        if not current["documents"]:
            return []
        doc_text = current["documents"][0]
    except Exception:
        return []

    results = col.query(
        query_texts=[doc_text],
        n_results=min(top_k + 1, total),
        include=["metadatas", "distances"],
    )

    similar = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        if meta["session_id"] == session_id:
            continue
        similar.append({
            "meme_title": meta["meme_title"],
            "similarity": round((1 - dist) * 100, 1),
            "energy_level": meta["energy_level"],
            "traits": meta.get("traits", "").split(","),
        })
    return similar[:top_k]


def get_cluster_stats() -> dict:
    """获取向量库中人格分布统计"""
    col = get_chroma_collection()
    total = col.count()
    if total == 0:
        return {"total": 0, "titles": {}}

    all_data = col.get(include=["metadatas"])
    from collections import Counter
    titles = Counter(m.get("meme_title", "未知") for m in all_data["metadatas"])
    return {"total": total, "titles": dict(titles.most_common(8))}