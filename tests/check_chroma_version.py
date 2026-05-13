"""
检查 backend/data/chroma 目录下的数据是否与当前安装的 chromadb 版本兼容。

判断依据：
  - ChromaDB 0.x：使用 SQLite 存储，目录下存在 chroma.sqlite3
                  以及 UUID 子目录中的 HNSW 二进制索引文件（data_level0.bin / length.bin）
  - ChromaDB 1.x：使用 Parquet + DuckDB 存储，目录下存在 .parquet 文件或 chroma.duckdb

运行方式（在项目根目录，激活 venv 后）：
    python tests/check_chroma_version.py
"""

import os
import sys
import sqlite3

# ── 路径配置 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CHROMA_DIR   = os.path.join(PROJECT_ROOT, "backend", "data", "chroma")
# ─────────────────────────────────────────────────────────────────────────────

SEP = "─" * 60


def check_installed_version() -> str:
    """返回当前环境安装的 chromadb 版本字符串。"""
    try:
        import chromadb
        return chromadb.__version__
    except ImportError:
        return "未安装"


def detect_data_format(chroma_dir: str) -> dict:
    """
    扫描 chroma_dir，识别数据格式。
    返回包含以下键的字典：
        exists          : 目录是否存在
        sqlite_file     : chroma.sqlite3 的完整路径（若存在）
        hnsw_files      : HNSW 二进制文件列表（0.x 特征）
        parquet_files   : .parquet 文件列表（1.x 特征）
        duckdb_files    : .duckdb 文件列表（1.x 特征）
        detected_format : "0.x" | "1.x" | "empty" | "unknown"
    """
    result = {
        "exists":          os.path.isdir(chroma_dir),
        "sqlite_file":     None,
        "hnsw_files":      [],
        "parquet_files":   [],
        "duckdb_files":    [],
        "detected_format": "unknown",
    }

    if not result["exists"]:
        result["detected_format"] = "empty"
        return result

    for root, _dirs, files in os.walk(chroma_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            if fname == "chroma.sqlite3":
                result["sqlite_file"] = fpath
            elif fname in ("data_level0.bin", "length.bin", "header.bin", "link_lists.bin"):
                result["hnsw_files"].append(fpath)
            elif fname.endswith(".parquet"):
                result["parquet_files"].append(fpath)
            elif fname.endswith(".duckdb"):
                result["duckdb_files"].append(fpath)

    # 判断格式
    has_sqlite = result["sqlite_file"] is not None
    has_hnsw   = len(result["hnsw_files"]) > 0
    has_parquet_or_duckdb = len(result["parquet_files"]) > 0 or len(result["duckdb_files"]) > 0

    all_empty = not has_sqlite and not has_hnsw and not has_parquet_or_duckdb

    if all_empty:
        result["detected_format"] = "empty"
    elif has_sqlite or has_hnsw:
        result["detected_format"] = "0.x"
    elif has_parquet_or_duckdb:
        result["detected_format"] = "1.x"
    # 如果同时出现两种特征（部分迁移状态），保留 "unknown"

    return result


def read_sqlite_meta(sqlite_path: str) -> dict:
    """尝试读取 SQLite 数据库中的元数据，了解存储的集合和向量数量。"""
    meta = {"collections": [], "embeddings_count": 0, "error": None}
    try:
        conn = sqlite3.connect(sqlite_path)
        cur  = conn.cursor()

        # 查询集合
        try:
            cur.execute("SELECT id, name FROM collections")
            meta["collections"] = cur.fetchall()
        except sqlite3.OperationalError:
            pass

        # 查询向量数
        try:
            cur.execute("SELECT COUNT(*) FROM embeddings")
            meta["embeddings_count"] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        conn.close()
    except Exception as exc:
        meta["error"] = str(exc)
    return meta


def try_chromadb_connect(chroma_dir: str) -> dict:
    """尝试用当前版本的 chromadb 库连接数据目录，验证实际可用性。"""
    result = {"success": False, "collections": [], "error": None}
    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_dir)
        cols = client.list_collections()
        result["success"]     = True
        result["collections"] = [c.name for c in cols]
    except Exception as exc:
        result["error"] = str(exc)
    return result


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    print(SEP)
    print(" ChromaDB 数据格式兼容性检查")
    print(SEP)

    # 1. 当前安装版本
    installed_ver = check_installed_version()
    print(f"\n[1] 已安装的 chromadb 版本 : {installed_ver}")
    print(f"    数据目录               : {CHROMA_DIR}")

    # 2. 扫描数据目录
    fmt = detect_data_format(CHROMA_DIR)
    print(f"\n[2] 数据目录扫描结果")
    print(f"    目录存在    : {fmt['exists']}")
    print(f"    检测到格式  : {fmt['detected_format']}")

    if fmt["sqlite_file"]:
        print(f"    chroma.sqlite3 : {fmt['sqlite_file']}")
    if fmt["hnsw_files"]:
        print(f"    HNSW 二进制文件 ({len(fmt['hnsw_files'])} 个) :")
        for f in fmt["hnsw_files"]:
            print(f"        {f}")
    if fmt["parquet_files"]:
        print(f"    Parquet 文件 ({len(fmt['parquet_files'])} 个) :")
        for f in fmt["parquet_files"][:5]:
            print(f"        {f}")
    if fmt["duckdb_files"]:
        print(f"    DuckDB 文件 ({len(fmt['duckdb_files'])} 个) :")
        for f in fmt["duckdb_files"]:
            print(f"        {f}")

    # 3. 若为 0.x 格式，读取 SQLite 元数据
    if fmt["sqlite_file"]:
        print(f"\n[3] SQLite 元数据（0.x 格式）")
        meta = read_sqlite_meta(fmt["sqlite_file"])
        if meta["error"]:
            print(f"    读取失败: {meta['error']}")
        else:
            print(f"    集合数量    : {len(meta['collections'])}")
            for col_id, col_name in meta["collections"]:
                print(f"        - {col_name}  (id: {col_id})")
            print(f"    向量条数    : {meta['embeddings_count']}")

    # 4. 尝试用当前 chromadb 版本实际连接
    print(f"\n[4] 尝试用 chromadb {installed_ver} 实际连接数据目录 ...")
    conn_result = try_chromadb_connect(CHROMA_DIR)
    if conn_result["success"]:
        print(f"    ✅ 连接成功，找到集合：{conn_result['collections'] or '（空）'}")
    else:
        print(f"    ❌ 连接失败：{conn_result['error']}")

    # 5. 兼容性结论
    print(f"\n{SEP}")
    print(" 兼容性结论")
    print(SEP)

    installed_major = installed_ver.split(".")[0] if installed_ver != "未安装" else "?"

    if fmt["detected_format"] == "empty":
        print(" ✅ 数据目录为空，无历史数据，当前版本可直接使用。")

    elif fmt["detected_format"] == "0.x" and installed_major == "1":
        print(" ❌ 不兼容！")
        print(f"    数据格式 : 0.x（SQLite + HNSW）")
        print(f"    已安装版 : chromadb {installed_ver}（1.x 使用 Parquet/DuckDB）")
        print()
        print(" 解决方案：删除旧数据后重新上传文档建立索引。")
        print()
        print("    # PowerShell 命令（在项目根目录执行）：")
        print(f"    Remove-Item -Recurse -Force '{CHROMA_DIR}\\*'")
        print()
        print("    删除后重启后端，再通过前端知识库界面重新上传文档。")

    elif fmt["detected_format"] == "0.x" and installed_major == "0":
        print(" ✅ 数据格式（0.x）与已安装版本（0.x）一致，兼容。")

    elif fmt["detected_format"] == "1.x" and installed_major == "1":
        if conn_result["success"]:
            print(" ✅ 数据格式（1.x）与已安装版本（1.x）一致，连接正常。")
        else:
            print(" ⚠️  格式匹配（1.x），但实际连接失败，请检查错误信息。")

    elif fmt["detected_format"] == "1.x" and installed_major == "0":
        print(" ❌ 不兼容！")
        print(f"    数据格式 : 1.x（Parquet/DuckDB）")
        print(f"    已安装版 : chromadb {installed_ver}（0.x 使用 SQLite）")
        print(" 请升级 chromadb：pip install 'chromadb>=1.0.0'")

    else:
        if conn_result["success"]:
            print(f" ✅ 实际连接成功，数据可正常使用（格式：{fmt['detected_format']}）。")
        else:
            print(f" ⚠️  格式不确定（{fmt['detected_format']}），且连接失败。")
            print(f"    错误：{conn_result['error']}")

    print(SEP)


if __name__ == "__main__":
    main()
