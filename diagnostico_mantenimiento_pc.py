"""
Diagnóstico y mantenimiento del PC - interfaz gráfica (CustomTkinter).
Se puede lanzar manualmente o dejar configurado para arrancar con Windows.

La lógica (diagnóstico, limpieza, procesos, gestión de inicio, herramientas
avanzadas) vive en utils.py; este archivo solo construye la ventana con
pestañas y reacciona a los clics.

OBJETIVOS DEL PROGRAMA
----------------------
  1) Panel: diagnóstico general del equipo (CPU, RAM, disco, temperatura,
     internet), con tarjetas de color (verde/ámbar/rojo).
  2) Optimizador: limpieza de archivos temporales y caché del sistema
     (TEMP, papelera, DNS).
  3) Duplicados: buscar archivos duplicados y enviarlos a la papelera.
  4) Procesos: ver qué consume más recursos en segundo plano y poder
     finalizar procesos concretos, con protección para los críticos.
  5) Gestión de inicio: activar/desactivar accesos directos de la carpeta
     de Inicio de Windows (reversible, sin tocar el registro).
  6) Herramientas avanzadas: analizador de espacio en disco, verificación
     de archivos de sistema (SFC) y reinicio de la configuración TCP/IP -
     siempre manuales, con confirmación previa.
  7) Historial: acciones de limpieza realizadas en esta sesión.
  8) Software: lista de programas instalados y desinstalación directa
     (ejecuta el comando de desinstalación del propio programa).

Todo el informe de limpieza se guarda con fecha/hora en:
  %USERPROFILE%\\diagnostico_pc.log

PERMISOS NECESARIOS PARA EJECUTARLO
------------------------------------
  - Se puede ejecutar como usuario normal (doble clic o
    `python diagnostico_mantenimiento_pc.py`).
  - Como usuario normal ya funciona: limpiar el TEMP del usuario, vaciar la
    papelera, limpiar la caché DNS, finalizar procesos propios del usuario,
    gestionar los accesos directos de Inicio del usuario actual y analizar
    espacio en disco.
  - Para poder borrar también C:\\Windows\\Temp, finalizar procesos de otros
    usuarios/servicios, leer las entradas de inicio de HKLM, o usar SFC y el
    reinicio de red, hace falta ejecutarlo "Como administrador" (clic derecho
    sobre el .py o sobre un acceso directo que lo lance -> "Ejecutar como
    administrador").
  - Si no se ejecuta como administrador, el programa omite esas partes sin
    fallar (no hace falta relanzarlo si no se necesitan).

SEGURIDAD Y PRECAUCIONES
-------------------------
  - El programa NUNCA borra archivos fuera de las carpetas temporales
    (%TEMP% del usuario y C:\\Windows\\Temp) ni toca documentos o fotos. El
    analizador de espacio en disco es de solo lectura: nunca borra nada,
    solo muestra qué carpetas ocupan más.
  - Excepción: la pestaña "Software" SÍ puede desinstalar un programa
    instalado, a petición explícita del usuario (botón "Desinstalar
    programa seleccionado"). Ejecuta el UninstallString que el propio
    programa registró en Windows, el mismo comando que usaría el panel
    "Programas y características".
  - Antes de finalizar un proceso se comprueba su nombre contra una lista de
    procesos protegidos (System, csrss.exe, wininit.exe, services.exe,
    lsass.exe, winlogon.exe, explorer.exe, este mismo script...). Si está
    protegido, el botón de finalizar lo rechaza y avisa por qué.
  - La "gestión de inicio" de esta app solo mueve accesos directos entre la
    carpeta de Inicio y una subcarpeta "Deshabilitados": no borra nada y es
    reversible con un clic. Las entradas de inicio que viven en el registro
    de Windows se muestran solo como información (no se modifican desde
    aquí), porque editar el registro es una operación de más riesgo.
  - Por el mismo motivo, este programa NO limpia el registro de Windows ni
    vacía la "standby list" de memoria con APIs no documentadas.
  - SFC (verificación de archivos de sistema) y el reinicio de la
    configuración TCP/IP SÍ están disponibles, pero solo como botones
    manuales en "Herramientas avanzadas", con una confirmación explícita
    antes de ejecutarlos: son operaciones legítimas de Windows, pero pueden
    tardar minutos (SFC) o requerir reiniciar el equipo (reset de red), así
    que no tiene sentido lanzarlas solas en cada arranque.
  - Desinstalar programas NO se hace desde aquí: el botón correspondiente
    solo abre el panel nativo "Aplicaciones instaladas" de Windows, que ya
    tiene su propia confirmación y es más seguro que un desinstalador propio.
  - Finalizar procesos que no reconozcas puede cerrar programas con trabajo
    sin guardar: revisa el nombre antes de finalizar uno.
  - Vaciar la papelera de reciclaje es irreversible: lo que hay en ella se
    borra de verdad.
"""

import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

import utils


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_ESTADO = {
    "ok": "#2fa84f",
    "warn": "#d9a441",
    "bad": "#c0392b",
}

COLOR_ACENTO = "#2563eb"
COLOR_SIDEBAR = "#151a23"
COLOR_SIDEBAR_HOVER = "#1f2733"

SECCIONES = [
    ("dashboard", "dashboard.png", "Panel"),
    ("optimizador", "broom.png", "Optimizador"),
    ("duplicados", "duplicados.png", "Duplicados"),
    ("procesos", "procesos.png", "Procesos"),
    ("inicio", "inicio.png", "Gestión de inicio"),
    ("avanzado", "avanzado.png", "Herramientas avanzadas"),
    ("historial", "clock.png", "Historial"),
    ("software", "software.png", "Software"),
]

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _icono(nombre, size=(18, 18)):
    """Carga un icono de icons/ como CTkImage, o None si falta o está corrupto."""
    ruta = os.path.join(ICONS_DIR, nombre)
    if not os.path.isfile(ruta):
        return None
    try:
        imagen = Image.open(ruta)
        imagen.load()
    except Exception:
        return None
    return ctk.CTkImage(light_image=imagen, dark_image=imagen, size=size)


