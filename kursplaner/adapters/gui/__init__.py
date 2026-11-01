"""GUI-Adapter des Kursplaners.

Einzige Stelle, die den bw-gui-Pfad setzt: Python führt diese Datei aus, bevor ein
Modul des Pakets geladen wird, die Module importieren ``bw_gui`` deshalb ganz normal.
Die Tests setzen den Pfad in ``tests/conftest.py``, weil sie ``bw_gui`` teils vor dem
Paket importieren. ``bw_libs`` wird auch von anderen Programmen genutzt und sorgt selbst dafür.
"""

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
