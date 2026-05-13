"""
BGE-M3 sparse (lexical) 编码器 —— 直接基于 transformers，不依赖 FlagEmbedding。

背景：FlagEmbedding 1.2.x/1.3.x 的 __init__.py 做了急切全量导入，
与 transformers>=5.0 的内部符号变动不兼容（is_torch_fx_available 等），
且它连带加载一堆根本用不到的 LLM reranker 模型。本模块用 50 行 transformers
原生代码复刻 BGE-M3 的 sparse 路径，规避这些问题，顺便省一份 encoder 显存
（复用 HuggingFaceEmbeddings 已加载的底层模型）。

核心公式（参考 BAAI/bge-m3 官方实现）：
    weight_per_token = ReLU(sparse_linear(last_hidden_state))
    lexical_weights  = 按 token_id 做 max 聚合（去除 CLS/SEP/PAD/UNK）
"""
from __future__ import annotations

import logging
import os

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class BGEM3SparseEncoder:
    """BGE-M3 sparse 头，最小实现。"""

    def __init__(
        self,
        model_path: str,
        reuse_model=None,
        reuse_tokenizer=None,
        device: str = "cuda",
        use_fp16: bool = True,
        max_length: int = 8192,
    ):
        self._device = device
        self._max_length = max_length
        self._dtype = torch.float16 if (use_fp16 and device == "cuda") else torch.float32

        # 1) encoder + tokenizer：优先复用外部已加载实例，避免双份显存
        if reuse_model is not None and reuse_tokenizer is not None:
            self._model = reuse_model
            self._tokenizer = reuse_tokenizer
            self._owns_model = False
            logger.info("BGEM3SparseEncoder: reusing pre-loaded BGE-M3 encoder (no extra VRAM)")
        else:
            from transformers import AutoModel, AutoTokenizer
            logger.info(f"BGEM3SparseEncoder: loading fresh encoder from {model_path}")
            self._tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._model = AutoModel.from_pretrained(model_path)
            self._model = self._model.to(device)
            if self._dtype == torch.float16:
                self._model = self._model.half()
            self._model.eval()
            self._owns_model = True

        # 2) sparse_linear.pt：BGE-M3 模型目录里自带的稀疏头权重
        sparse_linear_path = os.path.join(model_path, "sparse_linear.pt")
        if not os.path.exists(sparse_linear_path):
            raise FileNotFoundError(
                f"sparse_linear.pt not found at {sparse_linear_path}. "
                f"BGE-M3 requires this file for sparse retrieval."
            )
        hidden_size = self._model.config.hidden_size  # 1024 for BGE-M3
        sparse_linear = nn.Linear(hidden_size, 1)
        state = torch.load(sparse_linear_path, map_location="cpu", weights_only=True)
        sparse_linear.load_state_dict(state)
        sparse_linear = sparse_linear.to(device).to(self._dtype).eval()
        self._sparse_linear = sparse_linear

        # 3) 需要从输出里剔除的特殊 token（它们的稀疏权重无语义意义）
        special_ids = {
            self._tokenizer.cls_token_id,
            self._tokenizer.sep_token_id,
            self._tokenizer.pad_token_id,
            self._tokenizer.unk_token_id,
        }
        self._special_ids = {i for i in special_ids if i is not None}

    @torch.inference_mode()
    def encode_sparse(
        self, texts: list[str], batch_size: int = 16,
    ) -> list[dict[int, float]]:
        """返回 list[dict[token_id, weight]]，每个 dict 对应一个输入文本。"""
        if not texts:
            return []

        results: list[dict[int, float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            enc = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            ).to(self._device)

            out = self._model(**enc, return_dict=True)
            hidden = out.last_hidden_state                   # [B, L, H]
            # sparse_linear dtype 与 hidden 对齐（fp16 GPU 场景）
            if hidden.dtype != self._dtype:
                hidden = hidden.to(self._dtype)
            weights = F.relu(self._sparse_linear(hidden).squeeze(-1))  # [B, L]

            ids = enc["input_ids"]
            mask = enc["attention_mask"].bool()

            for j in range(len(batch)):
                m = mask[j]
                tok_ids = ids[j][m].tolist()
                w = weights[j][m].float().tolist()
                agg: dict[int, float] = {}
                for tid, val in zip(tok_ids, w):
                    if tid in self._special_ids or val <= 0.0:
                        continue
                    # 同一 token 多次出现取 max，对齐 BGE-M3 原实现
                    prev = agg.get(tid)
                    if prev is None or prev < val:
                        agg[tid] = float(val)
                results.append(agg)

        return results
