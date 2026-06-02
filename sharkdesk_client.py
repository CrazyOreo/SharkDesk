import flet as ft
import socket
import threading
import json
import time
import struct
from io import BytesIO
import queue

try: import mss; HAS_MSS = True
except ImportError: HAS_MSS = False

try: from PIL import Image; HAS_PIL = True
except ImportError: HAS_PIL = False

try: import pyautogui; pyautogui.FAILSAFE = False; HAS_PYAUTOGUI = True
except ImportError: HAS_PYAUTOGUI = False

MAGIC = 0xDEADBEEF
TYPE_JSON = 0x01
TYPE_FRAME = 0x02
HEADER_SIZE = 9

def build_packet(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">IBI", MAGIC, msg_type, len(payload)) + payload

def build_json_packet(obj: dict) -> bytes:
    return build_packet(TYPE_JSON, json.dumps(obj).encode("utf-8"))

# Paleta de Cores Coerente com o Servidor
C_BG = "#080A0F"
C_SURFACE = "#10141F"
C_PRIMARY = "#00E5FF"
C_ACCENT = "#FF4081"
C_TEXT = "#F1F5F9"
C_DIM = "#64748B"
C_GREEN = "#00E676"
C_RED = "#FF1744"

# DICIONÁRIO DE ESTADO GLOBAL
state = {
    "running": True,
    "connected": False,
    "sock": None,
    "screen_sharing": False,
    "send_lock": threading.Lock(),
}

class ScreenStreamer:
    def __init__(self, max_fps=8):
        self.queue = queue.Queue(maxsize=2)
        self.running = False
        self.thread = None
        self.delay = 1.0 / max_fps

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True, name="ClientStreamer")
            self.thread.start()

    def _run(self):
        global state
        if not (HAS_MSS and HAS_PIL): return
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            while self.running:
                if state["screen_sharing"] and state["connected"]:
                    try:
                        sct_img = sct.grab(monitor)
                        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                        img.thumbnail((960, 540))
                        out = BytesIO()
                        img.save(out, format="JPEG", quality=60)
                        img_bytes = out.getvalue()

                        while not self.queue.empty():
                            try: self.queue.get_nowait()
                            except queue.Empty: break

                        if not self.queue.full():
                            self.queue.put_nowait(img_bytes)
                    except Exception as e:
                        print(f"[Streamer] Erro: {e}")
                time.sleep(self.delay)

    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=1)

streamer = ScreenStreamer(max_fps=8)

