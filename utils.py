"""
Lógica de diagnóstico y mantenimiento del PC (sin interfaz gráfica).

Se separa de la interfaz para que diagnostico_mantenimiento_pc.py se pueda
centrar solo en la ventana, y para poder probar o reutilizar estas funciones
por separado.

MÓDULOS:
  1. Diagnóstico            (CPU, RAM, disco, temperatura, internet, procesos)
  2. Limpieza                (temporales, papelera, DNS)
  3. Gestión de procesos      (ver y finalizar procesos, con protección)
  4. Gestión de inicio        (activar/desactivar accesos directos de arranque)

Sobre "Gestión de inicio": esta versión SOLO gestiona accesos directos de la
carpeta de Inicio de Windows (moviéndolos a una subcarpeta "Deshabilitados",
exactamente igual que ya hace Windows/el propio usuario a mano - reversible
en un clic, sin tocar el registro). Las entradas de inicio que viven en el
registro (Run/RunOnce) se listan solo como información: desactivarlas ahí
significa editar el registro, que es una operación de mayor riesgo y por
eso se deja fuera del "hacerlo automático" (ver sección de seguridad del
archivo principal).
"""

import ctypes
import hashlib
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import winreg
from datetime import datetime

import psutil
import send2trash

LOG_FILE = os.path.join(os.path.expanduser("~"), "diagnostico_pc.log")
UMBRAL_CPU = 85
UMBRAL_RAM = 85
UMBRAL_DISCO = 90

# Procesos que nunca se dejan finalizar desde la app: procesos propios de
# Windows (o de este script) cuyo cierre puede colgar la sesión o el sistema.
PROCESOS_PROTEGIDOS = {
    "system", "system idle process", "registry",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "explorer.exe",
    "dwm.exe", "fontdrvhost.exe", "python.exe", "pythonw.exe",
}

REGISTRO_RUN_KEYS = [
    ("HKCU", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
]


def _estado(valor, umbral):
    """Clasifica un porcentaje en 'ok' / 'warn' / 'bad' según el umbral de alerta."""
    if valor >= umbral:
        return "bad"
    if valor >= umbral - 15:
        return "warn"
    return "ok"


# ============================================================
# 1) DIAGNÓSTICO — solo lectura, no modifica nada
# ============================================================

def check_internet():
    """Intenta abrir una conexión corta a un DNS público para saber si hay internet."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


def obtener_temperaturas():
    """Lee sensores de temperatura si el equipo/driver los expone (no todos los PC lo permiten)."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return "No disponible en este equipo"
        resumen = [f"{n} {e.label or ''}: {e.current:.1f}°C" for n, es in temps.items() for e in es]
        return "; ".join(resumen) if resumen else "No disponible"
    except Exception:
        return "No disponible (requiere permisos o hardware compatible)"


def top_procesos(n=5):
    """Devuelve los N procesos que más CPU consumen en este instante.

    psutil necesita dos lecturas separadas en el tiempo para calcular un
    cpu_percent real (la primera siempre devuelve 0.0), así que se toma una
    primera muestra de referencia, se espera un poco y se vuelve a leer.
    """
    procesos = list(psutil.process_iter(['name', 'memory_percent']))
    for p in procesos:
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(0.3)

    resultado = []
    for p in procesos:
        try:
            info = dict(p.info)
            info['cpu_percent'] = p.cpu_percent(None)
            resultado.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    resultado.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
    return resultado[:n]


def tamano_carpeta(ruta):
    """Suma el tamaño de todos los archivos de una carpeta (para medir MB liberados)."""
    total = 0
    for dirpath, _, filenames in os.walk(ruta):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def diagnostico_metricas():
    """Reúne CPU, RAM, disco, temperatura, internet y procesos en un diccionario.

    Cada métrica principal (cpu/ram/disco) incluye un 'estado' ok/warn/bad
    para que la interfaz pueda pintar tarjetas de color sin repetir umbrales.
    """
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    total, usado, libre = shutil.disk_usage("C:\\")
    porcentaje_disco = usado / total * 100

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "equipo": platform.node(),
        "so": platform.platform(),
        "cpu": {"texto": f"{cpu:.1f}%", "estado": _estado(cpu, UMBRAL_CPU)},
        "ram": {
            "texto": f"{ram.percent:.1f}%  ({ram.used // (1024**2)} / {ram.total // (1024**2)} MB)",
            "estado": _estado(ram.percent, UMBRAL_RAM),
        },
        "disco": {
            "texto": f"{porcentaje_disco:.1f}%  ({libre // (1024**3)} GB libres)",
            "estado": _estado(porcentaje_disco, UMBRAL_DISCO),
        },
        "temperaturas": obtener_temperaturas(),
        "internet": check_internet(),
        "procesos_top": top_procesos(),
    }


