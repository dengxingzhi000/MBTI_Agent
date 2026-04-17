"""
数据层：SQLite（结构化）+ ChromaDB（向量语义）+ 题目缓存池

缓存架构：
  L1 进程内存池  ← st.cache_resource 持有，零延迟命中
  L2 SQLite 题库 ← 跨进程持久化，按 phase+theme 分桶
  L3 ChromaDB    ← 向量化人格结果，相似度检索
"""

import sqlite3
import json
import uuid
import hashlib
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import chromadb

logger = logging.getLogger(__name__)

DATA_DIR    = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SQLITE_PATH = DATA_DIR / "mbti_meme.db"
CHROMA_PATH = DATA_DIR / "chroma_store"

# 每个 phase 桶至少保留多少道备用题才不再主动预热
POOL_MIN_SIZE = 6
POOL_MAX_SIZE = 30


# ══════════════════════════════════════════════════════════════
#  SQLite 连接 & 初始化
# ══════════════════════════════════════════════════════════════

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_sqlite():
    """建表 + 索引（幂等）"""
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS test_sessions (
        session_id   TEXT PRIMARY KEY,
        started_at   TEXT NOT NULL,
        finished_at  TEXT,
        total_qs     INTEGER DEFAULT 0,
        is_complete  INTEGER DEFAULT 0,
        user_tag     TEXT
    );

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
    );

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
    );

    CREATE TABLE IF NOT EXISTS question_cache (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        question_hash TEXT UNIQUE NOT NULL,
        phase         INTEGER NOT NULL,
        theme         TEXT    NOT NULL DEFAULT '',
        question_text TEXT    NOT NULL,
        options_json  TEXT    NOT NULL,
        used_count    INTEGER DEFAULT 0,
        last_used_at  TEXT,
        created_at    TEXT    NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_qcache_phase ON question_cache(phase);
    CREATE INDEX IF NOT EXISTS idx_qcache_used  ON question_cache(used_count, phase);

    CREATE TABLE IF NOT EXISTS global_stats (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
#  L1 进程内存池
# ══════════════════════════════════════════════════════════════

class QuestionPool:
    """
    按 phase 分桶的内存题目池，由 st.cache_resource 持有。
    结构：{ phase_int: [question_dict, ...] }
    """

    def __init__(self):
        self._buckets: dict[int, list[dict]] = {0: [], 1: [], 2: []}

    def load_from_db(self):
        """进程启动时从 SQLite 批量加载全部题目"""
        conn = get_conn()
        rows = conn.execute(
            "SELECT phase, question_text, options_json, theme FROM question_cache ORDER BY RANDOM()"
        ).fetchall()
        conn.close()

        for row in rows:
            p = row["phase"]
            q = {
                "question": row["question_text"],
                "theme":    row["theme"],
                "options":  json.loads(row["options_json"]),
            }
            if p in self._buckets:
                self._buckets[p].append(q)

        total = sum(len(v) for v in self._buckets.values())
        logger.info(f"[Pool] 初始加载 {total} 道题目")

    def pop(self, phase: int, used_texts: set[str]) -> Optional[dict]:
        """
        取一道未出过的题。不从桶里删除——支持跨用户复用。
        Returns None 表示缓存未命中。
        """
        bucket = self._buckets.get(phase, [])
        candidates = [q for q in bucket if q["question"] not in used_texts]
        if not candidates:
            return None
        return random.choice(candidates)

    def put(self, phase: int, question: dict):
        bucket = self._buckets.setdefault(phase, [])
        if any(q["question"] == question["question"] for q in bucket):
            return
        bucket.append(question)

    def size(self, phase: int) -> int:
        return len(self._buckets.get(phase, []))

    def needs_refill(self, phase: int) -> bool:
        return self.size(phase) < POOL_MIN_SIZE

    def stats(self) -> dict[str, int]:
        return {f"phase_{p}": len(b) for p, b in self._buckets.items()}


# ══════════════════════════════════════════════════════════════
#  L2 SQLite 题目缓存读写
# ══════════════════════════════════════════════════════════════

def persist_question(phase: int, question_text: str, options: list, theme: str = "") -> bool:
    """
    将新题写入 SQLite。
    Returns True=写入新记录，False=已存在（仅更新计数）。
    """
    h = hashlib.md5(question_text.encode("utf-8")).hexdigest()
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO question_cache
                (question_hash, phase, theme, question_text, options_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (h, phase, theme, question_text,
              json.dumps(options, ensure_ascii=False),
              datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def mark_question_used(question_text: str):
    """题目被实际下发给用户时调用，递增使用计数"""
    h = hashlib.md5(question_text.encode("utf-8")).hexdigest()
    conn = get_conn()
    conn.execute("""
        UPDATE question_cache
           SET used_count    = used_count + 1,
               last_used_at  = ?
         WHERE question_hash = ?
    """, (datetime.now().isoformat(), h))
    conn.commit()
    conn.close()


def get_cache_pool_status() -> dict:
    """各 phase 缓存数量统计，供 Dashboard 展示"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT phase, COUNT(*) as cnt, SUM(used_count) as total_used
          FROM question_cache
         GROUP BY phase ORDER BY phase
    """).fetchall()
    conn.close()
    return {
        f"phase_{r['phase']}": {
            "count":      r["cnt"],
            "total_used": r["total_used"] or 0,
        }
        for r in rows
    }


def get_cache_api_stats() -> dict:
    """命中率统计"""
    conn = get_conn()
    stats = {}
    for key in ("cache_hits", "api_calls", "prefetch_count"):
        row = conn.execute("SELECT value FROM global_stats WHERE key=?", (key,)).fetchone()
        stats[key] = int(row["value"]) if row else 0
    conn.close()
    total = stats["cache_hits"] + stats["api_calls"]
    stats["hit_rate"] = round(stats["cache_hits"] / total * 100, 1) if total > 0 else 0.0
    return stats


# ══════════════════════════════════════════════════════════════
#  Session / Answer / Result
# ══════════════════════════════════════════════════════════════

def create_session(user_tag: str = "") -> str:
    sid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO test_sessions (session_id, started_at, user_tag) VALUES (?,?,?)",
        (sid, datetime.now().isoformat(), user_tag)
    )
    conn.commit()
    conn.close()
    _inc("total_sessions")
    return sid


def save_answer(session_id: str, q_index: int, question: str,
                option_id: str, option_text: str, traits: list[str]):
    conn = get_conn()
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
    conn = get_conn()
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
    _inc("total_completions")


def get_recent_results(limit: int = 10) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.meme_title, r.meme_subtitle, r.energy_level,
               r.chaos_index, r.dimension_ei, r.created_at
          FROM personality_results r
         ORDER BY r.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trait_distribution() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT traits FROM personality_results").fetchall()
    conn.close()
    from collections import Counter
    counter = Counter()
    for row in rows:
        counter.update(json.loads(row["traits"] or "[]"))
    return dict(counter.most_common(12))


def get_stats() -> dict:
    conn = get_conn()
    stats = {}
    for key in ("total_sessions", "total_completions"):
        row = conn.execute("SELECT value FROM global_stats WHERE key=?", (key,)).fetchone()
        stats[key] = int(row["value"]) if row else 0
    conn.close()
    return stats


def _inc(key: str, amount: int = 1):
    conn = get_conn()
    conn.execute("""
        INSERT INTO global_stats (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + ?
    """, (key, amount, amount))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
#  ChromaDB
# ══════════════════════════════════════════════════════════════

_chroma_client = None
_collection    = None


def get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection    = _chroma_client.get_or_create_collection(
            name="personality_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def store_personality_vector(session_id: str, result: dict, history: list[dict]):
    answers_text = " | ".join(f"{h['question']} → {h['answer_text']}" for h in history)
    traits_text  = " ".join(result.get("traits", []))
    doc = f"{result.get('meme_title', '')} {traits_text} {answers_text}"
    metadata = {
        "session_id":   session_id,
        "meme_title":   result.get("meme_title", ""),
        "energy_level": result.get("energy_level", 50),
        "chaos_index":  result.get("chaos_index", 50),
        "dimension_ei": result.get("dimension_ei", ""),
        "dimension_ap": result.get("dimension_ap", ""),
        "traits":       ",".join(result.get("traits", [])),
        "created_at":   datetime.now().isoformat(),
    }
    get_chroma_collection().upsert(documents=[doc], metadatas=[metadata], ids=[session_id])


def find_similar_personalities(session_id: str, top_k: int = 3) -> list[dict]:
    col   = get_chroma_collection()
    total = col.count()
    if total < 2:
        return []
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
            "meme_title":   meta["meme_title"],
            "similarity":   round((1 - dist) * 100, 1),
            "energy_level": meta["energy_level"],
            "traits":       meta.get("traits", "").split(","),
        })
    return similar[:top_k]


def get_cluster_stats() -> dict:
    col   = get_chroma_collection()
    total = col.count()
    if total == 0:
        return {"total": 0, "titles": {}}
    from collections import Counter
    all_data = col.get(include=["metadatas"])
    titles   = Counter(m.get("meme_title", "未知") for m in all_data["metadatas"])
    return {"total": total, "titles": dict(titles.most_common(8))}