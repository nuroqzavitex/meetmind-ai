"""Pick the speech-to-text client for the worker from settings."""

import openai

from app.ai.stt import OpenAISTT, SpeechToText, UnconfiguredSTT
from app.core.config import Settings


def build_stt(settings: Settings) -> SpeechToText:
    key = settings.openai_api_key
    if key is None:
        return UnconfiguredSTT()
    client = openai.AsyncOpenAI(api_key=key.get_secret_value(), max_retries=2, timeout=600)
    return OpenAISTT(client, settings.stt_model)
