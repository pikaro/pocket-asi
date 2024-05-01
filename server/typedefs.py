"""Type definitions for the server."""

from typing import TypeVar

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from client.typedefs import AnyResult, LlamaClientConfig


class LlamaServerConfig(BaseSettings):
    """Options for llama.cpp server."""

    model_config = SettingsConfigDict(env_prefix='LLAMA_')

    model_path: str = 'undefined'
    n_ctx: int = 8192
    n_gpu_layers: int = -1
    verbose: bool = False

    split_mode: int | None = None
    main_gpu: int | None = None
    tensor_split: list[float] | None = None
    vocab_only: bool | None = None
    use_mmap: bool | None = None
    use_mlock: bool | None = None
    # Context Params
    seed: int | None = None
    n_batch: int | None = None
    n_threads: int | None = None
    n_threads_batch: int | None = None
    rope_scaling_type: int | None = None
    pooling_type: int | None = None
    rope_freq_base: float | None = None
    rope_freq_scale: float | None = None
    yarn_ext_factor: float | None = None
    yarn_attn_factor: float | None = None
    yarn_beta_fast: float | None = None
    yarn_beta_slow: float | None = None
    yarn_orig_ctx: int | None = None
    logits_all: bool | None = None
    embedding: bool | None = None
    offload_kqv: bool | None = None
    # Sampling Params
    last_n_tokens_size: int | None = None
    # LoRA Params
    lora_base: str | None = None
    lora_scale: float | None = None
    lora_path: str | None = None
    # Backend Params
    numa: bool | int | None = None
    # Chat Format Params
    chat_format: str | None = None
    # Speculative Decoding
    # KV cache quantization
    type_k: int | None = None
    type_v: int | None = None


ConfigT = TypeVar('ConfigT', LlamaServerConfig, LlamaClientConfig)


class SimpleShellResult(BaseModel):
    """Result of a command execution as expected by the LLM."""

    prompt: str
    command: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None


class SimpleFileReadResult(BaseModel):
    """Result of a file read operation as expected by the LLM."""

    file: str
    content: str | None = None
    error: str | None = None


class SimpleFileWriteResult(BaseModel):
    """Result of a file write operation as expected by the LLM."""

    file: str
    content: str
    written: int | None = None
    error: str | None = None


SimpleAnyResult = SimpleShellResult | SimpleFileReadResult | SimpleFileWriteResult
ResultHistory = list[AnyResult]
