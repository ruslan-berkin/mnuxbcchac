"""Ошибки с кодами выхода (CLAUDE.md §7)."""

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_EMPTY_TEXT = 3
EXIT_NO_KEY = 4
EXIT_LLM_UNAVAILABLE = 5


class ReqcheckError(Exception):
    exit_code = 1


class InputFileError(ReqcheckError):
    """Файл не найден или формат не поддерживается."""

    exit_code = EXIT_BAD_INPUT


class EmptyDocumentError(ReqcheckError):
    """В документе нет текста (например, скан без текстового слоя)."""

    exit_code = EXIT_EMPTY_TEXT


class MissingKeyError(ReqcheckError):
    """Нет ключа LLM при --require-llm."""

    exit_code = EXIT_NO_KEY


class LLMUnavailableError(ReqcheckError):
    """LLM недоступна после ретраев."""

    exit_code = EXIT_LLM_UNAVAILABLE
