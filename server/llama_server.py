"""Llama server model."""

import json
import logging
import os
from collections.abc import Iterator
from typing import cast

from llama_cpp import (
    Any,
    ChatCompletionRequestMessage,
    ChatCompletionStreamResponse,
    CreateChatCompletionResponse,
    Llama,
    LlamaGrammar,
)
from llama_cpp.llama_chat_format import Jinja2ChatFormatter
from pydantic import BaseModel

from client.typedefs import LlamaClientConfig
from server.common import env_bool, get_streaming_logger
from server.const import LLAMA_CLIENT_DEFAULTS, LLAMA_SERVER_DEFAULTS
from server.typedefs import ConfigT, LlamaServerConfig

log = logging.getLogger(__name__)

STREAM_RESPONSE = env_bool('LLAMA_STREAM_RESPONSE')


class LlamaServer(BaseModel):
    """Llama.cpp model."""

    _llm: Llama
    _grammar: LlamaGrammar
    _server_config: LlamaServerConfig
    _client_config: LlamaClientConfig
    _formatter: Jinja2ChatFormatter
    _streamer: logging.Logger

    def __init__(self):
        """Initialize the Llama server."""
        super().__init__()
        self._configure()
        self._grammar = LlamaGrammar.from_file('grammar.gbnf')
        self._llm = Llama(
            model_path=os.environ['LLAMA_MODEL_PATH'],
            n_gpu_layers=-1,
            n_ctx=self._server_config.n_ctx,
            verbose=env_bool('LLAMA_VERBOSE'),
        )
        context = self._llm.metadata.get('llama.context_length')

        if context and self._server_config.n_ctx > int(context):
            log.critical(f'Context lengthl {self._server_config.n_ctx} exceeds {context}')

        if context and not os.getenv('LLAMA_N_CTX'):
            log.info(f'Using model default context length: {context}')
            self._server_config.n_ctx = int(context)

        log.info(json.dumps(self._llm.metadata, indent=2))
        template = self._llm.metadata['tokenizer.chat_template']

        try:
            eos_id = int(self._llm.metadata['tokenizer.ggml.eos_token_id'])
        except KeyError:
            eos_id = self._llm.token_eos()
        try:
            bos_id = int(self._llm.metadata['tokenizer.ggml.bos_token_id'])
        except KeyError:
            bos_id = self._llm.token_bos()

        eos = self._llm._model.token_get_text(eos_id)  # noqa: SLF001 private access
        bos = self._llm._model.token_get_text(bos_id)  # noqa: SLF001 No idea how to fix this

        log.info(f'Template: {template} (EOS: {eos} {eos_id}, BOS: {bos} {bos_id})')
        self._formatter = Jinja2ChatFormatter(
            template=template,
            eos_token=eos,
            bos_token=bos,
            stop_token_ids=[eos_id],
        )

        if STREAM_RESPONSE:
            self._streamer = get_streaming_logger(self)

    def get_server_config(self, key: str) -> Any:
        """Get a config value."""
        return self._server_config.model_dump()[key]

    def format(self, messages: list[ChatCompletionRequestMessage]) -> str:
        """Tokenize messages."""
        return self._formatter(llama=self._llm, messages=messages).prompt

    def tokenize(self, text: str) -> list[int]:
        """Tokenize text."""
        return self._llm.tokenize(text.encode('utf-8'), add_bos=True, special=True)

    def tokenize_messages(self, messages: list[ChatCompletionRequestMessage]) -> list[int]:
        """Tokenize messages."""
        return self.tokenize(self.format(messages))

    def _configure(self):
        """Read config options from environment / defaults."""

        def _from_env(defaults: ConfigT) -> ConfigT:
            ret = defaults.model_dump().copy()
            for key in defaults.model_dump():
                if f'LLAMA_{key.upper()}' in os.environ:
                    ret[key] = os.environ[f'LLAMA_{key.upper()}']
                ret[key] = type(defaults.model_dump()[key])(ret[key])
            return type(defaults)(**ret)

        self._server_config = _from_env(LlamaServerConfig.model_validate(LLAMA_SERVER_DEFAULTS))
        self._client_config = _from_env(LlamaClientConfig.model_validate(LLAMA_CLIENT_DEFAULTS))

    def chat(self, messages: list[ChatCompletionRequestMessage], config: LlamaClientConfig) -> str:
        """Chat with the model."""
        config_dict = {k: v for k, v in config.model_dump().items() if v}
        config_dict = self._client_config.model_dump() | config_dict
        # Returns an iterator if streaming
        ret = self._llm.create_chat_completion(
            messages=messages,
            grammar=self._grammar,
            **config_dict,
            stream=STREAM_RESPONSE,
        )
        if STREAM_RESPONSE:
            log.debug('Streaming response')
            gen = cast(Iterator[ChatCompletionStreamResponse], ret)
            tokens = []
            for response in gen:
                if 'content' not in response['choices'][0]['delta']:
                    continue
                token = response['choices'][0]['delta']['content']
                tokens.append(token)
                self._streamer.info(token)
            self._streamer.info('\n')
            return ''.join(tokens)
        log.debug('Non-streaming response')
        resp = cast(CreateChatCompletionResponse, ret)
        tokens = resp['choices'][0]['message']['content']
        if not tokens:
            log.error('No tokens returned')
            return ''
        return tokens
