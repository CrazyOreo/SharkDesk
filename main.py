import flet as ft
import socket
import threading
import json
import time
import struct
import base64
import datetime
from io import BytesIO
import queue

# Evita que o PyInstaller quebre ao tentar importar dependências opcionais
try: import mss; HAS_MSS = True
except ImportError: HAS_MSS = False

try: from PIL import Image; HAS_PIL = True
except ImportError: HAS_PIL = False

try: import pyautogui; pyautogui.FAILSAFE = False; HAS_PYAUTOGUI = True
except ImportError: HAS_PYAUTOGUI = False

# ─── PROTOCOLO BINÁRIO COMPARTILHADO ─────────────────────────────────────────
MAGIC = 0xDEADBEEF
TYPE_JSON = 0x01
TYPE_FRAME = 0x02
HEADER_SIZE = 9

def build_packet(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">IBI", MAGIC, msg_type, len(payload)) + payload

def build_json_packet(obj: dict) -> bytes:
    return build_packet(TYPE_JSON, json.dumps(obj).encode("utf-8"))

# ─── PALETA DE CORES SUPREME (DARK/CYBERPUNK) ─────────────────────────────────
C_BG = "#080A0F"          
C_SURFACE = "#10141F"     
C_PRIMARY = "#00E5FF"     
C_ACCENT = "#FF4081"      
C_TEXT = "#F1F5F9"        
C_DIM = "#64748B"         
C_GREEN = "#00E676"       
C_RED = "#FF1744"         

# Dicionário global de estado reiniciável
state = {
    "running": True,
    "connected": False,
    "conn": None,
    "sock": None,
    "addr": None,
    "session_start": 0,
    "screen_sharing": False,
    "send_lock": threading.Lock(),
}

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Instanciação global da imagem de monitoramento
remote_img = ft.Image(fit=ft.ImageFit.CONTAIN, expand=True)

# ─── PROVEDOR DE FRAME DO CLIENTE ────────────────────────────────────────────
class ScreenStreamer:
    def __init__(self, max_fps=8):
        self.queue = queue.Queue(maxsize=2)
        self.running = False
        self.thread = None
        self.delay = 1.0 / max_fps

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True, name="Streamer")
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
                    except Exception: pass
                time.sleep(self.delay)

    def stop(self):
        self.running = False

streamer = ScreenStreamer(max_fps=8)


