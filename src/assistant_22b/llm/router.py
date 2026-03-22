"""LLMRouter — routes generation to local (llama-cpp) or external (CloudLLMRuntime)."""
from __future__ import annotations


def _import_cloud_runtime():
    from gongmun_doctor.llm.cloud_runtime import CloudLLMRuntime  # noqa: PLC0415
    return CloudLLMRuntime


# Resolved lazily so monkeypatching works in tests
CloudLLMRuntime = None  # type: ignore[assignment]
try:
    CloudLLMRuntime = _import_cloud_runtime()  # type: ignore[assignment]
except ImportError:
    pass


class LLMRouter:
    """
    Modes:
    - "none"     : rules-only, always returns "" (default, BMVP admin agent path)
    - "external" : delegates to P1's CloudLLMRuntime
    - "local"    : delegates to llama-cpp-python (optional dependency)
    """

    def __init__(
        self,
        mode: str = "none",
        model_path: str = "",
        provider: str = "claude",
    ) -> None:
        self._mode = mode
        self._model_path = model_path
        self._provider = provider
        self._cloud_runtime = None
        self._local_model = None

    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> str:
        if self._mode == "external":
            return self._generate_external(prompt, max_tokens, temperature)
        if self._mode == "local":
            return self._generate_local(prompt, max_tokens, temperature)
        return ""  # "none" or unknown

    # ------------------------------------------------------------------
    def _generate_external(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            Runtime = CloudLLMRuntime  # module-level, patchable
            if Runtime is None:
                Runtime = _import_cloud_runtime()
            if self._cloud_runtime is None:
                self._cloud_runtime = Runtime(provider=self._provider)
            return self._cloud_runtime.generate(
                prompt, max_tokens=max_tokens, temperature=temperature
            )
        except Exception:
            return ""

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            if self._local_model is None:
                from llama_cpp import Llama  # noqa: PLC0415
                self._local_model = Llama(
                    model_path=self._model_path, n_ctx=4096, verbose=False
                )
            output = self._local_model(
                prompt, max_tokens=max_tokens, temperature=temperature
            )
            return output["choices"][0]["text"]
        except Exception:
            return ""
