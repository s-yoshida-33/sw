# selector.py - IMAGENICS US-41系セレクターのLAN制御（緊急表示中に弊社STBの入力へ強制切替）

import logging
import re
import socket
import threading
from pathlib import Path

# 緊急表示（view.py）は弊社STBの画面にしか出ないため、セレクターで他の入力（CATV・外部入力等）を
# 選んでいると映らない。ON中はセレクターを弊社STBの入力へ切り替え、OFFで元の入力へ戻す。
#
# 制御はセレクターのLAN端子へのTCPコマンド（IMAGENICS標準のマトリックススイッチャー用コマンド）:
#   "<入力>,1\r"  入力切替（OFFは "q,1\r"）。戻り値なし
#   "w\r"         現在の入力の問い合わせ。"004\r" のように3桁で返る（OFFは "000"）
#   "kl\r"/"ku\r" 前面ボタンのキーロック設定/解除。戻り値なし
# TCPはソケット接続中1:1制御のため、コマンドごとに接続して切断する。
# 応答は複数回に分かれて届くことがあるため、[CR]まで読む。

STATE_FILE = Path("C:/sw/state/selector_prev_input.txt")
TIMEOUT_SEC = 3.0
_REPLY_RE = re.compile(r"(\d{3})")


class SelectorController:
    def __init__(self, host, port, emergency_input, lock=True, reassert_sec=5.0, state_file=STATE_FILE):
        self.host = host
        self.port = port
        self.emergency_input = emergency_input
        self.lock = lock
        self.reassert_sec = reassert_sec
        self.state_file = Path(state_file)
        self._desired = None   # None=まだ信号を受けていない / True=緊急表示中 / False=通常
        self._applied = None   # セレクターに反映済みの状態（失敗時は反映済みにしない＝次の周期で再試行）
        self._last_error = None
        self._wake = threading.Event()
        self._stop = False
        # OFFで元の入力へ戻し終えたときに（このスレッドから）呼ぶ。view.pyはこれを待って画像を消す
        self.on_restored = None
        self._thread = threading.Thread(target=self._run, name="selector", daemon=True)

    def start(self):
        logging.info(f"Selector control enabled: {self.host}:{self.port}, emergency input={self.emergency_input}, lock={self.lock}")
        self._thread.start()

    def stop(self):
        self._stop = True
        self._wake.set()

    # MQTTの受信のたびに呼ぶ（KC868-A16は1秒ごとに状態をpublishする）。通信は専用スレッドで行い、
    # Tkinterのスレッドを止めない。
    def request(self, emergency):
        emergency = bool(emergency)
        if emergency != self._desired:
            self._desired = emergency
            self._wake.set()

    # OFFを受けたときに、元の入力へ戻す切替が残っているか。view.pyは、残っていれば
    # 切替が終わるまで緊急画像とミュートを続ける（先に画像を消すと、#4のSTBの映像・音声が一瞬出るため）
    def restore_pending(self):
        prev = self._load_prev()
        return prev is not None and prev != self.emergency_input

    # ---------- 通信 ----------
    def _exchange(self, cmd, expect_reply):
        with socket.create_connection((self.host, self.port), timeout=TIMEOUT_SEC) as s:
            s.settimeout(TIMEOUT_SEC)
            s.sendall(f"{cmd}\r".encode("ascii"))
            if not expect_reply:
                return None
            buf = b""
            while not buf.endswith(b"\r"):
                chunk = s.recv(64)
                if not chunk:
                    break
                buf += chunk
            return buf.decode("ascii", errors="replace").strip()

    def query_input(self):
        reply = self._exchange("w", True)
        m = _REPLY_RE.search(reply or "")
        if not m:
            raise OSError(f"unexpected reply to 'w': {reply!r}")
        return int(m.group(1))

    def select_input(self, n):
        self._exchange(f"{n if n else 'q'},1", False)

    def set_key_lock(self, locked):
        self._exchange("kl" if locked else "ku", False)

    # ---------- 元の入力の保存（緊急表示中にSTBが再起動しても戻せるようにファイルに残す） ----------
    def _load_prev(self):
        try:
            return int(self.state_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _save_prev(self, n):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(str(n), encoding="utf-8")

    # ---------- 制御ループ ----------
    def _run(self):
        while not self._stop:
            self._wake.wait(self.reassert_sec)
            self._wake.clear()
            desired = self._desired
            if desired is None:
                continue
            try:
                if desired:
                    self._apply_emergency()
                else:
                    self._apply_normal()
                if self._last_error:
                    logging.info("Selector communication recovered")
                    self._last_error = None
            except OSError as e:
                if str(e) != self._last_error:
                    logging.error(f"Selector error ({self.host}:{self.port}): {e}")
                    self._last_error = str(e)

    def _apply_emergency(self):
        current = self.query_input()
        # 2回目以降のON（緊急表示中のview.py再起動を含む）では、既に切替済みの入力で上書きしない
        if self._load_prev() is None:
            self._save_prev(current)
            logging.info(f"Selector: saved current input {current}")
        # ON中は毎周期確認し、ずれていれば切り替え直す（セレクターの電源再投入・手動操作への備え）
        if current != self.emergency_input:
            self.select_input(self.emergency_input)
            after = self.query_input()
            if after != self.emergency_input:
                raise OSError(f"switch to input {self.emergency_input} not applied (now {after})")
            logging.info(f"Selector: input {current} -> {self.emergency_input}")
            if self.lock:
                self.set_key_lock(True)
        elif self._applied is not True and self.lock:
            self.set_key_lock(True)
        self._applied = True

    def _apply_normal(self):
        prev = self._load_prev()
        if self._applied is False and prev is None:
            return
        if self.lock and (self._applied is True or prev is not None):
            self.set_key_lock(False)
        if prev is not None:
            current = self.query_input()
            # 緊急表示中に（ロックなしの設定で）手動で別の入力に替えられていた場合は、その選択を尊重する
            if current == self.emergency_input and prev != current:
                self.select_input(prev)
                logging.info(f"Selector: input {current} -> {prev} (restored)")
            try:
                self.state_file.unlink()
            except FileNotFoundError:
                pass
        self._applied = False
        if self.on_restored:
            self.on_restored()