def _fila_con_icono(master, nombre_icono, texto, **label_kwargs):
    """Crea una fila con un icono a la izquierda de un CTkLabel en negrita."""
    fila = ctk.CTkFrame(master, fg_color="transparent")
    icono = _icono(nombre_icono)
    if icono is not None:
        ctk.CTkLabel(fila, image=icono, text="").pack(side="left", padx=(0, 6))
    ctk.CTkLabel(fila, text=texto, font=ctk.CTkFont(weight="bold"), **label_kwargs).pack(side="left")
    return fila


class TarjetaMetrica(ctk.CTkFrame):
    """Tarjeta moderna para una métrica: fondo oscuro, valor grande en color
    según estado (verde/ámbar/rojo) y barra de progreso fina del mismo color."""

    def __init__(self, master, titulo):
        super().__init__(
            master,
            corner_radius=14,
            fg_color="#1c2333",
            border_width=1,
            border_color="#2a3446",
        )
        self.label_titulo = ctk.CTkLabel(
            self, text=titulo.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#8b949e",
        )
        self.label_titulo.pack(anchor="w", padx=16, pady=(14, 0))
        self.label_valor = ctk.CTkLabel(
            self, text="—",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#e6e8eb",
        )
        self.label_valor.pack(anchor="w", padx=16, pady=(2, 6))
        self.barra = ctk.CTkProgressBar(
            self, height=6, corner_radius=3,
            fg_color="#2a3446", progress_color=COLOR_ESTADO["ok"],
        )
        self.barra.pack(fill="x", padx=16, pady=(0, 14))
        self.barra.set(0)

    def actualizar(self, texto, estado):
        color = COLOR_ESTADO.get(estado, COLOR_ESTADO["ok"])
        self.label_valor.configure(text=texto, text_color=color)
        self.barra.configure(progress_color=color)
        # Intentar extraer un porcentaje del texto para la barra
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", texto)
        if m:
            try:
                self.barra.set(min(float(m.group(1).replace(",", ".")) / 100.0, 1.0))
            except ValueError:
                self.barra.set(0)
        else:
            self.barra.set(0)


def _habilitar_orden_columnas(tabla, titulos, numericas):
    """Hace que las columnas de un Treeview se ordenen al hacer clic en su cabecera.

    'titulos' es {columna: texto_cabecera} y 'numericas' el subconjunto de
    columnas que deben compararse como número en vez de como texto.
    """
    estado = {"columna": None, "ascendente": True}

    def ordenar(columna):
        ascendente = not estado["ascendente"] if estado["columna"] == columna else True
        estado["columna"], estado["ascendente"] = columna, ascendente

        def clave(item):
            valor = tabla.set(item, columna)
            if columna in numericas:
                try:
                    return float(valor)
                except ValueError:
                    return 0.0
            return valor.lower()

        for indice, item in enumerate(sorted(tabla.get_children(""), key=clave, reverse=not ascendente)):
            tabla.move(item, "", indice)

        for col, titulo in titulos.items():
            flecha = (" ▲" if ascendente else " ▼") if col == columna else ""
            tabla.heading(col, text=titulo + flecha, command=lambda c=col: ordenar(c))

    for col, titulo in titulos.items():
        tabla.heading(col, text=titulo, command=lambda c=col: ordenar(c))


