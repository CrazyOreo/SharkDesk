import flet as ft
import socket
import threading
import json
import time
import struct
import base64
import datetime

# Protocolo Binário
MAGIC = 0xDEADBEEF
TYPE_JSON = 0x01
TYPE_FRAME = 0x02
HEADER_SIZE = 9

def build_packet(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">IBI", MAGIC, msg_type, len(payload)) + payload

def build_json_packet(obj: dict) -> bytes:
    return build_packet(TYPE_JSON, json.dumps(obj).encode("utf-8"))

# Paleta de Cores Premium (Cyberpunk/Dark Mode)
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
    "conn": None,
    "addr": None,
    "session_start": 0,
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

remote_img = ft.Image(
    fit=ft.ImageFit.CONTAIN,
    expand=True
)

def main(page: ft.Page):
    global state
    page.title = "SharkDesk — Painel do Especialista"
    page.background_color = C_BG
    page.padding = 24
    page.window_width = 1150
    page.window_height = 800
    page.window_resizable = True

    my_ip = get_local_ip()
    my_port = 55800
    connection_code = f"{my_ip.replace('.', '-')}_{my_port}"

    # UI Components Estilizados
    lbl_status_server = ft.Text("Servidor offline", color=C_DIM, size=13, weight=ft.FontWeight.W_500)
    lbl_client_info = ft.Text("Nenhum cliente conectado", color=C_DIM, size=14)
    lbl_session_time = ft.Text("Sessão: --:--:--", color=C_DIM, size=13, font_family="monospace")
    
    chat_box = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    txt_msg = ft.TextField(
        hint_text="Digite as orientações para o cliente...", 
        shift_enter=True, 
        color=C_TEXT, 
        border_color=C_DIM,
        focused_border_color=C_PRIMARY,
        cursor_color=C_PRIMARY,
        expand=True,
        border_radius=8,
        text_size=14
    )
    btn_send = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=C_PRIMARY, icon_size=24, tooltip="Enviar Mensagem")
    
    btn_view_client = ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.icons.MONITOR_ROUNDED, size=18), ft.Text("VER TELA", weight=ft.FontWeight.BOLD)], spacing=8),
        bgcolor=C_PRIMARY,
        color=C_BG,
        disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    
    btn_control_client = ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.icons.KEYBOARD_ALT_ROUNDED, size=18), ft.Text("CONTROLAR", weight=ft.FontWeight.BOLD)], spacing=8),
        bgcolor=C_ACCENT,
        color=C_TEXT,
        disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    dlg_view_client = ft.AlertDialog(
        title=ft.Text("Monitoramento em Tempo Real", color=C_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=remote_img,
            width=960,
            height=540,
            alignment=ft.alignment.center,
            bgcolor=C_BG,
            border=ft.border.all(1, "#1E293B"),
            border_radius=12
        ),
        on_dismiss=lambda e: print("[Servidor] Fechou visualização.")
    )
    page.overlay.append(dlg_view_client)

    def append_chat(sender: str, message: str):
        is_client = (sender == "Cliente")
        chat_box.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text(sender.upper(), size=10, color=C_ACCENT if is_client else C_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Text(message, size=14, color=C_TEXT)
                ], spacing=2),
                bgcolor="#161B26" if is_client else "#0F172A",
                padding=12,
                border_radius=8,
                border=ft.border.all(1, "#262F45" if is_client else "#1E293B")
            )
        )
        try: page.update()
        except Exception: pass

    def safe_send(packet: bytes) -> bool:
        if not state["conn"]: return False
        with state["send_lock"]:
            try:
                state["conn"].sendall(packet)
                return True
            except Exception: return False

    def _handle_client_frame(frame_bytes: bytes):
        try:
            if dlg_view_client.open:
                remote_img.src_base64 = base64.b64encode(frame_bytes).decode("utf-8")
                remote_img.update()
        except Exception as e:
            print(f"[Servidor] Erro render: {e}")

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
                    if obj.get("type") == "chat":
                        append_chat("Cliente", obj.get("msg", ""))
                elif msg_type == TYPE_FRAME:
                    _handle_client_frame(payload)
            except Exception:
                break

        state["connected"] = False
        state["conn"] = None
        btn_view_client.disabled = True
        btn_control_client.disabled = True
        lbl_client_info.value = "Nenhum cliente conectado"
        lbl_client_info.color = C_DIM
        try:
            if dlg_view_client.open:
                dlg_view_client.open = False
            page.update()
        except Exception: pass
        append_chat("Sistema", "Conexão encerrada pelo cliente remetente.")

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
            try:
                conn, addr = server_sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            if state["connected"]:
                conn.close()
                continue

            state["conn"] = conn
            state["addr"] = addr
            state["connected"] = True
            state["session_start"] = time.time()

            lbl_client_info.value = f"Conectado à máquina de IP: {addr[0]}"
            lbl_client_info.color = C_PRIMARY
            btn_view_client.disabled = False
            btn_control_client.disabled = False
            try: page.update()
            except Exception: pass

            threading.Thread(target=loop_recv, args=(conn,), daemon=True, name="ServerRecv").start()

    def send_msg(e):
        if not txt_msg.value.strip() or not state["connected"]: return
        payload = {"type": "chat", "msg": txt_msg.value.strip()}
        if safe_send(build_json_packet(payload)):
            append_chat("Você (Suporte)", txt_msg.value.strip())
            txt_msg.value = ""
            page.update()

    def show_client_screen_click(e):
        if not state["connected"]: return
        remote_img.src_base64 = ""
        dlg_view_client.open = True
        page.update()

    btn_send.on_click = send_msg
    txt_msg.on_submit = send_msg
    btn_view_client.on_click = show_client_screen_click

    top_bar = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.MONITOR_HEART_ROUNDED, color=C_PRIMARY, size=32),
                ft.Column([
                    ft.Text("SHARKDESK", color=C_TEXT, size=18, weight=ft.FontWeight.W_900),
                    lbl_status_server
                ], spacing=0)
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=C_SURFACE, padding=20, border_radius=12, border=ft.border.all(1, "#1E293B")
    )

    code_panel = ft.Container(
        content=ft.Column([
            ft.Text("CÓDIGO DE CONEXÃO", color=C_PRIMARY, size=11, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Text(connection_code, color=C_TEXT, size=18, weight=ft.FontWeight.BOLD, font_family="monospace"),
                ft.IconButton(ft.icons.COPY_ROUNDED, icon_color=C_DIM, icon_size=16, on_click=lambda e: page.set_clipboard(connection_code))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("Passe este código para o cliente inserir no aplicativo de suporte.", color=C_DIM, size=12)
        ], spacing=8),
        bgcolor="#0D1527", padding=16, border_radius=10, border=ft.border.all(1, "#00E5FF")
    )

    info_panel = ft.Container(
        content=ft.Column([
            code_panel,
            ft.Divider(color="#1E293B", height=20),
            ft.Text("SESSÃO ATUAL", color=C_DIM, size=11, weight=ft.FontWeight.BOLD),
            lbl_client_info,
            lbl_session_time,
            ft.Column([
                btn_view_client,
                btn_control_client
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        ], spacing=16),
        bgcolor=C_SURFACE, padding=20, border_radius=12, width=320, border=ft.border.all(1, "#1E293B")
    )

    chat_panel = ft.Container(
        content=ft.Column([
            ft.Text("CONVERSA EM TEMPO REAL", color=C_DIM, size=11, weight=ft.FontWeight.BOLD),
            ft.Container(chat_box, bgcolor="#0A0D14", border=ft.border.all(1, "#1E293B"), border_radius=8, expand=True, padding=12),
            ft.Row([txt_msg, btn_send], spacing=8)
        ], spacing=12),
        bgcolor=C_SURFACE, padding=20, border_radius=12, expand=True, border=ft.border.all(1, "#1E293B")
    )

    page.add(
        top_bar,
        ft.Row([info_panel, chat_panel], expand=True, spacing=16)
    )

    def update_timer():
        while state["running"]:
            if state["connected"] and state["session_start"] > 0:
                elapsed = int(time.time() - state["session_start"])
                lbl_session_time.value = f"Sessão: {datetime.timedelta(seconds=elapsed)}"
                lbl_session_time.color = C_PRIMARY
                try: page.update()
                except Exception: pass
            time.sleep(1)

    threading.Thread(target=server_listen, daemon=True, name="ServerListener").start()
    threading.Thread(target=update_timer, daemon=True, name="ServerTimer").start()

    def on_disconnect_server(e):
        global state
        state["running"] = False
        if state["conn"]:
            try: state["conn"].close()
            except Exception: pass

    page.on_disconnect = on_disconnect_server

if __name__ == "__main__":
    ft.app(target=main)