import sys
import threading
import time

import pyperclip

from .config import config
from .error_log import write_error


def _ensure_com_initialized():
    """Initialize COM MTA on the current thread if not already initialized.

    On non-Windows platforms this is a no-op.  On Windows, UIA operations
    require a COM apartment — calling this before any UIA call ensures one
    exists without double-initializing or changing an already-established
    apartment model.
    """
    if sys.platform != "win32":
        return
    try:
        import pythoncom
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
    except Exception:
        pass  # Already initialized or incompatible apartment model


class TextGrabber:
    """Grab and replace text in the foreground application using UIA or clipboard fallback."""

    def __init__(self):
        self._original_clipboard: str = ""
        self._clipboard_saved: bool = False
        self._foreground_control = None
        self._state_lock = threading.Lock()

    def capture_foreground(self):
        _ensure_com_initialized()
        try:
            import uiautomation as uia
            control = uia.GetFocusedControl()
            with self._state_lock:
                self._foreground_control = control
        except Exception:
            with self._state_lock:
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

    def focus_foreground(self) -> bool:
        """Attempt to restore focus to the captured foreground control."""
        with self._state_lock:
            control = self._foreground_control
        if control is None:
            return False
        _ensure_com_initialized()
        try:
            control.SetFocus()
            return True
        except Exception as e:
            write_error(e, "focus_foreground")
            return False

    def replace_text(self, new_text: str) -> bool:
        if not new_text:
            return False
        _ensure_com_initialized()
        self.focus_foreground()
        if self._replace_via_uia(new_text):
            return True
        return self._replace_via_clipboard(new_text)

    def _get_selected_via_uia(self) -> str:
        try:
            try:
                import uiautomation as uia
            except ImportError:
                return ""

            with self._state_lock:
                control = self._foreground_control
            if control is None:
                control = uia.GetFocusedControl()
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

            with self._state_lock:
                control = self._foreground_control
            if control is None:
                control = uia.GetFocusedControl()
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
                            rng.Select()
                            control.SendKeys(self._escape_sendkeys(new_text))
                            return True
                        else:
                            # No active selection; select all and replace
                            doc_range = tp.DocumentRange()
                            if doc_range:
                                doc_range.Select()
                                control.SendKeys(self._escape_sendkeys(new_text))
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
            content = pyperclip.paste()
            with self._state_lock:
                self._original_clipboard = content
            self._clipboard_saved = True
        except Exception as e:
            write_error(e, "_save_clipboard")
            with self._state_lock:
                self._original_clipboard = ""
            self._clipboard_saved = False

    def _restore_clipboard(self):
        if self._clipboard_saved:
            with self._state_lock:
                content = self._original_clipboard
            try:
                pyperclip.copy(content)
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
    def _escape_sendkeys(text: str) -> str:
        """Escape SendKeys special characters: {}()+-^%~"""
        result = []
        for ch in text:
            if ch == '{':
                result.append('{{}')
            elif ch == '}':
                result.append('{}}')
            elif ch in '+^%~()':
                result.append(f'{{{ch}}}')
            else:
                result.append(ch)
        return ''.join(result)

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
