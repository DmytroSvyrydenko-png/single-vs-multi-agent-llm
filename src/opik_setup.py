import os

import openai
import opik
from agents import set_trace_processors
from opik.integrations.openai import track_openai
from opik.integrations.openai.agents import OpikTracingProcessor

import config

_OPIK_READY = False


def ensure_opik_configured() -> None:
    global _OPIK_READY

    if _OPIK_READY:
        return

    os.environ["OPIK_PROJECT_NAME"] = config.OPIK_PROJECT_NAME

    configure_kwargs = {}
    if config.OPIK_API_KEY:
        configure_kwargs["api_key"] = config.OPIK_API_KEY
    if config.OPIK_WORKSPACE:
        configure_kwargs["workspace"] = config.OPIK_WORKSPACE
    if config.OPIK_URL:
        configure_kwargs["url"] = config.OPIK_URL

    if configure_kwargs:
        opik.configure(**configure_kwargs)

    set_trace_processors([OpikTracingProcessor(project_name=config.OPIK_PROJECT_NAME)])
    _OPIK_READY = True


def track_openai_client(client: openai.OpenAI) -> openai.OpenAI:
    ensure_opik_configured()
    return track_openai(client, project_name=config.OPIK_PROJECT_NAME)