# ============================================================
# 2) LIMPIEZA — únicas funciones que borran/modifican algo,
#    y solo tocan carpetas temporales / caché, nunca datos del usuario.
# ============================================================

def limpiar_temporales():
    """Borra el contenido de %TEMP% y C:\\Windows\\Temp. Devuelve MB liberados.

    Si un archivo está en uso o no hay permisos para borrarlo, se salta ese
    archivo y sigue con el resto; nunca sale de estas dos carpetas.
    """
    carpetas = [os.environ.get("TEMP", ""), r"C:\Windows\Temp"]
    liberado = 0
    for carpeta in carpetas:
        if not carpeta or not os.path.isdir(carpeta):
            continue
        try:
            nombres = os.listdir(carpeta)
        except (PermissionError, OSError):
            continue  # sin permisos para esta carpeta (requiere admin), se omite
        for nombre in nombres:
            ruta = os.path.join(carpeta, nombre)
            try:
                if os.path.isfile(ruta) or os.path.islink(ruta):
                    tamano = os.path.getsize(ruta)
                    os.remove(ruta)
                    liberado += tamano
                elif os.path.isdir(ruta):
                    tamano = tamano_carpeta(ruta)
                    shutil.rmtree(ruta, ignore_errors=True)
                    if not os.path.isdir(ruta):
                        liberado += tamano
            except OSError:
                pass  # archivo en uso, se ignora
    return liberado // (1024 ** 2)


def vaciar_papelera():
    """Vacía la papelera de reciclaje de Windows. Acción irreversible."""
    # S_OK (0) o S_FALSE... en la práctica SHEmptyRecycleBinW devuelve un código
    # distinto de 0 cuando falla; 0x8000FFFF/-2147418113 = papelera ya vacía, no es error.
    PAPELERA_YA_VACIA = -2147418113
    try:
        resultado = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000001 | 0x00000002 | 0x00000004)
        return resultado == 0 or resultado == PAPELERA_YA_VACIA
    except Exception:
        return False


def limpiar_dns():
    """Limpia la caché de resolución DNS (equivalente a 'ipconfig /flushdns')."""
    try:
        resultado = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return resultado.returncode == 0
    except Exception:
        return False


# ============================================================
# 3) GESTIÓN DE PROCESOS EN SEGUNDO PLANO
# ============================================================

def procesos_por_consumo(n=20):
    """Devuelve los N procesos que más RAM consumen, con PID, nombre, CPU% y RAM%."""
    procesos = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = p.info
            if info['pid'] == 0:
                continue
            procesos.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procesos.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
    return procesos[:n]


def es_proceso_protegido(nombre):
    """True si el proceso está en la lista de procesos críticos que no se deben finalizar."""
    return (nombre or "").strip().lower() in PROCESOS_PROTEGIDOS


def finalizar_proceso(pid, nombre):
    """Intenta finalizar un proceso por PID. Rechaza los de la lista de protegidos."""
    if es_proceso_protegido(nombre):
        return False, f"'{nombre}' es un proceso del sistema protegido: no se finaliza."
    try:
        proceso = psutil.Process(pid)
        proceso.terminate()
        proceso.wait(timeout=3)
        return True, f"Proceso '{nombre}' (PID {pid}) finalizado."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.TimeoutExpired:
        return False, f"'{nombre}' no respondió a tiempo al cierre."
    except psutil.AccessDenied:
        return False, f"Sin permisos para finalizar '{nombre}' (prueba a ejecutar como administrador)."
    except Exception as e:
        return False, f"No se pudo finalizar '{nombre}': {e}"