def main(page: ft.Page):
    global state
    page.title = "SharkDesk — Painel do Cliente"
    page.background_color = C_BG
    page.padding = 24
    page.window_width = 880
    page.window_height = 680
    page.window_resizable = True

    txt_code = ft.TextField(
        label="Código de Acesso do Técnico", 
        value="", 
        hint_text="Ex: 192-168-1-15_55800",
        color=C_TEXT, 
        border_color=C_DIM, 
        focused_border_color=C_PRIMARY, 
        expand=True,
        border_radius=8,
        text_size=14
    )
    
    btn_connect = ft.ElevatedButton(
        content=ft.Text("CONECTAR", weight=ft.FontWeight.BOLD, color=C_BG), 
        bgcolor=C_PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    btn_disconnect = ft.ElevatedButton(
        text="DESCONECTAR", bgcolor=C_RED, color=C_TEXT, disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    lbl_status = ft.Text("Dispositivo isolado", color=C_DIM, weight=ft.FontWeight.W_500, size=13)

    chat_box = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    txt_msg = ft.TextField(hint_text="Fale com o especialista...", shift_enter=True, color=C_TEXT, border_color=C_DIM, focused_border_color=C_PRIMARY, expand=True, border_radius=8, text_size=14)
    btn_send = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=C_PRIMARY)

    btn_share_txt = ft.Text("COMPARTILHAR TELA", color=C_DIM, size=11, weight=ft.FontWeight.BOLD)
    btn_share_screen = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SCREEN_SHARE_ROUNDED, size=20, color=C_TEXT),
            btn_share_txt
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor=C_SURFACE, border=ft.border.all(1, C_DIM), border_radius=8,
        padding=12, alignment=ft.alignment.center, on_click=lambda e: toggle_screen_share(e)
    )

    def append_chat(sender: str, message: str):
        is_me = (sender == "Você")
        chat_box.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text(sender.upper(), size=10, color=C_PRIMARY if is_me else C_ACCENT, weight=ft.FontWeight.BOLD),
                    ft.Text(message, size=14, color=C_TEXT)
                ], spacing=2),
                bgcolor="#0F172A" if is_me else "#161B26",
                padding=12,
                border_radius=8,
                border=ft.border.all(1, "#1E293B" if is_me else "#262F45")
            )
        )
        try: page.update()
        except Exception: pass

    def safe_send(packet: bytes) -> bool:
        if not state["sock"]: return False
        with state["send_lock"]:
            try:
                state["sock"].sendall(packet)
                return True
            except Exception: return False

    def loop_recv():
        global state
        sock = state["sock"]
        while state["running"] and state["connected"]:
            try:
                header = sock.recv(HEADER_SIZE)
                if len(header) < HEADER_SIZE: break
                magic, msg_type, size = struct.unpack(">IBI", header)
                if magic != MAGIC: break

                payload = b""
                while len(payload) < size:
                    chunk = sock.recv(size - len(payload))
                    if not chunk: break
                    payload += chunk
                if len(payload) < size: break

                if msg_type == TYPE_JSON:
                    obj = json.loads(payload.decode("utf-8"))
                    if obj.get("type") == "chat":
                        append_chat("Especialista", obj.get("msg", ""))
            except Exception:
                break
        
        state["connected"] = False
        state["screen_sharing"] = False
        lbl_status.value = "Dispositivo isolado"
        lbl_status.color = C_DIM
        btn_connect.disabled = False
        btn_disconnect.disabled = True
        btn_share_screen.bgcolor = C_SURFACE
        btn_share_txt.value = "COMPARTILHAR TELA"
        btn_share_txt.color = C_DIM
        append_chat("Sistema", "Conexão com a central interrompida.")

    def loop_send_frames():
        global state
        while state["running"]:
            if state["connected"] and state["screen_sharing"]:
                try:
                    frame_bytes = streamer.queue.get(timeout=0.2)
                    packet = build_packet(TYPE_FRAME, frame_bytes)
                    if not safe_send(packet): break
                except queue.Empty: continue
            else: time.sleep(0.1)

    def connect_click(e):
        global state
        if state["connected"]: return
        raw_code = txt_code.value.strip()
        if "_" not in raw_code:
            append_chat("Sistema", "Código inválido. Formato esperado: XXX-XXX-X-X_XXXXX")
            return
        
        try:
            coded_ip, coded_port = raw_code.split("_")
            ip = coded_ip.replace("-", ".")
            port = int(coded_port)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            state["sock"] = sock
            state["connected"] = True
            btn_connect.disabled = True
            btn_disconnect.disabled = False
            lbl_status.value = f"Sessão de suporte ativa com a central"
            lbl_status.color = C_GREEN
            
            append_chat("Sistema", "Conexão segura estabelecida com sucesso.")
            threading.Thread(target=loop_recv, daemon=True).start()
            page.update()
        except Exception as err:
            append_chat("Sistema", f"Falha de conexão direta: {err}")

    def disconnect_click(e):
        global state
        state["connected"] = False
        state["screen_sharing"] = False
        btn_share_screen.bgcolor = C_SURFACE
        btn_share_txt.value = "COMPARTILHAR TELA"
        btn_share_txt.color = C_DIM
        if state["sock"]:
            try: state["sock"].close()
            except Exception: pass
        btn_connect.disabled = False
        btn_disconnect.disabled = True
        lbl_status.value = "Dispositivo isolado"
        lbl_status.color = C_DIM
        append_chat("Sistema", "Você encerrou a sessão.")
        page.update()

    def send_msg(e):
        global state
        if not txt_msg.value.strip() or not state["connected"]: return
        payload = {"type": "chat", "msg": txt_msg.value.strip()}
        if safe_send(build_json_packet(payload)):
            append_chat("Você", txt_msg.value.strip())
            txt_msg.value = ""
            page.update()

    def toggle_screen_share(e):
        global state
        if not state["connected"]: return
        state["screen_sharing"] = not state["screen_sharing"]
        if state["screen_sharing"]:
            btn_share_screen.bgcolor = C_GREEN
            btn_share_txt.value = "COMPARTILHANDO VÍDEO"
            btn_share_txt.color = C_BG
        else:
            btn_share_screen.bgcolor = C_SURFACE
            btn_share_txt.value = "COMPARTILHAR TELA"
            btn_share_txt.color = C_DIM
        page.update()

    btn_connect.on_click = connect_click
    btn_disconnect.on_click = disconnect_click
    btn_send.on_click = send_msg
    txt_msg.on_submit = send_msg

    top_bar = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SECURITY_ROUNDED, color=C_PRIMARY, size=28),
            ft.Column([
                ft.Text("SHARKDESK :: SUPORTE AO USUÁRIO", color=C_TEXT, size=15, weight=ft.FontWeight.BOLD),
                lbl_status
            ], spacing=0)
        ]),
        bgcolor=C_SURFACE, padding=16, border_radius=12, border=ft.border.all(1, "#1E293B")
    )

    tools_panel = ft.Container(
        content=ft.Column([
            ft.Text("CONEXÃO", color=C_DIM, size=11, weight=ft.FontWeight.BOLD),
            ft.Row([txt_code]),
            ft.Column([btn_connect, btn_disconnect], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            ft.Divider(color="#1E293B", height=20),
            ft.Text("CONTROLES DE MÍDIA", color=C_DIM, size=11, weight=ft.FontWeight.BOLD),
            btn_share_screen
        ], spacing=16),
        bgcolor=C_SURFACE, padding=20, border_radius=12, width=300, border=ft.border.all(1, "#1E293B")
    )

    chat_panel = ft.Container(
        content=ft.Column([
            ft.Text("CHAT DE SUPORTE", color=C_DIM, size=11, weight=ft.FontWeight.BOLD),
            ft.Container(chat_box, bgcolor="#0A0D14", border=ft.border.all(1, "#1E293B"), border_radius=8, expand=True, padding=12),
            ft.Row([txt_msg, btn_send], spacing=8)
        ], spacing=12),
        bgcolor=C_SURFACE, padding=20, border_radius=12, expand=True, border=ft.border.all(1, "#1E293B")
    )

    page.add(top_bar, ft.Row([tools_panel, chat_panel], expand=True, spacing=16))
    
    streamer.start()
    threading.Thread(target=loop_send_frames, daemon=True, name="ClientFrameSender").start()

    def on_disconnect(e):
        global state
        state["running"] = False
        streamer.stop()
        if state["sock"]:
            try: state["sock"].close()
            except Exception: pass

    page.on_disconnect = on_disconnect

if __name__ == "__main__":
    ft.app(target=main)