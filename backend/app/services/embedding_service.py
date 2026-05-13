"""
Embedding 服务管理模块。
负责：GPU 检测、Embedding 配置持久化、BGE-M3 模型下载进度追踪、Embeddings 工厂。
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")
EMBEDDING_CONFIG_FILE = os.path.join(DATA_DIR, "embedding_config.json")

BGE_M3_REPO_ID = "BAAI/bge-m3"
BGE_M3_LOCAL_PATH = os.path.join(MODELS_DIR, "bge-m3")
BGE_M3_TOTAL_MB = 2270.0  # 约 2.27 GB

BGE_RERANKER_REPO_ID = "BAAI/bge-reranker-v2-m3"
BGE_RERANKER_LOCAL_PATH = os.path.join(MODELS_DIR, "bge-reranker-v2-m3")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)


# ── 向量维度映射（用于判断切换模型是否需要清空 ChromaDB）──────────────

MODEL_DIMENSIONS: dict[str, int] = {
    "bge-m3": 1024,
    "bge-large-zh-v1.5": 1024,
    "bge-base-zh-v1.5": 768,
    "bge-small-zh-v1.5": 512,
    "minilm": 384,
}


# ── 配置 dataclass ────────────────────────────────────────────────────

@dataclass
class EmbeddingConfig:
    mode: str = "local"             # "local" | "online"
    local_model: str = "bge-m3"     # 本地模型标识
    use_gpu: bool = True             # 是否使用 GPU
    online_provider: str | None = None   # "volcengine" | "openai" | None
    online_api_key: str = ""
    # Multi-Query 多路召回开关（classic 路径）：
    #   开启时每次检索由 LLM 生成 3 个 variant 一起召回，再合并 / 融合；
    #   默认 OFF（见 plan-doc-dir/query改写方案汇总.md §九）
    multi_query_enabled: bool = False
    # Agentic RAG 档位开关（classic 路径）：
    #   "off"              : 完全走现有 classical（含启发式 rewrite / Multi-Query，不变）
    #   "grading_only"     : 跳启发式 rewrite → 单路检索 → Document Grading 过滤 → 生成
    #   "grading_rewrite"  : 同上 + Grading 通过率低时 rewrite 重试（最多 2 次；Multi-Query ON 时降 1）
    #   "full"             : 同 grading_rewrite + 生成后做 Hallucination Check（失败挂警告 banner）
    #   默认 "off"。仅在 intent=general AND use_knowledge_base=true 时触发。
    #   见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md
    agentic_rag_mode: str = "off"
    # Graph RAG（LightRAG）开关与查询模式（classic 路径，最高优先级）：
    #   启用时覆盖 Agentic RAG + Multi-Query；走 backend/data/lightrag/ 下的独立图+向量索引。
    #   查询模式对齐 LightRAG 原生：naive / local / global / hybrid / mix，默认 hybrid。
    #   见 plan-doc-dir/LightRAG集成落地.md
    graph_rag_enabled: bool = False
    graph_rag_query_mode: str = "hybrid"
    # Celery 异步向量化开关（默认 off）：
    #   开启时上传文档后走 Celery 队列（Redis 持久化 + Docker worker 消费），
    #   关闭时走原有 asyncio.create_task + asyncio.to_thread 路径。
    #   架构：worker 不加载 BGE-M3，只做 HTTP 转发到 backend 内部端点；
    #   削峰阀门 = worker --concurrency=N（默认 2）。
    #   见 plan-doc-dir/quizzical-spinning-parrot.md + analysis-for-backend/celery-module.md
    celery_enabled: bool = False


def get_config() -> EmbeddingConfig:
    """读取 embedding_config.json，不存在则返回默认值。"""
    if os.path.exists(EMBEDDING_CONFIG_FILE):
        try:
            with open(EMBEDDING_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EmbeddingConfig(**{k: v for k, v in data.items()
                                      if k in EmbeddingConfig.__dataclass_fields__})
        except Exception as e:
            logger.warning(f"Failed to load embedding config, using defaults: {e}")
    return EmbeddingConfig()


def save_config(config: EmbeddingConfig) -> None:
    """持久化配置到 embedding_config.json。"""
    with open(EMBEDDING_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, ensure_ascii=False, indent=2)


# ── GPU 检测 ──────────────────────────────────────────────────────────

def get_gpu_info() -> dict[str, Any]:
    """
    两层 GPU 检测：
    Layer 1：nvidia-smi（硬件层）
    Layer 2：torch.cuda.is_available()（PyTorch 层，是否真正可用）
    """
    result: dict[str, Any] = {
        "hardware_available": False,
        "name": None,
        "vram_total_gb": None,
        "vram_free_gb": None,
        "pytorch_cuda_available": False,
        "pytorch_mps_available": False,      # macOS Apple Silicon
        "accelerator": "cpu",                # "cuda" | "mps" | "cpu"，前端按此分支显示
        "pytorch_version": None,
        "cuda_version": None,
        "error": None,
    }

    # Layer 2: PyTorch 层检测
    # - macOS：检测 MPS（Apple Silicon）
    # - Linux / Windows：检测 CUDA
    try:
        import torch
        result["pytorch_version"] = torch.__version__

        if sys.platform == "darwin":
            mps_available = (
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
            result["pytorch_mps_available"] = mps_available
            if mps_available:
                result["hardware_available"] = True
                result["accelerator"] = "mps"
                result["name"] = "Apple Silicon (MPS)"
                # PyTorch MPS 目前没有等价 mem_get_info，保留 None
        else:
            result["pytorch_cuda_available"] = torch.cuda.is_available()
            if result["pytorch_cuda_available"]:
                result["hardware_available"] = True
                result["accelerator"] = "cuda"
                result["name"] = torch.cuda.get_device_name(0)
                result["cuda_version"] = torch.version.cuda
                props = torch.cuda.get_device_properties(0)
                result["vram_total_gb"] = round(props.total_memory / 1e9, 2)
                free, _ = torch.cuda.mem_get_info(0)
                result["vram_free_gb"] = round(free / 1e9, 2)
    except ImportError:
        result["error"] = "torch 未安装"
    except Exception as e:
        result["error"] = f"PyTorch 检测异常：{e}"
        result["pytorch_version"] = _get_torch_version_fallback()

    # Layer 1: nvidia-smi 硬件检测 —— 仅 Linux / Windows 且 PyTorch 层未探测到硬件时调用
    # macOS 上没有 nvidia-smi，直接跳过，避免 FileNotFoundError 噪音
    if sys.platform != "darwin" and not result["hardware_available"]:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                parts = out.stdout.strip().split(",")
                result["hardware_available"] = True
                result["name"] = parts[0].strip()
                result["vram_total_gb"] = round(float(parts[1].strip()) / 1024, 2)
        except Exception:
            pass

    return result


def _get_torch_version_fallback() -> str | None:
    try:
        import torch
        return torch.__version__
    except Exception:
        return None


# ── 本地模型状态检测 ──────────────────────────────────────────────────

def get_model_status() -> dict[str, Any]:
    """检测 BGE-M3 和 BGE-Reranker 本地下载状态。"""
    downloaded = _is_bge_m3_cached()
    size_bytes = _get_dir_size(BGE_M3_LOCAL_PATH) if downloaded else 0

    reranker_downloaded = _is_reranker_cached()
    reranker_size_bytes = _get_dir_size(BGE_RERANKER_LOCAL_PATH) if reranker_downloaded else 0

    return {
        "bge_m3": {
            "downloaded": downloaded,
            "path": BGE_M3_LOCAL_PATH,
            "size_gb": round(size_bytes / 1e9, 2) if size_bytes else 0,
            "expected_gb": BGE_M3_TOTAL_MB / 1000,
        },
        "bge_reranker": {
            "downloaded": reranker_downloaded,
            "path": BGE_RERANKER_LOCAL_PATH,
            "size_gb": round(reranker_size_bytes / 1e9, 2) if reranker_size_bytes else 0,
            "expected_gb": 2.4,
        },
    }


def _is_bge_m3_cached() -> bool:
    """检查 BGE-M3 是否已完整下载（至少包含 config.json 和 tokenizer_config.json）。"""
    if not os.path.isdir(BGE_M3_LOCAL_PATH):
        return False
    required = ("config.json", "tokenizer_config.json")
    files = os.listdir(BGE_M3_LOCAL_PATH)
    return all(f in files for f in required)


def _is_reranker_cached() -> bool:
    """检查 BGE-Reranker-v2-m3 是否已完整下载。"""
    if not os.path.isdir(BGE_RERANKER_LOCAL_PATH):
        return False
    required = ("config.json", "tokenizer_config.json")
    files = os.listdir(BGE_RERANKER_LOCAL_PATH)
    return all(f in files for f in required)


def _get_dir_size(path: str) -> int:
    """递归计算目录大小（字节）。"""
    if not os.path.exists(path):
        return 0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


# ── 模型下载进度追踪 ──────────────────────────────────────────────────

import threading
import time

_download_state: dict[str, Any] = {
    "status": "idle",       # idle / downloading / paused / done / failed
    "progress": 0.0,        # 0.0 ~ 1.0
    "downloaded_mb": 0.0,
    "total_mb": BGE_M3_TOTAL_MB,
    "speed_mbps": 0.0,      # 当前下载速度（MB/s）
    "error": "",
}

# 取消标志：下载线程每完成一个文件后检查
_cancel_event = threading.Event()


def get_download_state() -> dict[str, Any]:
    return dict(_download_state)


def _should_skip_bge_m3_file(filename: str) -> bool:
    """
    BGE-M3 仓库里冗余/无用文件，跳过可省 ~2.3GB：
      - onnx/*            : ONNX 推理格式（含 ~2.27GB 的 model.onnx_data），本项目没人用
                            （grep 全 backend 无 onnxruntime/optimum 引用）
      - imgs/*, *.jpg/png : README 配图
      - README.md, .gitattributes

    注意：BGE-M3 仓库**只有 pytorch_model.bin**，没有 model.safetensors，所以 .bin 必须保留。
    """
    if filename.startswith(("onnx/", "imgs/")):
        return True
    if filename in ("README.md", ".gitattributes", "long.jpg"):
        return True
    if filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return True
    return False


def _query_repo_total_mb() -> float | None:
    """
    通过 HF API 汇总仓库内**实际会下载的**文件大小（MB），跳过 _should_skip_bge_m3_file 命中的文件。
    失败返回 None。
    """
    try:
        from huggingface_hub import HfApi
        info = HfApi().repo_info(BGE_M3_REPO_ID, files_metadata=True)
        total_bytes = sum(
            (f.size or 0)
            for f in (info.siblings or [])
            if f.rfilename and not _should_skip_bge_m3_file(f.rfilename)
        )
        if total_bytes > 0:
            return round(total_bytes / 1e6, 1)
    except Exception as e:
        logger.warning(f"Failed to query BGE-M3 repo total size, fallback to estimate: {e}")
    return None


def _do_download_bge_m3_sync() -> None:
    """
    逐文件下载 BGE-M3，每个文件完成后检查取消标志。
    支持断点续传：已存在的文件会被 hf_hub_download 跳过。
    """
    from huggingface_hub import list_repo_files, hf_hub_download

    os.makedirs(BGE_M3_LOCAL_PATH, exist_ok=True)
    _download_state["status"] = "downloading"
    _download_state["error"] = ""
    _cancel_event.clear()

    # BGE-M3 仓库里同时存在 pytorch_model.bin / model.safetensors / onnx/* 等多份权重，
    # 真实总量（3GB+）大于硬编码的 2270MB，需动态修正，否则进度条会出现 3099/2270 > 100% 的怪象。
    real_total = _query_repo_total_mb()
    if real_total:
        _download_state["total_mb"] = real_total
        logger.info(f"BGE-M3 real repo size (from HF API): {real_total} MB")

    try:
        all_files = list(list_repo_files(BGE_M3_REPO_ID))
        file_list = [f for f in all_files if not _should_skip_bge_m3_file(f)]
        skipped = len(all_files) - len(file_list)
        logger.info(
            f"BGE-M3 has {len(all_files)} files in repo; "
            f"will download {len(file_list)}, skip {skipped} (onnx / pytorch_model.bin / imgs / docs)."
        )

        for filename in file_list:
            # 检查是否被用户取消
            if _cancel_event.is_set():
                _download_state["status"] = "paused"
                _download_state["speed_mbps"] = 0.0
                logger.info("BGE-M3 download paused by user.")
                return

            try:
                hf_hub_download(
                    repo_id=BGE_M3_REPO_ID,
                    filename=filename,
                    local_dir=BGE_M3_LOCAL_PATH,
                    local_dir_use_symlinks=False,
                )
            except Exception as e:
                logger.warning(f"Failed to download {filename}: {e}")

        _download_state["status"] = "done"
        _download_state["progress"] = 1.0
        _download_state["downloaded_mb"] = _download_state["total_mb"]
        _download_state["speed_mbps"] = 0.0
        logger.info("BGE-M3 download completed.")

    except Exception as e:
        _download_state["status"] = "failed"
        _download_state["error"] = str(e)
        _download_state["speed_mbps"] = 0.0
        logger.error(f"BGE-M3 download failed: {e}")


async def _poll_download_progress() -> None:
    """
    轮询目录大小更新进度和速度，直到下载结束（done / paused / failed）。
    """
    prev_mb = 0.0
    prev_time = time.monotonic()

    while _download_state["status"] == "downloading":
        await asyncio.sleep(2)
        size = _get_dir_size(BGE_M3_LOCAL_PATH)
        now_mb = size / 1e6
        now_time = time.monotonic()

        elapsed = now_time - prev_time
        if elapsed > 0:
            speed = max(0.0, (now_mb - prev_mb) / elapsed)
            _download_state["speed_mbps"] = round(speed, 2)

        prev_mb = now_mb
        prev_time = now_time

        # downloaded_mb 用真实目录大小，但封顶到 total_mb，避免 UI 出现 3099/2270 这种超标显示
        total_mb = _download_state["total_mb"] or BGE_M3_TOTAL_MB
        _download_state["downloaded_mb"] = round(min(now_mb, total_mb), 1)
        _download_state["progress"] = round(min(now_mb / total_mb, 0.99), 3)

    _download_state["speed_mbps"] = 0.0


def cancel_download() -> dict[str, str]:
    """请求停止下载（下载线程完成当前文件后暂停）。"""
    if _download_state["status"] != "downloading":
        return {"message": "当前未在下载"}
    _cancel_event.set()
    return {"message": "停止信号已发送，将在当前文件完成后暂停"}


async def start_download_bge_m3(resume: bool = True) -> dict[str, str]:
    """
    触发后台下载 BGE-M3。
    resume=True：断点续传（跳过已下载的文件）
    resume=False：重新下载（先清空目录）
    """
    if _download_state["status"] == "downloading":
        return {"message": "已在下载中"}
    if _is_bge_m3_cached():
        return {"message": "模型已存在，无需下载"}

    if not resume and os.path.exists(BGE_M3_LOCAL_PATH):
        import shutil as _shutil
        _shutil.rmtree(BGE_M3_LOCAL_PATH)
        logger.info("BGE-M3 local cache cleared for fresh download.")

    _cancel_event.clear()
    _download_state["status"] = "downloading"
    _download_state["progress"] = 0.0
    _download_state["downloaded_mb"] = _get_dir_size(BGE_M3_LOCAL_PATH) / 1e6
    _download_state["speed_mbps"] = 0.0
    _download_state["error"] = ""

    asyncio.create_task(asyncio.to_thread(_do_download_bge_m3_sync))
    asyncio.create_task(_poll_download_progress())
    return {"message": "下载已开始"}


# ── Embeddings 工厂 ───────────────────────────────────────────────────

def build_embeddings(config: EmbeddingConfig):
    """
    根据配置构建 LangChain Embeddings 对象。
    本地模型：HuggingFaceEmbeddings（BGE-M3 或 MiniLM）
    在线模式：预留扩展点
    """
    if config.mode == "online":
        return _build_online_embeddings(config)

    # 本地模式
    from langchain_huggingface import HuggingFaceEmbeddings

    model_path = BGE_M3_LOCAL_PATH if config.local_model == "bge-m3" else None
    if model_path is None or not _is_bge_m3_cached():
        raise RuntimeError("本地 BGE-M3 模型未下载，无法初始化 Embedding 服务。")

    # 检测实际可用设备
    device = _resolve_device(config.use_gpu)
    logger.info(f"Loading BGE-M3 on device={device}")

    return HuggingFaceEmbeddings(
        model_name=model_path,
        model_kwargs={
            "device": device,
        },
        encode_kwargs={
            "normalize_embeddings": True,  # BGE 系列需要归一化
            "batch_size": 32 if device in ("cuda", "mps") else 8,
        },
    )


def _resolve_device(prefer_gpu: bool) -> str:
    """
    根据用户偏好和实际 GPU 可用性决定推理设备。
    优先级：CUDA → MPS (Apple Silicon) → CPU。
    """
    if prefer_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
    return "cpu"


def _build_online_embeddings(config: EmbeddingConfig):
    """在线 Embedding 接口预留（火山引擎等），待实现。"""
    raise NotImplementedError("在线 Embedding 暂未实现，请使用本地模式。")