# ============================================================
# 4) GESTIÓN DE INICIO
#    - Accesos directos de la carpeta de Inicio: se pueden activar/desactivar
#      moviéndolos a una subcarpeta "Deshabilitados" (reversible, sin registro).
#    - Entradas del registro (Run): solo informativas, no se modifican aquí.
# ============================================================

def _carpetas_startup():
    """Carpeta de Inicio del usuario actual y su subcarpeta de deshabilitados."""
    startup = os.path.join(
        os.path.expanduser("~"),
        r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup",
    )
    deshabilitados = os.path.join(startup, "Deshabilitados")
    return startup, deshabilitados


def listar_inicio_carpeta():
    """Lista los accesos directos de la carpeta de Inicio, activos y deshabilitados."""
    startup, deshabilitados = _carpetas_startup()
    entradas = []
    for carpeta, habilitado in ((startup, True), (deshabilitados, False)):
        if not os.path.isdir(carpeta):
            continue
        for nombre in os.listdir(carpeta):
            ruta = os.path.join(carpeta, nombre)
            if os.path.isfile(ruta) and nombre.lower().endswith((".lnk", ".url")):
                entradas.append({"nombre": nombre, "ruta": ruta, "habilitado": habilitado})
    return entradas


def alternar_inicio_carpeta(ruta, habilitar):
    """Mueve un acceso directo entre la carpeta de Inicio y 'Deshabilitados'."""
    startup, deshabilitados = _carpetas_startup()
    if not os.path.isfile(ruta):
        return False, "El acceso directo ya no existe.", ruta
    os.makedirs(deshabilitados, exist_ok=True)
    destino_carpeta = startup if habilitar else deshabilitados
    destino = os.path.join(destino_carpeta, os.path.basename(ruta))
    try:
        if os.path.abspath(ruta) != os.path.abspath(destino):
            shutil.move(ruta, destino)
        return True, ("activado" if habilitar else "desactivado"), destino
    except OSError as e:
        return False, f"No se pudo mover: {e}", ruta


def listar_inicio_registro():
    """Lista (solo lectura) las entradas de arranque del registro (HKCU/HKLM Run)."""
    entradas = []
    for etiqueta, hive, subclave in REGISTRO_RUN_KEYS:
        try:
            with winreg.OpenKey(hive, subclave, 0, winreg.KEY_READ) as clave:
                i = 0
                while True:
                    try:
                        nombre, comando, _ = winreg.EnumValue(clave, i)
                        entradas.append({"origen": etiqueta, "nombre": nombre, "comando": comando})
                        i += 1
                    except OSError:
                        break
        except PermissionError:
            entradas.append({"origen": etiqueta, "nombre": "(sin acceso)", "comando": "requiere ejecutar como administrador"})
        except FileNotFoundError:
            pass
    return entradas


# ============================================================
# 5) HERRAMIENTAS AVANZADAS
#    Estas operaciones son más invasivas que la limpieza básica
#    (pueden tardar minutos o requerir reinicio), así que la interfaz
#    las deja siempre detrás de una confirmación explícita del usuario
#    y nunca se ejecutan solas al arrancar Windows.
# ============================================================

def analizar_espacio_carpetas(ruta, n=10):
    """Devuelve las N subcarpetas de primer nivel de 'ruta' que más ocupan, en MB.

    Es de solo lectura: no borra nada, sirve para que el usuario decida qué
    limpiar manualmente.
    """
    resultados = []
    try:
        subcarpetas = [
            os.path.join(ruta, nombre) for nombre in os.listdir(ruta)
            if os.path.isdir(os.path.join(ruta, nombre))
        ]
    except (PermissionError, OSError) as e:
        return [], f"No se pudo leer '{ruta}': {e}"

    for carpeta in subcarpetas:
        try:
            mb = tamano_carpeta(carpeta) / (1024 ** 2)
            resultados.append((os.path.basename(carpeta), mb))
        except OSError:
            pass

    resultados.sort(key=lambda x: x[1], reverse=True)
    return resultados[:n], None


