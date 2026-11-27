"""Ошибки с кодами выхода."""

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_EMPTY_TEXT = 3
EXIT_NO_KEY = 4
EXIT_LLM_UNAVAILABLE = 5
EXIT_BUDGET = 6


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
    transient = False  # True: исчерпаны ретраи на лимиты/5xx (провайдер временно «лежит»)


class InputTooLargeError(InputFileError):
    """Документ превышает лимиты (размер, страницы, символы, число требований)."""


class BudgetExceededError(ReqcheckError):
    """Исчерпан бюджет прогона: число вызовов LLM, объём промптов или время."""

    exit_code = EXIT_BUDGET
