#!/usr/bin/env python3
"""
clear_pycache.py
Elimina todos los directorios __pycache__ y archivos .pyc del proyecto
EscanerWifi, forzando a Python a recompilar desde los archivos .py corregidos.

Uso:
    python clear_pycache.py
    python clear_pycache.py /ruta/personalizada/EscanerWifi
"""

import sys
import os
import shutil

def limpiar_pycache(raiz: str):
    eliminados_dirs  = 0
    eliminados_files = 0

    for dirpath, dirnames, filenames in os.walk(raiz, topdown=True):
        # Eliminar carpetas __pycache__ en su totalidad
        if "__pycache__" in dirnames:
            pycache_path = os.path.join(dirpath, "__pycache__")
            try:
                shutil.rmtree(pycache_path)
                print(f"  🗑  {pycache_path}")
                eliminados_dirs += 1
            except Exception as e:
                print(f"  ⚠️  No se pudo eliminar {pycache_path}: {e}")
            dirnames.remove("__pycache__")   # evitar descender dentro

        # Eliminar .pyc huérfanos que estén fuera de __pycache__
        for fname in filenames:
            if fname.endswith((".pyc", ".pyo")):
                fpath = os.path.join(dirpath, fname)
                try:
                    os.remove(fpath)
                    print(f"  🗑  {fpath}")
                    eliminados_files += 1
                except Exception as e:
                    print(f"  ⚠️  No se pudo eliminar {fpath}: {e}")

    print(f"\n✅ Eliminados: {eliminados_dirs} carpetas __pycache__"
          f" + {eliminados_files} archivos .pyc/.pyo")
    print("   Python regenerará el __pycache__ automáticamente al próximo arranque.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raiz = sys.argv[1]
    else:
        # Por defecto sube un nivel desde donde vive este script
        raiz = os.path.abspath(os.path.dirname(__file__))

    if not os.path.isdir(raiz):
        print(f"❌ Directorio no encontrado: {raiz}")
        sys.exit(1)

    print(f"🔍 Limpiando __pycache__ en: {raiz}\n")
    limpiar_pycache(raiz)