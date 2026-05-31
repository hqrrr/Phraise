import sys
import time

import pyperclip

from .config import config
from .error_log import write_error


class TextGrabber:
    """Grab and replace text in the foreground application using UIA or clipboard fallback."""

    def __init__(self):
        self._original_clipboard: str = ""
        self._foreground_control = None

    def capture_foreground(self):
        try:
            import uiautomation as uia
            self._foreground_control = uia.GetFocusedControl()
        except Exception:
            self._foreground_control = None

    def get_selected_text(self, use_clipboard: bool = True) -> str:
        text = self._get_selected_via_uia()
        if text:
            return text
        if use_clipboard:
            return self._get_selected_via_clipboard()
        return ""

    def get_foreground_process_name(self) -> str:
        try:
            import uiautomation as uia
            window = uia.GetForegroundControl()
            if window:
                name = getattr(window, 'ProcessName', '') or ''
                return name
        except Exception as e:
            write_error(e, "get_foreground_process_name")
            pass
        return ""

    def replace_text(self, new_text: str) -> bool:
        if self._replace_via_uia(new_text):
            return True
        return self._replace_via_clipboard(new_text)

    def _get_selected_via_uia(self) -> str:
        try:
            try:
                import uiautomation as uia
            except ImportError:
                return ""

            control = self._foreground_control or uia.GetFocusedControl()
            if control is None:
                return ""

            for _ in range(3):
                tp = None
                try:
                    tp = control.GetTextPattern()
                except AttributeError:
                    pass
                except Exception as e:
                    write_error(e, "_get_selected_via_uia:GetTextPattern")
                if tp is None:
                    pass
                else:
                    try:
                        selection = tp.GetSelection()
                        if selection:
                            texts = [r.GetText(-1) for r in selection if r]
                            combined = "\n".join(texts)
                            if combined.strip():
                                return combined
                        break
                    except Exception as e:
                        write_error(e, "_get_selected_via_uia:GetSelection")
                        break

                try:
                    parent = control.GetParentControl()
                    if parent:
                        control = parent
                    else:
                        break
                except Exception as e:
                    write_error(e, "_get_selected_via_uia:GetParentControl")
                    break

        except Exception as e:
            write_error(e, "_get_selected_via_uia")
            pass

        return ""

    def _get_selected_via_clipboard(self) -> str:
        try:
            self._save_clipboard()
            self._send_copy()
            time.sleep(0.2)
            text = pyperclip.paste()
            if not isinstance(text, str):
                text = ""
            self._restore_clipboard()
            return text if text else ""
        except Exception as e:
            write_error(e, "_get_selected_via_clipboard")
            self._restore_clipboard()
            return ""

    def _replace_via_uia(self, new_text: str) -> bool:
        try:
            try:
                import uiautomation as uia
            except ImportError:
                return False

            control = self._foreground_control or uia.GetFocusedControl()
            if control is None:
                return False

            for _ in range(3):
                try:
                    vp = control.GetValuePattern()
                    if vp:
                        vp.SetValue(new_text)
                        return True
                except AttributeError:
                    pass
                except Exception as e:
                    write_error(e, "_replace_via_uia:GetValuePattern")

                try:
                    tp = control.GetTextPattern()
                    if tp:
                        selection = tp.GetSelection()
                        if selection and selection[0]:
                            rng = selection[0]
                            rng.MoveEndpointByRange(
                                uia.TextPatternRangeEndpoint_End,
                                rng,
                                uia.TextPatternRangeEndpoint_Start,
                            )
                            rng.Select()
                            control.SendKeys(new_text)
                            return True
                except AttributeError:
                    pass
                except Exception as e:
                    write_error(e, "_replace_via_uia:GetTextPattern")

                try:
                    parent = control.GetParentControl()
                    if parent:
                        control = parent
                    else:
                        break
                except Exception as e:
                    write_error(e, "_replace_via_uia:GetParentControl")
                    break

        except Exception as e:
            write_error(e, "_replace_via_uia")
            pass

        return False

    def _replace_via_clipboard(self, new_text: str) -> bool:
        try:
            self._save_clipboard()
            pyperclip.copy(new_text)
            time.sleep(0.1)
            self._send_paste()
            time.sleep(0.1)
            self._restore_clipboard()
            return True
        except Exception as e:
            write_error(e, "_replace_via_clipboard")
            self._restore_clipboard()
            return False

    def _save_clipboard(self):
        try:
            self._original_clipboard = pyperclip.paste()
        except Exception as e:
            write_error(e, "_save_clipboard")
            self._original_clipboard = ""

    def _restore_clipboard(self):
        if self._original_clipboard:
            try:
                pyperclip.copy(self._original_clipboard)
            except Exception as e:
                write_error(e, "_restore_clipboard")
                pass

    def _send_copy(self):
        try:
            import uiautomation as uia
            uia.SendKeys('{Ctrl}c', waitTime=0.05)
        except Exception as e:
            write_error(e, "_send_copy:UIA")
            try:
                self._send_copy_via_ctypes()
            except Exception as e2:
                write_error(e2, "_send_copy:ctypes")
                pass

    def _send_paste(self):
        try:
            import uiautomation as uia
            uia.SendKeys('{Ctrl}v', waitTime=0.05)
        except Exception as e:
            write_error(e, "_send_paste:UIA")
            try:
                self._send_paste_via_ctypes()
            except Exception as e2:
                write_error(e2, "_send_paste:ctypes")
                pass

    @staticmethod
    def _send_copy_via_ctypes():
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_C = 0x43
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_C, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def _send_paste_via_ctypes():
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_V = 0x56
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
