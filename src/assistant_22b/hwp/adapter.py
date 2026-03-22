"""HwpAdapter — thin wrapper around P1's HwpController and HwpCorrectionBridge."""
from __future__ import annotations


# Module-level lazy importers — replaced by monkeypatching in tests
def _hwp_controller_class():
    from gongmun_doctor.hwp_com.controller import HwpController  # noqa: PLC0415
    return HwpController


def _hwp_bridge_class():
    from gongmun_doctor.hwp_com.bridge import HwpCorrectionBridge  # noqa: PLC0415
    return HwpCorrectionBridge


def _load_rules_fn():
    from gongmun_doctor.rules.loader import load_rules  # noqa: PLC0415
    return load_rules


class HwpAdapter:
    """
    Wraps P1's HwpController + HwpCorrectionBridge.

    Usage:
        adapter = HwpAdapter()
        if adapter.is_available() and adapter.connect():
            result = adapter.run_correction("track_changes")
    """

    def __init__(self) -> None:
        self._controller = None
        self._bridge = None

    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Returns True if gongmun_doctor.hwp_com is importable (pywin32 installed)."""
        try:
            _hwp_controller_class()
            return True
        except (ImportError, Exception):
            return False

    def connect(self) -> bool:
        """Connect to running Hanword via COM. Returns False on any failure."""
        try:
            CtrlClass = _hwp_controller_class()
            BridgeClass = _hwp_bridge_class()
            load_rules = _load_rules_fn()

            ctrl = CtrlClass()
            ctrl.connect()
            rules = load_rules()
            self._controller = ctrl
            self._bridge = BridgeClass(controller=ctrl, rules=rules)
            return True
        except Exception:
            return False

    def run_correction(self, mode: str = "track_changes") -> dict:
        """
        Run correction on currently open HWP document.

        Args:
            mode: "track_changes" | "direct" | "report_only"

        Returns:
            {"success": True, "result": ...} or {"success": False, "error": "..."}
        """
        if self._bridge is None:
            return {"success": False, "error": "Not connected — call connect() first"}
        try:
            result = self._bridge.run_correction(mode)
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def disconnect(self) -> None:
        """Release COM references."""
        self._bridge = None
        self._controller = None
