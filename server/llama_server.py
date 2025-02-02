"""Llama server model."""

import json
import logging
from collections.abc import Iterator
from typing import cast

from llama_cpp import (
    Any,
    ChatCompletionRequestMessage,
    ChatCompletionStreamResponse,
    CreateChatCompletionResponse,
    Llama,
    LlamaGrammar,
    Path,
)
from llama_cpp.llama_chat_format import Jinja2ChatFormatter
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from client.typedefs import (
    AnyCommands,
    LlamaClientConfig,
)
from server.common import get_streaming_logger
from server.const import LLAMA_AUTOGEN_GRAMMAR
from server.typedefs import LlamaServerConfig

log = logging.getLogger(__name__)


def _config_params(model: BaseSettings) -> dict[str, Any]:
    ret = {k: v for k, v in model.model_dump().items() if v is not None}
    for k, v in ret.items():
        log.debug(f'{model.__class__.__name__}.{k}: {v}')
    return ret


def _generate_grammar() -> LlamaGrammar:
    schema = AnyCommands.model_json_schema()
    return LlamaGrammar.from_json_schema(json.dumps(schema))


class LlamaServer(BaseModel):
    """Llama.cpp model."""

    _llm: Llama
    _grammar: LlamaGrammar
    server_config: LlamaServerConfig
    client_config: LlamaClientConfig
    _formatter: Jinja2ChatFormatter
    _streamer: logging.Logger

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def __init__(self, *args, **kwargs):
        """Initialize the Llama server."""
        super().__init__(*args, **kwargs)
        if LLAMA_AUTOGEN_GRAMMAR:
            log.info('Generating grammar automatically')
            self._grammar = _generate_grammar()
        else:
            log.info('Loading grammar from file')
            self._grammar = LlamaGrammar.from_file(Path('grammar.gbnf'))
        log.debug(f'Generated grammar: {self._grammar}')
        self._llm = Llama(**_config_params(self.server_config))

        context = self._llm.metadata.get('llama.context_length')
        if context and self.server_config.n_ctx > int(context):
            log.critical(f'Context length {self.server_config.n_ctx} exceeds metadata {context}')

        log.debug(json.dumps(self._llm.metadata, indent=2))
        template = self._llm.metadata['tokenizer.chat_template']

        try:
            eos_id = int(self._llm.metadata['tokenizer.ggml.eos_token_id'])
        except KeyError:
            eos_id = self._llm.token_eos()
        try:
            bos_id = int(self._llm.metadata['tokenizer.ggml.bos_token_id'])
        except KeyError:
            bos_id = self._llm.token_bos()

        # All methods to convert special tokens to text are private
        eos = self._llm._model.token_get_text(eos_id)  # noqa: SLF001 private access
        bos = self._llm._model.token_get_text(bos_id)  # noqa: SLF001 No idea how to fix this

        log.debug(f'Template: {template} (EOS: {eos} {eos_id}, BOS: {bos} {bos_id})')
        self._formatter = Jinja2ChatFormatter(
            template=template,
            eos_token=eos,
            bos_token=bos,
            stop_token_ids=[eos_id],
        )

        if self.client_config.stream:
            self._streamer = get_streaming_logger(self)

    def format(self, messages: list[ChatCompletionRequestMessage]) -> str:
        """Format messages in the model's chat format."""
        return self._formatter(llama=self._llm, messages=messages).prompt

    def tokenize(self, what: str | list[ChatCompletionRequestMessage], special: bool) -> list[int]:
        """Tokenize text or messages."""
        if isinstance(what, str):
            return self._llm.tokenize(what.encode('utf-8'), add_bos=special, special=special)
        return self.tokenize(self.format(what), special=special)

    def chat(self, messages: list[ChatCompletionRequestMessage], config: LlamaClientConfig) -> str:
        """Chat with the model."""
        log.debug('Static parameters:')
        _ = _config_params(self.client_config)
        log.debug('Dynamic parameters:')
        dynamic_params = _config_params(config)
        log.debug('Resulting parameters:')
        params = _config_params(self.client_config.model_copy(update=dynamic_params))
        ret = self._llm.create_chat_completion(
            messages=messages,
            grammar=self._grammar,
            **params,
        )
        if self.client_config.stream:
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