def es_administrador():
    """True si el proceso actual se está ejecutando como administrador."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def reiniciar_como_administrador():
    """Relanza este mismo programa pidiendo permisos de administrador (UAC).

    Devuelve True si Windows aceptó la petición de lanzamiento (el usuario
    todavía puede cancelar el propio diálogo de UAC, en cuyo caso la nueva
    instancia simplemente no llega a abrirse). No cierra la instancia actual:
    eso lo debe hacer quien llame a esta función tras comprobar el resultado.
    """
    try:
        parametros = " ".join(f'"{arg}"' for arg in sys.argv)
        resultado = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, parametros, None, 1)
        return resultado > 32
    except Exception:
        return False


def ejecutar_sfc_scan():
    """Ejecuta 'sfc /scannow' (verifica y repara archivos de sistema).

    Requiere permisos de administrador y puede tardar varios minutos.
    Se debe lanzar siempre desde un botón con confirmación previa, nunca
    de forma automática, precisamente porque es una operación pesada.
    """
    try:
        resultado = subprocess.run(
            ["sfc", "/scannow"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1800,
        )
        salida = (resultado.stdout or "") + (resultado.stderr or "")
        return resultado.returncode == 0, salida.strip() or "Sin salida del comando."
    except subprocess.TimeoutExpired:
        return False, "El análisis tardó demasiado y se canceló (más de 30 minutos)."
    except Exception as e:
        return False, f"No se pudo ejecutar sfc /scannow: {e}"


def resetear_tcpip():
    """Ejecuta 'netsh int ip reset' para restablecer la configuración TCP/IP.

    Requiere permisos de administrador y normalmente pide reiniciar el
    equipo para que el cambio surta efecto. Solo debe lanzarse a mano,
    tras confirmar, cuando hay problemas de red persistentes.
    """
    try:
        resultado = subprocess.run(
            ["netsh", "int", "ip", "reset"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        salida = (resultado.stdout or "") + (resultado.stderr or "")
        return resultado.returncode == 0, salida.strip() or "Sin salida del comando."
    except Exception as e:
        return False, f"No se pudo ejecutar netsh int ip reset: {e}"


def abrir_desinstalador_windows():
    """Abre el panel nativo de Windows 'Aplicaciones instaladas'.

    Deliberadamente NO se implementa un desinstalador propio: desinstalar
    un programa equivocado es un riesgo real, y Windows ya ofrece una forma
    segura y con confirmación propia de hacerlo.
    """
    try:
        os.startfile("ms-settings:appsfeatures")
        return True
    except OSError:
        return False


# ============================================================
# 6) BÚSQUEDA DE ARCHIVOS DUPLICADOS
#    Solo lectura al buscar. Al borrar, SIEMPRE se envían a la papelera
#    de reciclaje (nunca borrado permanente), para que sea reversible si
#    el usuario marca por error el archivo que quería conservar.
# ============================================================

def _hash_parcial(ruta, tam=65536):
    """Hash de los primeros bytes de un archivo: descarta rápido a los que no coinciden."""
    try:
        with open(ruta, "rb") as f:
            return hashlib.sha256(f.read(tam)).hexdigest()
    except OSError:
        return None


def _hash_completo(ruta):
    """Hash del contenido completo del archivo, para confirmar que son idénticos de verdad."""
    h = hashlib.sha256()
    try:
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloque)
        return h.hexdigest()
    except OSError:
        return None


def buscar_duplicados(ruta):
    """Busca archivos con contenido idéntico dentro de 'ruta' (recursivo).

    Estrategia en 3 pasos para no tener que hashear todo el disco:
      1) Agrupa por tamaño de archivo (tamaños únicos no pueden ser duplicados).
      2) Entre los que comparten tamaño, agrupa por hash de los primeros 64 KB.
      3) Entre esos, calcula el hash completo para confirmar que son iguales.

    Devuelve (grupos, error). Cada grupo es una lista de dicts
    {ruta, tamano_mb, modificado} con 2 o más archivos idénticos.
    No borra ni mueve nada: es de solo lectura.
    """
    if not os.path.isdir(ruta):
        return [], f"'{ruta}' no es una carpeta válida."

    por_tamano = {}
    for dirpath, _, filenames in os.walk(ruta):
        for nombre in filenames:
            ruta_archivo = os.path.join(dirpath, nombre)
            try:
                tam = os.path.getsize(ruta_archivo)
            except OSError:
                continue
            if tam == 0:
                continue  # los archivos vacíos no son duplicados útiles que limpiar
            por_tamano.setdefault(tam, []).append(ruta_archivo)

    por_hash_parcial = {}
    for tam, rutas in por_tamano.items():
        if len(rutas) < 2:
            continue
        for ruta_archivo in rutas:
            h = _hash_parcial(ruta_archivo)
            if h:
                por_hash_parcial.setdefault((tam, h), []).append(ruta_archivo)

    grupos = []
    for rutas in por_hash_parcial.values():
        if len(rutas) < 2:
            continue
        por_hash_completo = {}
        for ruta_archivo in rutas:
            h = _hash_completo(ruta_archivo)
            if h:
                por_hash_completo.setdefault(h, []).append(ruta_archivo)
        for rutas_iguales in por_hash_completo.values():
            if len(rutas_iguales) < 2:
                continue
            grupo = []
            for r in rutas_iguales:
                try:
                    stat = os.stat(r)
                    grupo.append({
                        "ruta": r,
                        "tamano_mb": stat.st_size / (1024 ** 2),
                        "modificado": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                except OSError:
                    pass
            if len(grupo) >= 2:
                grupos.append(grupo)

    grupos.sort(key=lambda g: g[0]["tamano_mb"] * (len(g) - 1), reverse=True)
    return grupos, None


DEBUG_LOG_FILE = os.path.join(os.path.expanduser("~"), "diagnostico_pc_debug.log")


def _registrar_debug(mensaje):
    try:
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}\n")
    except OSError:
        pass


def enviar_a_papelera(ruta):
    """Envía un archivo a la papelera de reciclaje. Reversible: no es un borrado permanente."""
    if not os.path.isfile(ruta):
        return False, "El archivo ya no existe."
    try:
        send2trash.send2trash(ruta)
        return True, "Enviado a la papelera de reciclaje."
    except Exception as e:
        detalle = (
            f"Fallo enviando a la papelera.\n"
            f"  ruta: {ruta!r}\n"
            f"  longitud ruta: {len(ruta)}\n"
            f"  tipo excepción: {type(e).__name__}\n"
            f"  repr: {e!r}\n"
            f"  winerror: {getattr(e, 'winerror', None)}\n"
            f"  args: {e.args!r}"
        )
        _registrar_debug(detalle)
        return False, f"No se pudo enviar a la papelera: {e}"


# ============================================================
# 7) SOFTWARE INSTALADO
# ============================================================

_CLAVES_DESINSTALACION = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def listar_programas_instalados():
    """Lista los programas instalados que aparecen en el registro de Windows.

    Incluye tanto la clave de 64 bits como su equivalente "Wow6432Node" para
    que los programas de 32 bits instalados en un Windows de 64 bits también
    aparezcan.
    """
    vistos = set()
    programas = []
    for hkey, uninstall_key in _CLAVES_DESINSTALACION:
        try:
            with winreg.OpenKey(hkey, uninstall_key) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                nombre = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                                editor = winreg.QueryValueEx(subkey, "Publisher")[0]
                                clave = (nombre, version, editor)
                                if nombre and editor != "Microsoft Corporation" and clave not in vistos:
                                    vistos.add(clave)
                                    programas.append({"nombre": nombre, "version": version, "editor": editor})
                            except OSError:
                                pass
                    except OSError:
                        pass
        except OSError:
            pass
    return sorted(programas, key=lambda p: p['nombre'].lower())


def desinstalar_programa(nombre):
    """Busca el comando de desinstalación de un programa y lo ejecuta."""
    for hkey, uninstall_key in _CLAVES_DESINSTALACION:
        try:
            with winreg.OpenKey(hkey, uninstall_key) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                if winreg.QueryValueEx(subkey, "DisplayName")[0] == nombre:
                                    uninstall_string = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                    subprocess.Popen(uninstall_string, shell=True)
                                    return True, f"Se ha iniciado el desinstalador de '{nombre}'."
                            except OSError:
                                pass
                    except OSError:
                        pass
        except OSError:
            pass
    return False, f"No se encontró el desinstalador para '{nombre}'."