class VentanaMantenimiento(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Diagnóstico y mantenimiento del PC — Roberto García")
        self.geometry("920x680")
        self.minsize(780, 540)
        self.configure(fg_color="#0d1117")
        ruta_icono_ventana = os.path.join(ICONS_DIR, "monitor.png")
        if os.path.isfile(ruta_icono_ventana):
            try:
                self._icono_ventana = ImageTk.PhotoImage(Image.open(ruta_icono_ventana))
                self.iconphoto(True, self._icono_ventana)
            except Exception:
                pass

        self.metricas_actuales = None
        self._progreso_activo = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_sidebar()

        self.marco_contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.marco_contenido.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14)
        self.marco_contenido.grid_columnconfigure(0, weight=1)
        self.marco_contenido.grid_rowconfigure(0, weight=1)

        self.paginas = {}
        constructores = {
            "dashboard": self._construir_tab_dashboard,
            "optimizador": self._construir_tab_optimizador,
            "duplicados": self._construir_tab_duplicados,
            "procesos": self._construir_tab_procesos,
            "inicio": self._construir_tab_inicio,
            "avanzado": self._construir_tab_avanzado,
            "historial": self._construir_tab_historial,
            "software": self._construir_tab_software,
        }
        for clave, icono_nombre, titulo in SECCIONES:
            pagina = ctk.CTkFrame(self.marco_contenido, fg_color="#161b22", corner_radius=12)
            pagina.grid(row=0, column=0, sticky="nsew")
            pagina.grid_columnconfigure(0, weight=1)
            pagina.grid_rowconfigure(1, weight=1)
            icono_titulo = _icono(icono_nombre, size=(26, 26))
            ctk.CTkLabel(
                pagina, text="  " + titulo if icono_titulo else titulo,
                image=icono_titulo, compound="left",
                font=ctk.CTkFont(size=21, weight="bold"), text_color="#e6e8eb",
            ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6))
            ctk.CTkFrame(pagina, height=2, fg_color=COLOR_ACENTO, corner_radius=1).grid(
                row=0, column=0, sticky="sw", padx=20, pady=(0, 0)
            )
            cuerpo = ctk.CTkFrame(pagina, fg_color="transparent")
            cuerpo.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
            constructores[clave](cuerpo)
            self.paginas[clave] = pagina

        self._mostrar_seccion("dashboard")

        self.after(100, self.actualizar_diagnostico)
        self.after(200, self.actualizar_procesos)
        self.after(300, self.actualizar_inicio)
        self.after(400, self.actualizar_software)

    # -------- Barra lateral de navegación --------

    def _construir_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=COLOR_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        marco_logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        marco_logo.pack(fill="x", padx=18, pady=(22, 6))
        logo = _icono("monitor.png", size=(34, 34))
        if logo is not None:
            ctk.CTkLabel(marco_logo, image=logo, text="").pack(side="left", padx=(0, 10))
        marco_titulos = ctk.CTkFrame(marco_logo, fg_color="transparent")
        marco_titulos.pack(side="left")
        ctk.CTkLabel(
            marco_titulos, text="Mantenimiento PC",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#e6e8eb",
        ).pack(anchor="w")
        ctk.CTkLabel(
            marco_titulos, text="de Roberto García",
            font=ctk.CTkFont(size=11), text_color="#8b949e",
        ).pack(anchor="w")

        # Separador bajo el logo
        ctk.CTkFrame(sidebar, height=1, fg_color="#2a3446").pack(fill="x", padx=14, pady=(10, 12))

        self.botones_nav = {}
        for clave, icono_nombre, titulo in SECCIONES:
            icono = _icono(icono_nombre, size=(18, 18))
            boton = ctk.CTkButton(
                sidebar,
                text="  " + titulo,
                image=icono,
                anchor="w",
                compound="left",
                corner_radius=10,
                height=38,
                fg_color="transparent",
                hover_color=COLOR_SIDEBAR_HOVER,
                text_color="#c7ccd4",
                font=ctk.CTkFont(size=13),
                command=lambda c=clave: self._mostrar_seccion(c),
            )
            boton.pack(fill="x", padx=12, pady=4)
            self.botones_nav[clave] = boton

        # Firma del autor al pie de la barra lateral
        ctk.CTkLabel(
            sidebar,
            text="© 2026 Roberto García",
            font=ctk.CTkFont(size=11),
            text_color="#8b949e",
        ).pack(side="bottom", pady=(0, 14))

    def _mostrar_seccion(self, clave):
        for otra_clave, boton in self.botones_nav.items():
            activa = otra_clave == clave
            boton.configure(
                fg_color=COLOR_ACENTO if activa else "transparent",
                text_color="white" if activa else "#c7ccd4",
            )
        self.paginas[clave].tkraise()

    # -------- Barra de progreso compartida --------

    def _iniciar_progreso(self, indeterminate=False):
        if indeterminate:
            self.barra_progreso_optimizador.pack(fill="x", padx=4, pady=(0, 8))
            self.barra_progreso_optimizador.start()
        else:
            self._progreso_activo = True
            self._tick_progreso(0.0)

    def _tick_progreso(self, valor):
        if not self._progreso_activo:
            return
        self.barra_progreso.set(valor)
        siguiente = 0.0 if valor >= 1.0 else valor + 0.08
        self.after(120, lambda: self._tick_progreso(siguiente))

    def _detener_progreso(self, indeterminate=False):
        if indeterminate:
            self.barra_progreso_optimizador.stop()
            self.barra_progreso_optimizador.pack_forget()
        else:
            self._progreso_activo = False
            self.barra_progreso.set(1.0)
            self.after(300, lambda: self.barra_progreso.set(0))

    # -------- Pestaña 1: Panel --------

    def _construir_tab_dashboard(self, marco):
        marco_tarjetas = ctk.CTkFrame(marco, fg_color="transparent")
        marco_tarjetas.pack(fill="x", padx=4, pady=(4, 8))
        marco_tarjetas.columnconfigure((0, 1, 2), weight=1)

        self.tarjeta_cpu = TarjetaMetrica(marco_tarjetas, "CPU")
        self.tarjeta_ram = TarjetaMetrica(marco_tarjetas, "RAM")
        self.tarjeta_disco = TarjetaMetrica(marco_tarjetas, "Disco C:")
        self.tarjeta_cpu.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.tarjeta_ram.grid(row=0, column=1, sticky="nsew", padx=6)
        self.tarjeta_disco.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        self.barra_progreso = ctk.CTkProgressBar(marco)
        self.barra_progreso.pack(fill="x", padx=4, pady=(0, 8))
        self.barra_progreso.set(0)

        self.texto = ctk.CTkTextbox(marco, wrap="word", font=("Consolas", 11))
        self.texto.pack(fill="both", expand=True, padx=4, pady=4)
        self.texto.configure(state="disabled")

        self.btn_actualizar = ctk.CTkButton(
            marco, text="⟳  Actualizar diagnóstico",
            command=self.actualizar_diagnostico,
            height=38, corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_actualizar.pack(anchor="w", padx=4, pady=(0, 4))

    def _escribir(self, texto):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("end", texto)
        self.texto.configure(state="disabled")

    def actualizar_diagnostico(self):
        self.btn_actualizar.configure(state="disabled")
        self._iniciar_progreso()
        self._escribir("Analizando el equipo...\n")

        def tarea():
            metricas = utils.diagnostico_metricas()
            self.after(0, lambda: self._mostrar_diagnostico(metricas))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_diagnostico(self, metricas):
        self.metricas_actuales = metricas
        self.tarjeta_cpu.actualizar(metricas["cpu"]["texto"], metricas["cpu"]["estado"])
        self.tarjeta_ram.actualizar(metricas["ram"]["texto"], metricas["ram"]["estado"])
        self.tarjeta_disco.actualizar(metricas["disco"]["texto"], metricas["disco"]["estado"])

        lineas = [
            f"Equipo: {metricas['equipo']} | SO: {metricas['so']}",
            f"Hora del diagnóstico: {metricas['timestamp']}",
            f"Temperaturas: {metricas['temperaturas']}",
            f"Conexión a internet: {'OK' if metricas['internet'] else 'SIN CONEXIÓN'}",
            "Procesos que más CPU consumen:",
        ]
        for p in metricas["procesos_top"]:
            lineas.append(f"  - {p['name']}: CPU {p['cpu_percent']}% | RAM {p['memory_percent']:.1f}%")

        self._escribir("\n".join(lineas))
        self._detener_progreso()
        self.btn_actualizar.configure(state="normal")

    # -------- Pestaña 2: Optimizador (limpieza) --------

    def _construir_tab_optimizador(self, marco):
        self.var_temporales = tk.BooleanVar(value=True)
        self.var_papelera = tk.BooleanVar(value=True)
        self.var_dns = tk.BooleanVar(value=True)

        marco_opciones = ctk.CTkFrame(marco)
        marco_opciones.pack(fill="x", padx=4, pady=(8, 8))
        _fila_con_icono(marco_opciones, "broom.png", "Acciones de limpieza a ejecutar").pack(
            anchor="w", padx=10, pady=(8, 2)
        )
        ctk.CTkCheckBox(marco_opciones, text="Borrar archivos temporales", variable=self.var_temporales).pack(
            anchor="w", padx=12, pady=2
        )
        ctk.CTkCheckBox(marco_opciones, text="Vaciar papelera de reciclaje", variable=self.var_papelera).pack(
            anchor="w", padx=12, pady=2
        )
        ctk.CTkCheckBox(marco_opciones, text="Limpiar caché DNS", variable=self.var_dns).pack(
            anchor="w", padx=12, pady=(2, 10)
        )

        self.barra_progreso_optimizador = ctk.CTkProgressBar(marco, mode="indeterminate")
        self.barra_progreso_optimizador.pack(fill="x", padx=4, pady=(0, 8))
        self.barra_progreso_optimizador.pack_forget()

        self.btn_ejecutar = ctk.CTkButton(marco, text="Ejecutar acciones seleccionadas", command=self.ejecutar_acciones)
        self.btn_ejecutar.pack(anchor="w", padx=4, pady=4)

        self.texto_optimizador = ctk.CTkTextbox(marco, wrap="word", font=("Consolas", 11))
        self.texto_optimizador.pack(fill="both", expand=True, padx=4, pady=4)
        self.texto_optimizador.configure(state="disabled")

    def _escribir_optimizador(self, texto):
        self.texto_optimizador.configure(state="normal")
        self.texto_optimizador.delete("1.0", "end")
        self.texto_optimizador.insert("end", texto)
        self.texto_optimizador.configure(state="disabled")

    def ejecutar_acciones(self):
        self.btn_ejecutar.configure(state="disabled", text="Limpiando...")
        self._iniciar_progreso(indeterminate=True)
        hacer_temporales = self.var_temporales.get()
        hacer_papelera = self.var_papelera.get()
        hacer_dns = self.var_dns.get()

        def tarea():
            log_entries = []
            if hacer_temporales:
                mb_liberados = utils.limpiar_temporales()
                log_entries.append(f"Limpieza de temporales completada. {mb_liberados}MB liberados.")
            if hacer_papelera:
                if utils.vaciar_papelera():
                    log_entries.append("Papelera de reciclaje vaciada.")
            if hacer_dns:
                if utils.limpiar_dns():
                    log_entries.append("Caché DNS limpiada.")
            
            self.after(0, lambda: self._mostrar_resultado(log_entries))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultado(self, log_entries):
        timestamp = utils.datetime.now().strftime("%Y-%m-%d %H:%M")
        full_log = ""
        for entry in log_entries:
            log_line = f"[{timestamp}] {entry}\n"
            full_log += log_line
            self.historial_texto.configure(state="normal")
            self.historial_texto.insert("1.0", log_line)
            self.historial_texto.configure(state="disabled")

        if full_log:
            with open(utils.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(full_log + "\n")
        
        self._escribir_optimizador(full_log)
        self._detener_progreso(indeterminate=True)
        self.btn_ejecutar.configure(state="normal", text="Ejecutar acciones seleccionadas")

    # -------- Pestaña 3: Archivos duplicados --------

    def _construir_tab_duplicados(self, marco):
        self.grupos_duplicados = []
        self.duplicados_marcados = set()

        ctk.CTkLabel(
            marco,
            text=(
                "Busca archivos con contenido idéntico (por tamaño y hash, no por nombre). "
                "Solo lee: no borra nada hasta que tú lo pidas, y siempre envía a la papelera de reciclaje (reversible)."
            ),
            wraplength=700, justify="left", text_color="gray60",
        ).pack(anchor="w", padx=4, pady=(4, 6))

        marco_ruta = ctk.CTkFrame(marco, fg_color="transparent")
        marco_ruta.pack(fill="x", padx=4, pady=(0, 6))
        self.entry_ruta_duplicados = ctk.CTkEntry(marco_ruta, placeholder_text="Carpeta donde buscar")
        self.entry_ruta_duplicados.insert(0, os.path.expanduser("~"))
        self.entry_ruta_duplicados.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(marco_ruta, text="Elegir...", width=80, command=self._elegir_carpeta_duplicados).pack(side="left", padx=6)
        self.btn_buscar_duplicados = ctk.CTkButton(marco_ruta, text="Buscar duplicados", width=130, command=self._buscar_duplicados)
        self.btn_buscar_duplicados.pack(side="left")

        columnas = ("ruta", "tamano", "modificado", "estado")
        self.tabla_duplicados = ttk.Treeview(marco, columns=columnas, show="tree headings", height=14)
        self.tabla_duplicados.heading("#0", text="Grupo")
        self.tabla_duplicados.heading("ruta", text="Archivo")
        self.tabla_duplicados.heading("tamano", text="Tamaño (MB)")
        self.tabla_duplicados.heading("modificado", text="Modificado")
        self.tabla_duplicados.heading("estado", text="Estado")
        self.tabla_duplicados.column("#0", width=110)
        self.tabla_duplicados.column("ruta", width=320)
        self.tabla_duplicados.column("tamano", width=90, anchor="center")
        self.tabla_duplicados.column("modificado", width=130, anchor="center")
        self.tabla_duplicados.column("estado", width=110, anchor="center")
        self.tabla_duplicados.pack(fill="both", expand=True, padx=4, pady=4)
        self.tabla_duplicados.bind("<Button-1>", self._clic_tabla_duplicados)
        self.tabla_duplicados.tag_configure("marcado", foreground="#c0392b")

        self.label_resumen_duplicados = ctk.CTkLabel(marco, text="")
        self.label_resumen_duplicados.pack(anchor="w", padx=4, pady=(0, 4))

        marco_botones = ctk.CTkFrame(marco, fg_color="transparent")
        marco_botones.pack(fill="x", padx=4, pady=(0, 8))
        ctk.CTkButton(
            marco_botones, text="Marcar automático (conservar el más reciente)",
            command=self._marcar_duplicados_automatico,
        ).pack(side="left")
        self.btn_borrar_duplicados = ctk.CTkButton(
            marco_botones, text="Enviar marcados a la papelera", fg_color="#c0392b", hover_color="#992e22",
            command=self._enviar_duplicados_papelera,
        )
        self.btn_borrar_duplicados.pack(side="left", padx=8)

    def _elegir_carpeta_duplicados(self):
        ruta = filedialog.askdirectory()
        if ruta:
            self.entry_ruta_duplicados.delete(0, "end")
            self.entry_ruta_duplicados.insert(0, ruta)

    def _buscar_duplicados(self):
        ruta = self.entry_ruta_duplicados.get().strip()
        if not ruta:
            return
        self.btn_buscar_duplicados.configure(state="disabled", text="Buscando...")
        self.duplicados_marcados.clear()
        self.label_resumen_duplicados.configure(text="Buscando archivos duplicados, esto puede tardar según el tamaño de la carpeta...")

        def tarea():
            grupos, error = utils.buscar_duplicados(ruta)
            self.after(0, lambda: self._mostrar_duplicados(grupos, error))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_duplicados(self, grupos, error):
        self.grupos_duplicados = grupos
        self.tabla_duplicados.delete(*self.tabla_duplicados.get_children())

        if error:
            messagebox.showerror("No se pudo buscar", error)
        else:
            espacio_recuperable = sum(g[0]["tamano_mb"] * (len(g) - 1) for g in grupos)
            for indice, grupo in enumerate(grupos):
                grupo_iid = f"grupo{indice}"
                self.tabla_duplicados.insert(
                    "", "end", iid=grupo_iid, text=f"Grupo {indice + 1} ({len(grupo)} copias)", open=True,
                )
                for archivo in grupo:
                    self.tabla_duplicados.insert(
                        grupo_iid, "end", iid=archivo["ruta"],
                        values=(archivo["ruta"], f"{archivo['tamano_mb']:.2f}", archivo["modificado"], ""),
                    )
            self.label_resumen_duplicados.configure(
                text=f"{len(grupos)} grupos de duplicados encontrados — hasta {espacio_recuperable:.1f} MB recuperables."
                if grupos else "No se encontraron archivos duplicados en esta carpeta."
            )

        self.btn_buscar_duplicados.configure(state="normal", text="Buscar duplicados")

    def _clic_tabla_duplicados(self, evento):
        fila = self.tabla_duplicados.identify_row(evento.y)
        if not fila or not self.tabla_duplicados.parent(fila):
            return  # clic fuera de una fila, o en la cabecera de un grupo (no un archivo)

        if fila in self.duplicados_marcados:
            self.duplicados_marcados.discard(fila)
            self.tabla_duplicados.set(fila, "estado", "")
            self.tabla_duplicados.item(fila, tags=())
        else:
            self.duplicados_marcados.add(fila)
            self.tabla_duplicados.set(fila, "estado", "Se enviará a la papelera")
            self.tabla_duplicados.item(fila, tags=("marcado",))

    def _marcar_duplicados_automatico(self):
        """Marca todos los archivos de cada grupo menos el modificado más reciente."""
        self.duplicados_marcados.clear()
        for grupo in self.grupos_duplicados:
            mas_reciente = max(grupo, key=lambda a: a["modificado"])
            for archivo in grupo:
                fila = archivo["ruta"]
                if archivo is mas_reciente:
                    self.tabla_duplicados.set(fila, "estado", "")
                    self.tabla_duplicados.item(fila, tags=())
                else:
                    self.duplicados_marcados.add(fila)
                    self.tabla_duplicados.set(fila, "estado", "Se enviará a la papelera")
                    self.tabla_duplicados.item(fila, tags=("marcado",))

    def _enviar_duplicados_papelera(self):
        if not self.duplicados_marcados:
            messagebox.showinfo("Nada marcado", "Marca al menos un archivo haciendo clic sobre él en la lista.")
            return

        # Red de seguridad: nunca vaciar un grupo entero, siempre debe quedar al menos 1 copia.
        rutas_a_enviar = []
        for grupo in self.grupos_duplicados:
            rutas_grupo = [a["ruta"] for a in grupo]
            marcadas_del_grupo = [r for r in rutas_grupo if r in self.duplicados_marcados]
            if len(marcadas_del_grupo) == len(rutas_grupo) and marcadas_del_grupo:
                marcadas_del_grupo = marcadas_del_grupo[:-1]  # se conserva la última del grupo
            rutas_a_enviar.extend(marcadas_del_grupo)

        if not rutas_a_enviar:
            messagebox.showinfo("Nada que enviar", "No queda nada seguro que borrar (se conserva siempre 1 copia por grupo).")
            return

        if not messagebox.askyesno(
            "Confirmar",
            f"Se enviarán {len(rutas_a_enviar)} archivo(s) a la papelera de reciclaje (podrás recuperarlos desde allí). ¿Continuar?",
        ):
            return

        self.btn_borrar_duplicados.configure(state="disabled", text="Enviando...")

        def tarea():
            rutas_con_error = set()
            mensajes_error = []
            for ruta in rutas_a_enviar:
                exito, mensaje = utils.enviar_a_papelera(ruta)
                if not exito:
                    rutas_con_error.add(ruta)
                    mensajes_error.append(f"{ruta}: {mensaje}")
            self.after(0, lambda: self._tras_enviar_duplicados(rutas_a_enviar, rutas_con_error, mensajes_error))

        threading.Thread(target=tarea, daemon=True).start()

    def _tras_enviar_duplicados(self, rutas_enviadas, rutas_con_error, mensajes_error):
        for ruta in rutas_enviadas:
            if ruta not in rutas_con_error and self.tabla_duplicados.exists(ruta):
                self.tabla_duplicados.delete(ruta)
            self.duplicados_marcados.discard(ruta)

        for grupo_iid in list(self.tabla_duplicados.get_children("")):
            if len(self.tabla_duplicados.get_children(grupo_iid)) < 2:
                self.tabla_duplicados.delete(grupo_iid)

        self.btn_borrar_duplicados.configure(state="normal", text="Enviar marcados a la papelera")
        if mensajes_error:
            messagebox.showwarning("Algunos archivos no se pudieron enviar", "\n".join(mensajes_error))
        else:
            messagebox.showinfo("Listo", f"{len(rutas_enviadas)} archivo(s) enviados a la papelera de reciclaje.")

    # -------- Pestaña 4: Procesos en segundo plano --------

    def _construir_tab_procesos(self, marco):
        aviso = (
            "Los procesos marcados como (protegido) son del sistema y no se pueden finalizar. "
            "Revisa el nombre antes de finalizar cualquier otro: puede cerrar un programa con trabajo sin guardar."
        )
        ctk.CTkLabel(marco, text=aviso, wraplength=700, justify="left", text_color="gray60").pack(
            anchor="w", padx=4, pady=(4, 8)
        )

        columnas = ("pid", "nombre", "cpu", "ram")
        self.tabla_procesos = ttk.Treeview(marco, columns=columnas, show="headings", height=15)
        _habilitar_orden_columnas(
            self.tabla_procesos,
            {"pid": "PID", "nombre": "Nombre", "cpu": "CPU %", "ram": "RAM %"},
            numericas={"pid", "cpu", "ram"},
        )
        self.tabla_procesos.column("pid", width=70, anchor="center")
        self.tabla_procesos.column("nombre", width=320)
        self.tabla_procesos.column("cpu", width=80, anchor="center")
        self.tabla_procesos.column("ram", width=80, anchor="center")
        self.tabla_procesos.pack(fill="both", expand=True, padx=4, pady=4)

        marco_botones = ctk.CTkFrame(marco, fg_color="transparent")
        marco_botones.pack(fill="x", padx=4, pady=4)
        self.btn_refrescar_procesos = ctk.CTkButton(marco_botones, text="Actualizar lista", command=self.actualizar_procesos)
        self.btn_refrescar_procesos.pack(side="left")
        self.btn_finalizar = ctk.CTkButton(
            marco_botones, text="Finalizar proceso seleccionado", fg_color="#c0392b", hover_color="#992e22",
            command=self.finalizar_seleccionado,
        )
        self.btn_finalizar.pack(side="left", padx=8)

    def actualizar_procesos(self):
        self.btn_refrescar_procesos.configure(state="disabled")

        def tarea():
            procesos = utils.procesos_por_consumo()
            self.after(0, lambda: self._mostrar_procesos(procesos))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_procesos(self, procesos):
        self.tabla_procesos.delete(*self.tabla_procesos.get_children())
        for p in procesos:
            protegido = " (protegido)" if utils.es_proceso_protegido(p['name']) else ""
            self.tabla_procesos.insert(
                "", "end", iid=str(p['pid']),
                values=(p['pid'], f"{p['name']}{protegido}", f"{p['cpu_percent'] or 0:.1f}", f"{p['memory_percent'] or 0:.1f}"),
            )
        self.btn_refrescar_procesos.configure(state="normal")

    def finalizar_seleccionado(self):
        seleccion = self.tabla_procesos.selection()
        if not seleccion:
            messagebox.showinfo("Ningún proceso seleccionado", "Selecciona primero un proceso de la lista.")
            return
        pid = int(seleccion[0])
        valores = self.tabla_procesos.item(seleccion[0], "values")
        nombre = valores[1].replace(" (protegido)", "")

        if utils.es_proceso_protegido(nombre):
            messagebox.showwarning("Proceso protegido", f"'{nombre}' es un proceso del sistema y no se puede finalizar desde aquí.")
            return

        if not messagebox.askyesno("Confirmar", f"¿Finalizar el proceso '{nombre}' (PID {pid})?"):
            return

        exito, mensaje = utils.finalizar_proceso(pid, nombre)
        (messagebox.showinfo if exito else messagebox.showerror)(
            "Proceso finalizado" if exito else "No se pudo finalizar", mensaje
        )
        self.actualizar_procesos()

    # -------- Pestaña 5: Gestión de inicio --------

    def _construir_tab_inicio(self, marco):
        ctk.CTkLabel(
            marco,
            text="Accesos directos de la carpeta de Inicio (activar/desactivar es reversible, no borra nada):",
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=4, pady=(4, 4))

        columnas = ("nombre", "estado")
        self.tabla_inicio_carpeta = ttk.Treeview(marco, columns=columnas, show="headings", height=6)
        _habilitar_orden_columnas(
            self.tabla_inicio_carpeta, {"nombre": "Programa", "estado": "Estado"}, numericas=set()
        )
        self.tabla_inicio_carpeta.column("nombre", width=460)
        self.tabla_inicio_carpeta.column("estado", width=140, anchor="center")
        self.tabla_inicio_carpeta.pack(fill="both", expand=False, padx=4, pady=4)

        marco_botones = ctk.CTkFrame(marco, fg_color="transparent")
        marco_botones.pack(fill="x", padx=4, pady=(0, 10))
        ctk.CTkButton(marco_botones, text="Actualizar lista", command=self.actualizar_inicio).pack(side="left")
        ctk.CTkButton(marco_botones, text="Activar", command=lambda: self._alternar_inicio(True)).pack(side="left", padx=8)
        ctk.CTkButton(marco_botones, text="Desactivar", command=lambda: self._alternar_inicio(False)).pack(side="left")

        ctk.CTkLabel(
            marco,
            text=(
                "Entradas de inicio en el registro de Windows (solo informativo: no se modifican aquí,\n"
                "porque editar el registro conlleva más riesgo; usa una herramienta dedicada si quieres desactivarlas):"
            ),
            wraplength=700, justify="left", text_color="gray60",
        ).pack(anchor="w", padx=4, pady=(6, 4))

        columnas_reg = ("origen", "nombre", "comando")
        self.tabla_inicio_registro = ttk.Treeview(marco, columns=columnas_reg, show="headings", height=6)
        _habilitar_orden_columnas(
            self.tabla_inicio_registro,
            {"origen": "Origen", "nombre": "Nombre", "comando": "Comando"},
            numericas=set(),
        )
        self.tabla_inicio_registro.column("origen", width=70, anchor="center")
        self.tabla_inicio_registro.column("nombre", width=150)
        self.tabla_inicio_registro.column("comando", width=460)
        self.tabla_inicio_registro.pack(fill="both", expand=True, padx=4, pady=4)

    def actualizar_inicio(self):
        def tarea():
            carpeta = utils.listar_inicio_carpeta()
            registro = utils.listar_inicio_registro()
            self.after(0, lambda: self._mostrar_inicio(carpeta, registro))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_inicio(self, carpeta, registro):
        self.tabla_inicio_carpeta.delete(*self.tabla_inicio_carpeta.get_children())
        for entrada in carpeta:
            self.tabla_inicio_carpeta.insert(
                "", "end", iid=entrada["ruta"],
                values=(entrada["nombre"], "Activado" if entrada["habilitado"] else "Desactivado"),
            )

        self.tabla_inicio_registro.delete(*self.tabla_inicio_registro.get_children())
        for entrada in registro:
            self.tabla_inicio_registro.insert(
                "", "end", values=(entrada["origen"], entrada["nombre"], entrada["comando"])
            )

    def _alternar_inicio(self, habilitar):
        seleccion = self.tabla_inicio_carpeta.selection()
        if not seleccion:
            messagebox.showinfo("Ningún elemento seleccionado", "Selecciona primero un acceso directo de la lista.")
            return
        ruta = seleccion[0]
        exito, mensaje, _ = utils.alternar_inicio_carpeta(ruta, habilitar)
        if not exito:
            messagebox.showerror("No se pudo cambiar", mensaje)
        self.actualizar_inicio()

    # -------- Pestaña 6: Herramientas avanzadas --------

    def _construir_tab_avanzado(self, marco):
        # --- Analizador de espacio en disco (solo lectura) ---
        marco_disco = ctk.CTkFrame(marco)
        marco_disco.pack(fill="x", padx=4, pady=(8, 8))
        ctk.CTkLabel(marco_disco, text="Analizador de espacio en disco (no borra nada)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 2)
        )
        marco_ruta = ctk.CTkFrame(marco_disco, fg_color="transparent")
        marco_ruta.pack(fill="x", padx=10, pady=(0, 8))
        self.entry_ruta = ctk.CTkEntry(marco_ruta, placeholder_text="Carpeta a analizar")
        self.entry_ruta.insert(0, os.path.expanduser("~"))
        self.entry_ruta.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(marco_ruta, text="Elegir...", width=80, command=self._elegir_carpeta).pack(side="left", padx=6)
        self.btn_analizar_disco = ctk.CTkButton(marco_ruta, text="Analizar", width=90, command=self._analizar_disco)
        self.btn_analizar_disco.pack(side="left")

        columnas_disco = ("carpeta", "mb")
        self.tabla_disco = ttk.Treeview(marco_disco, columns=columnas_disco, show="headings", height=6)
        _habilitar_orden_columnas(self.tabla_disco, {"carpeta": "Carpeta", "mb": "Tamaño (MB)"}, numericas={"mb"})
        self.tabla_disco.column("carpeta", width=460)
        self.tabla_disco.column("mb", width=140, anchor="center")
        self.tabla_disco.pack(fill="x", padx=10, pady=(0, 10))

        # --- SFC y reset de red (manuales, con confirmación) ---
        marco_sistema = ctk.CTkFrame(marco)
        marco_sistema.pack(fill="x", padx=4, pady=8)
        ctk.CTkLabel(
            marco_sistema,
            text="Operaciones avanzadas (requieren administrador, piden confirmación antes de ejecutarse):",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 6))

        marco_botones_sistema = ctk.CTkFrame(marco_sistema, fg_color="transparent")
        marco_botones_sistema.pack(fill="x", padx=10, pady=(0, 4))
        self.btn_sfc = ctk.CTkButton(marco_botones_sistema, text="Verificar archivos de sistema (SFC)", command=self._ejecutar_sfc)
        self.btn_sfc.pack(side="left")
        self.btn_reset_red = ctk.CTkButton(marco_botones_sistema, text="Reiniciar configuración TCP/IP", command=self._resetear_red)
        self.btn_reset_red.pack(side="left", padx=8)
        ctk.CTkButton(marco_botones_sistema, text="Desinstalar programas (abre Windows)", command=self._abrir_desinstalador).pack(
            side="left"
        )

        self.texto_avanzado = ctk.CTkTextbox(marco, wrap="word", font=("Consolas", 11))
        self.texto_avanzado.pack(fill="both", expand=True, padx=4, pady=(8, 4))
        self.texto_avanzado.configure(state="disabled")

    def _escribir_avanzado(self, texto):
        self.texto_avanzado.configure(state="normal")
        self.texto_avanzado.delete("1.0", "end")
        self.texto_avanzado.insert("end", texto)
        self.texto_avanzado.configure(state="disabled")

    def _elegir_carpeta(self):
        ruta = filedialog.askdirectory()
        if ruta:
            self.entry_ruta.delete(0, "end")
            self.entry_ruta.insert(0, ruta)

    def _analizar_disco(self):
        ruta = self.entry_ruta.get().strip()
        if not ruta:
            return
        self.btn_analizar_disco.configure(state="disabled", text="Analizando...")

        def tarea():
            resultados, error = utils.analizar_espacio_carpetas(ruta)
            self.after(0, lambda: self._mostrar_disco(resultados, error))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_disco(self, resultados, error):
        self.tabla_disco.delete(*self.tabla_disco.get_children())
        if error:
            messagebox.showerror("No se pudo analizar", error)
        else:
            for nombre, mb in resultados:
                self.tabla_disco.insert("", "end", values=(nombre, f"{mb:.1f}"))
        self.btn_analizar_disco.configure(state="normal", text="Analizar")

    def _pedir_elevacion(self, accion):
        """Si no hay permisos de administrador, ofrece reiniciar el programa como tal.

        Devuelve True si ya se puede continuar con la acción (ya éramos
        administrador). Si el usuario acepta reiniciar, se lanza la nueva
        instancia elevada (Windows pedirá confirmación por UAC) y se cierra
        esta; devuelve False para que el llamante no siga con la acción actual.
        """
        if utils.es_administrador():
            return True
        if messagebox.askyesno(
            "Necesita permisos de administrador",
            f"{accion} requiere ejecutar este programa como administrador.\n\n"
            "¿Reiniciar el programa ahora como administrador? Windows te pedirá confirmación.",
        ):
            if utils.reiniciar_como_administrador():
                self.destroy()
            else:
                messagebox.showerror(
                    "No se pudo reiniciar",
                    "No se pudo relanzar el programa como administrador. Inténtalo manualmente: "
                    "clic derecho sobre el programa -> \"Ejecutar como administrador\".",
                )
        return False

    def _ejecutar_sfc(self):
        if not self._pedir_elevacion("Verificar archivos de sistema (SFC)"):
            return
        if not messagebox.askyesno(
            "Confirmar verificación de archivos de sistema",
            "Esto ejecuta 'sfc /scannow'. Puede tardar varios minutos y necesita permisos de administrador.\n\n¿Continuar?",
        ):
            return
        self.btn_sfc.configure(state="disabled", text="Verificando...")
        self._escribir_avanzado("Ejecutando sfc /scannow, esto puede tardar varios minutos...\n")

        def tarea():
            exito, salida = utils.ejecutar_sfc_scan()
            self.after(0, lambda: self._mostrar_avanzado_resultado(self.btn_sfc, "Verificar archivos de sistema (SFC)", exito, salida))

        threading.Thread(target=tarea, daemon=True).start()

    def _resetear_red(self):
        if not self._pedir_elevacion("Reiniciar la configuración TCP/IP"):
            return
        if not messagebox.askyesno(
            "Confirmar reinicio de red",
            "Esto ejecuta 'netsh int ip reset' y normalmente requiere reiniciar el equipo después. "
            "Necesita permisos de administrador.\n\n¿Continuar?",
        ):
            return
        self.btn_reset_red.configure(state="disabled", text="Reiniciando red...")
        self._escribir_avanzado("Restableciendo configuración TCP/IP...\n")

        def tarea():
            exito, salida = utils.resetear_tcpip()
            self.after(0, lambda: self._mostrar_avanzado_resultado(self.btn_reset_red, "Reiniciar configuración TCP/IP", exito, salida))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_avanzado_resultado(self, boton, texto_original, exito, salida):
        self._escribir_avanzado(salida)
        boton.configure(state="normal", text=texto_original)
        if not exito:
            messagebox.showwarning("Revisa el resultado", "El comando no terminó correctamente; revisa el texto mostrado.")

    def _abrir_desinstalador(self):
        if not utils.abrir_desinstalador_windows():
            messagebox.showerror("No se pudo abrir", "No se pudo abrir el panel de aplicaciones de Windows.")

    # -------- Pestaña 7: Historial --------

    def _construir_tab_historial(self, marco):
        fila_titulo = ctk.CTkFrame(marco, fg_color="transparent")
        fila_titulo.pack(anchor="w", padx=4, pady=(4, 4))
        icono_historial = _icono("clock.png")
        if icono_historial is not None:
            ctk.CTkLabel(fila_titulo, image=icono_historial, text="").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            fila_titulo,
            text="Historial de acciones de limpieza realizadas en esta sesión.",
            wraplength=700, justify="left",
        ).pack(side="left")

        self.historial_texto = ctk.CTkTextbox(marco, wrap="word", font=("Consolas", 11))
        self.historial_texto.pack(fill="both", expand=True, padx=4, pady=4)
        self.historial_texto.configure(state="disabled")

    # -------- Pestaña 8: Software --------

    def _construir_tab_software(self, marco):
        ctk.CTkLabel(
            marco,
            text="Programas instalados en el equipo. La desinstalación se realiza a través del desinstalador de Windows.",
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=4, pady=(4, 4))

        columnas = ("nombre", "version", "editor")
        self.tabla_software = ttk.Treeview(marco, columns=columnas, show="headings", height=15)
        _habilitar_orden_columnas(
            self.tabla_software,
            {"nombre": "Nombre", "version": "Versión", "editor": "Editor"},
            numericas=set(),
        )
        self.tabla_software.column("nombre", width=320)
        self.tabla_software.column("version", width=100)
        self.tabla_software.column("editor", width=200)
        self.tabla_software.pack(fill="both", expand=True, padx=4, pady=4)

        marco_botones = ctk.CTkFrame(marco, fg_color="transparent")
        marco_botones.pack(fill="x", padx=4, pady=4)
        self.btn_refrescar_software = ctk.CTkButton(marco_botones, text="Actualizar lista", command=self.actualizar_software)
        self.btn_refrescar_software.pack(side="left")
        self.btn_desinstalar = ctk.CTkButton(
            marco_botones, text="Desinstalar programa seleccionado", fg_color="#c0392b", hover_color="#992e22",
            command=self.desinstalar_software_seleccionado,
        )
        self.btn_desinstalar.pack(side="left", padx=8)

    def actualizar_software(self):
        self.btn_refrescar_software.configure(state="disabled")

        def tarea():
            programas = utils.listar_programas_instalados()
            self.after(0, lambda: self._mostrar_software(programas))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_software(self, programas):
        self.tabla_software.delete(*self.tabla_software.get_children())
        for indice, p in enumerate(programas):
            self.tabla_software.insert(
                "", "end", iid=str(indice),
                values=(p['nombre'], p['version'], p['editor']),
            )
        self.btn_refrescar_software.configure(state="normal")

    def desinstalar_software_seleccionado(self):
        seleccion = self.tabla_software.selection()
        if not seleccion:
            messagebox.showinfo("Ningún programa seleccionado", "Selecciona primero un programa de la lista.")
            return
        nombre = self.tabla_software.item(seleccion[0], "values")[0]

        if not messagebox.askyesno("Confirmar", f"¿Desinstalar el programa '{nombre}'?"):
            return

        exito, mensaje = utils.desinstalar_programa(nombre)
        (messagebox.showinfo if exito else messagebox.showerror)(
            "Desinstalación iniciada" if exito else "No se pudo desinstalar", mensaje
        )
        self.actualizar_software()


def main():
    app = VentanaMantenimiento()
    app.mainloop()


if __name__ == "__main__":
    main()