# ─── TELA INTERNA: SERVER (ESPECIALISTA) ──────────────────────────────────────
def carregar_modo_server(page: ft.Page):
    global state
    page.clean()
    page.title = "SharkDesk — Painel do Especialista"
    page.window_width = 1150
    page.window_height = 800
    
    my_ip = get_local_ip()
    my_port = 55800
    connection_code = f"{my_ip.replace('.', '-')}_{my_port}"

    lbl_status_server = ft.Text("Servidor offline", color=C_DIM, size=13, weight=ft.FontWeight.W_500)
    lbl_client_info = ft.Text("Nenhum cliente conectado", color=C_DIM, size=14)
    lbl_session_time = ft.Text("Sessão: --:--:--", color=C_DIM, size=13, font_family="monospace")
    
    chat_box = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    txt_msg = ft.TextField(hint_text="Digite as orientações para o cliente...", shift_enter=True, color=C_TEXT, border_color=C_DIM, focused_border_color=C_PRIMARY, expand=True, border_radius=8, text_size=14)
    btn_send = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=C_PRIMARY, icon_size=24)
    
    btn_view_client = ft.ElevatedButton(content=ft.Row([ft.Icon(ft.icons.MONITOR_ROUNDED, size=18), ft.Text("VER TELA", weight=ft.FontWeight.BOLD)], spacing=8), bgcolor=C_PRIMARY, color=C_BG, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    btn_control_client = ft.ElevatedButton(content=ft.Row([ft.Icon(ft.icons.KEYBOARD_ALT_ROUNDED, size=18), ft.Text("CONTROLAR", weight=ft.FontWeight.BOLD)], spacing=8), bgcolor=C_ACCENT, color=C_TEXT, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    dlg_view_client = ft.AlertDialog(
        title=ft.Text("Monitoramento em Tempo Real", color=C_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(content=remote_img, width=960, height=540, alignment=ft.alignment.center, bgcolor=C_BG, border=ft.border.all(1, "#1E293B"), border_radius=12)
    )
    page.overlay.append(dlg_view_client)

    def append_chat(sender: str, message: str):
        is_client = (sender == "Cliente")
        chat_box.controls.append(ft.Container(content=ft.Column([ft.Text(sender.upper(), size=10, color=C_ACCENT if is_client else C_PRIMARY, weight=ft.FontWeight.BOLD), ft.Text(message, size=14, color=C_TEXT)], spacing=2), bgcolor="#161B26" if is_client else "#0F172A", padding=12, border_radius=8, border=ft.border.all(1, "#262F45" if is_client else "#1E293B")))
        try: page.update()
        except Exception: pass

    def safe_send(packet: bytes) -> bool:
        if not state["conn"]: return False
        with state["send_lock"]:
            try:
                state["conn"].sendall(packet)
                return True
            except Exception: return False

    def loop_recv(conn):
        while state["running"] and state["connected"]:
            try:
                header = conn.recv(HEADER_SIZE)
                if len(header) < HEADER_SIZE: break
                magic, msg_type, size = struct.unpack(">IBI", header)
                if magic != MAGIC: break
                payload = b""
                while len(payload) < size:
                    chunk = conn.recv(size - len(payload))
                    if not chunk: break
                    payload += chunk
                if len(payload) < size: break

                if msg_type == TYPE_JSON:
                    obj = json.loads(payload.decode("utf-8"))
                    if obj.get("type") == "chat": append_chat("Cliente", obj.get("msg", ""))
                elif msg_type == TYPE_FRAME:
                    if dlg_view_client.open:
                        remote_img.src_base64 = base64.b64encode(payload).decode("utf-8")
                        remote_img.update()
            except Exception: break

        state["connected"] = False
        state["conn"] = None
        btn_view_client.disabled = True
        btn_control_client.disabled = True
        lbl_client_info.value = "Nenhum cliente conectado"
        lbl_client_info.color = C_DIM
        if dlg_view_client.open: dlg_view_client.open = False
        append_chat("Sistema", "Conexão encerrada pelo cliente remetente.")
        try: page.update()
        except Exception: pass

    def server_listen():
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(("0.0.0.0", my_port))
            server_sock.listen(1)
            lbl_status_server.value = f"Online — Escutando na porta {my_port}"
            lbl_status_server.color = C_GREEN
            page.update()
        except Exception as e:
            lbl_status_server.value = f"Falha crítica: {e}"
            lbl_status_server.color = C_RED
            page.update()
            return

        while state["running"]:
            server_sock.settimeout(1.0)
            try: conn, addr = server_sock.accept()
            except socket.timeout: continue
            except Exception: break

            if state["connected"]:
                conn.close()
                continue

            state["conn"], state["addr"], state["connected"], state["session_start"] = conn, addr, True, time.time()
            lbl_client_info.value = f"Conectado à máquina de IP: {addr[0]}"
            lbl_client_info.color = C_PRIMARY
            btn_view_client.disabled = False
            btn_control_client.disabled = False
            try: page.update()
            except Exception: pass
            threading.Thread(target=loop_recv, args=(conn,), daemon=True).start()

    def send_msg(e):
        if not txt_msg.value.strip() or not state["connected"]: return
        if safe_send(build_json_packet({"type": "chat", "msg": txt_msg.value.strip()})):
            append_chat("Você (Suporte)", txt_msg.value.strip())
            txt_msg.value = ""
            page.update()

    btn_send.on_click = send_msg
    txt_msg.on_submit = send_msg
    btn_view_client.on_click = lambda e: (setattr(remote_img, 'src_base64', ""), setattr(dlg_view_client, 'open', True), page.update())

    # Estruturação visual
    top_bar = ft.Container(content=ft.Row([ft.Row([ft.Icon(ft.icons.MONITOR_HEART_ROUNDED, color=C_PRIMARY, size=32), ft.Column([ft.Text("SHARKDESK — CENTRAL", color=C_TEXT, size=18, weight=ft.FontWeight.W_900), lbl_status_server], spacing=0)]), ft.TextButton("VOLTAR AO MENU", icon=ft.icons.ARROW_BACK_ROUNDED, icon_color=C_ACCENT, on_click=lambda e: restaurar_menu(page))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), bgcolor=C_SURFACE, padding=20, border_radius=12, border=ft.border.all(1, "#1E293B"))
    code_panel = ft.Container(content=ft.Column([ft.Text("CÓDIGO DE CONEXÃO", color=C_PRIMARY, size=11, weight=ft.FontWeight.BOLD), ft.Row([ft.Text(connection_code, color=C_TEXT, size=18, weight=ft.FontWeight.BOLD, font_family="monospace"), ft.IconButton(ft.icons.COPY_ROUNDED, icon_color=C_DIM, icon_size=16, on_click=lambda e: page.set_clipboard(connection_code))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Text("Passe este código para o cliente.", color=C_DIM, size=12)], spacing=8), bgcolor="#0D1527", padding=16, border_radius=10, border=ft.border.all(1, "#00E5FF"))
    info_panel = ft.Container(content=ft.Column([code_panel, ft.Divider(color="#1E293B", height=20), ft.Text("SESSÃO ATUAL", color=C_DIM, size=11, weight=ft.FontWeight.BOLD), lbl_client_info, lbl_session_time, ft.Column([btn_view_client, btn_control_client], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)], spacing=16), bgcolor=C_SURFACE, padding=20, border_radius=12, width=320, border=ft.border.all(1, "#1E293B"))
    chat_panel = ft.Container(content=ft.Column([ft.Text("CONVERSA EM TEMPO REAL", color=C_DIM, size=11, weight=ft.FontWeight.BOLD), ft.Container(chat_box, bgcolor="#0A0D14", border=ft.border.all(1, "#1E293B"), border_radius=8, expand=True, padding=12), ft.Row([txt_msg, btn_send], spacing=8)], spacing=12), bgcolor=C_SURFACE, padding=20, border_radius=12, expand=True, border=ft.border.all(1, "#1E293B"))
    
    page.add(top_bar, ft.Row([info_panel, chat_panel], expand=True, spacing=16))

    def update_timer():
        while state["running"] and page.title == "SharkDesk — Painel do Especialista":
            if state["connected"] and state["session_start"] > 0:
                elapsed = int(time.time() - state["session_start"])
                lbl_session_time.value = f"Sessão: {datetime.timedelta(seconds=elapsed)}"
                lbl_session_time.color = C_PRIMARY
                try: page.update()
                except Exception: pass
            time.sleep(1)

    threading.Thread(target=server_listen, daemon=True).start()
    threading.Thread(target=update_timer, daemon=True).start()


# ─── TELA INTERNA: CLIENT (SUPORTE AO USUÁRIO) ────────────────────────────────
def carregar_modo_client(page: ft.Page):
    global state
    page.clean()
    page.title = "SharkDesk — Painel do Cliente"
    page.window_width = 880
    page.window_height = 680

    txt_code = ft.TextField(label="Código de Acesso do Técnico", hint_text="Ex: 192-168-1-15_55800", color=C_TEXT, border_color=C_DIM, focused_border_color=C_PRIMARY, expand=True, border_radius=8, text_size=14)
    btn_connect = ft.ElevatedButton(content=ft.Text("CONECTAR", weight=ft.FontWeight.BOLD, color=C_BG), bgcolor=C_PRIMARY, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    btn_disconnect = ft.ElevatedButton(text="DESCONECTAR", bgcolor=C_RED, color=C_TEXT, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    lbl_status = ft.Text("Dispositivo isolado", color=C_DIM, weight=ft.FontWeight.W_500, size=13)

    chat_box = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    txt_msg = ft.TextField(hint_text="Fale com o especialista...", shift_enter=True, color=C_TEXT, border_color=C_DIM, focused_border_color=C_PRIMARY, expand=True, border_radius=8, text_size=14)
    btn_send = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=C_PRIMARY)

    btn_share_txt = ft.Text("COMPARTILHAR TELA", color=C_DIM, size=11, weight=ft.FontWeight.BOLD)
    btn_share_screen = ft.Container(
        content=ft.Row([ft.Icon(ft.icons.SCREEN_SHARE_ROUNDED, size=20, color=C_TEXT), btn_share_txt], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor=C_SURFACE, border=ft.border.all(1, C_DIM), border_radius=8, padding=12, alignment=ft.alignment.center,
        on_click=lambda e: toggle_screen_share()
    )

    def append_chat(sender: str, message: str):
        is_me = (sender == "Você")
        chat_box.controls.append(ft.Container(content=ft.Column([ft.Text(sender.upper(), size=10, color=C_PRIMARY if is_me else C_ACCENT, weight=ft.FontWeight.BOLD), ft.Text(message, size=14, color=C_TEXT)], spacing=2), bgcolor="#0F172A" if is_me else "#161B26", padding=12, border_radius=8, border=ft.border.all(1, "#1E293B" if is_me else "#262F45")))
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
        while state["running"] and state["connected"]:
            try:
                header = state["sock"].recv(HEADER_SIZE)
                if len(header) < HEADER_SIZE: break
                magic, msg_type, size = struct.unpack(">IBI", header)
                if magic != MAGIC: break
                payload = b""
                while len(payload) < size:
                    chunk = state["sock"].recv(size - len(payload))
                    if not chunk: break
                    payload += chunk
                if len(payload) < size: break

                if msg_type == TYPE_JSON:
                    obj = json.loads(payload.decode("utf-8"))
                    if obj.get("type") == "chat": append_chat("Especialista", obj.get("msg", ""))
            except Exception: break
        
        state["connected"], state["screen_sharing"] = False, False
        lbl_status.value, lbl_status.color = "Dispositivo isolado", C_DIM
        btn_connect.disabled, btn_disconnect.disabled = False, True
        btn_share_screen.bgcolor, btn_share_txt.value, btn_share_txt.color = C_SURFACE, "COMPARTILHAR TELA", C_DIM
        append_chat("Sistema", "Conexão com a central interrompida.")
        try: page.update()
        except Exception: pass

    def loop_send_frames():
        while state["running"] and page.title == "SharkDesk — Painel do Cliente":
            if state["connected"] and state["screen_sharing"]:
                try:
                    frame_bytes = streamer.queue.get(timeout=0.2)
                    if not safe_send(build_packet(TYPE_FRAME, frame_bytes)): break
                except queue.Empty: continue
            else: time.sleep(0.1)

    def connect_click(e):
        raw_code = txt_code.value.strip()
        if "_" not in raw_code:
            append_chat("Sistema", "Código inválido. Formato esperado: XXX-XXX-X-X_XXXXX")
            return
        try:
            coded_ip, coded_port = raw_code.split("_")
            state["sock"] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            state["sock"].connect((coded_ip.replace("-", "."), int(coded_port)))
            state["sock"].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            state["connected"] = True
            btn_connect.disabled, btn_disconnect.disabled = True, False
            lbl_status.value, lbl_status.color = "Sessão de suporte ativa com a central", C_GREEN
            append_chat("Sistema", "Conexão segura estabelecida com sucesso.")
            threading.Thread(target=loop_recv, daemon=True).start()
            page.update()
        except Exception as err: append_chat("Sistema", f"Falha de conexão: {err}")

    def disconnect_click(e):
        state["connected"], state["screen_sharing"] = False, False
        btn_share_screen.bgcolor, btn_share_txt.value, btn_share_txt.color = C_SURFACE, "COMPARTILHAR TELA", C_DIM
        if state["sock"]:
            try: state["sock"].close()
            except Exception: pass
        btn_connect.disabled, btn_disconnect.disabled = False, True
        lbl_status.value, lbl_status.color = "Dispositivo isolado", C_DIM
        append_chat("Sistema", "Você encerrou a sessão.")
        page.update()

    def send_msg(e):
        if not txt_msg.value.strip() or not state["connected"]: return
        if safe_send(build_json_packet({"type": "chat", "msg": txt_msg.value.strip()})) :
            append_chat("Você", txt_msg.value.strip())
            txt_msg.value = ""
            page.update()

    def toggle_screen_share():
        if not state["connected"]: return
        state["screen_sharing"] = not state["screen_sharing"]
        if state["screen_sharing"]:
            btn_share_screen.bgcolor, btn_share_txt.value, btn_share_txt.color = C_GREEN, "COMPARTILHANDO VÍDEO", C_BG
        else:
            btn_share_screen.bgcolor, btn_share_txt.value, btn_share_txt.color = C_SURFACE, "COMPARTILHAR TELA", C_DIM
        page.update()

    btn_connect.on_click = connect_click
    btn_disconnect.on_click = disconnect_click
    btn_send.on_click = send_msg
    txt_msg.on_submit = send_msg

    top_bar = ft.Container(content=ft.Row([ft.Row([ft.Icon(ft.icons.SECURITY_ROUNDED, color=C_PRIMARY, size=28), ft.Column([ft.Text("SHARKDESK :: CLIENTE", color=C_TEXT, size=15, weight=ft.FontWeight.BOLD), lbl_status], spacing=0)]), ft.TextButton("VOLTAR AO MENU", icon=ft.icons.ARROW_BACK_ROUNDED, icon_color=C_ACCENT, on_click=lambda e: (disconnect_click(None), restaurar_menu(page)))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), bgcolor=C_SURFACE, padding=16, border_radius=12, border=ft.border.all(1, "#1E293B"))
    tools_panel = ft.Container(content=ft.Column([ft.Text("CONEXÃO", color=C_DIM, size=11, weight=ft.FontWeight.BOLD), ft.Row([txt_code]), ft.Column([btn_connect, btn_disconnect], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), ft.Divider(color="#1E293B", height=20), ft.Text("CONTROLES DE MÍDIA", color=C_DIM, size=11, weight=ft.FontWeight.BOLD), btn_share_screen], spacing=16), bgcolor=C_SURFACE, padding=20, border_radius=12, width=300, border=ft.border.all(1, "#1E293B"))
    chat_panel = ft.Container(content=ft.Column([ft.Text("CHAT DE SUPORTE", color=C_DIM, size=11, weight=ft.FontWeight.BOLD), ft.Container(chat_box, bgcolor="#0A0D14", border=ft.border.all(1, "#1E293B"), border_radius=8, expand=True, padding=12), ft.Row([txt_msg, btn_send], spacing=8)], spacing=12), bgcolor=C_SURFACE, padding=20, border_radius=12, expand=True, border=ft.border.all(1, "#1E293B"))

    page.add(top_bar, ft.Row([tools_panel, chat_panel], expand=True, spacing=16))
    streamer.start()
    threading.Thread(target=loop_send_frames, daemon=True).start()


# ─── MENU INICIAL (LAUNCHER) ──────────────────────────────────────────────────
def restaurar_menu(page: ft.Page):
    global state
    # Fecha conexões ativas ao voltar ao menu
    state["running"] = False
    state["connected"] = False
    streamer.stop()
    if state["conn"]: 
        try: state["conn"].close()
        except: pass
    if state["sock"]: 
        try: state["sock"].close()
        except: pass
    
    # Restaura o estado padrão de execução
    state["running"] = True
    state["conn"] = None
    state["sock"] = None

    page.clean()
    page.title = "SharkDesk — Inicializador Oficial"
    page.window_width = 620
    page.window_height = 480
    page.window_resizable = False

    header = ft.Container(
        content=ft.Column([
            ft.Icon(ft.icons.SHIELD_ROUNDED, color=C_PRIMARY, size=54),
            ft.Text("SHARKDESK", color=C_TEXT, size=28, weight=ft.FontWeight.W_900),
            ft.Text("Selecione o modo de operação desejado para iniciar", color=C_DIM, size=13)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        margin=ft.margin.only(bottom=20)
    )

    def criar_card_opcao(titulo, sub, icone, cor, callback):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icone, color=cor, size=32),
                ft.Column([
                    ft.Text(titulo, color=C_TEXT, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(sub, color=C_DIM, size=12, width=340)
                ], spacing=2)
            ], alignment=ft.MainAxisAlignment.START, spacing=16),
            bgcolor=C_SURFACE,
            padding=20,
            border_radius=12,
            border=ft.border.all(1, "#1E293B"),
            on_click=callback,
            animate=ft.animation.Animation(200, "easeOut")
        )

    btn_server = criar_card_opcao(
        "Modo Especialista (Server)",
        "Abra o painel de controle e gere códigos de acesso para monitorar máquinas remotas em tempo real.",
        ft.icons.SUPPORT_AGENT_ROUNDED, C_PRIMARY, lambda e: carregar_modo_server(page)
    )

    btn_client = criar_card_opcao(
        "Modo Usuário (Client)",
        "Insira o código fornecido pelo técnico para autorizar o compartilhamento seguro do seu terminal.",
        ft.icons.LAPTOP_ROUNDED, C_ACCENT, lambda e: carregar_modo_client(page)
    )

    # Efeito simples de Hover nos cards do Launcher
    def hover_effect(e, container):
        container.border = ft.border.all(1, C_PRIMARY if e.data == "true" else "#1E293B")
        container.update()

    btn_server.on_hover = lambda e: hover_effect(e, btn_server)
    btn_client.on_hover = lambda e: hover_effect(e, btn_client)

    page.add(
        ft.Container(
            content=ft.Column([
                header,
                ft.Column([btn_server, btn_client], spacing=14)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True
        )
    )
    page.update()

def main_app(page: ft.Page):
    page.background_color = C_BG
    page.padding = 24
    restaurar_menu(page)

    def on_app_disconnect(e):
        global state
        state["running"] = False
        streamer.stop()
        if state["conn"]: 
            try: state["conn"].close()
            except: pass
        if state["sock"]: 
            try: state["sock"].close()
            except: pass

    page.on_disconnect = on_app_disconnect

if __name__ == "__main__":
    ft.app(target=main_app)