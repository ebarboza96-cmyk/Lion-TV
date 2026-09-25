"""Template for an extra sheet module (files starting with '_' are ignored by plan_svg.build()).

A sheet module lives in tools/sheets/<name>.py and exposes

    def sheets(ex, lay, val) -> list[dict(id, file, title, order, svg)]

`order` sorts the sheet in the PDF set (A-101 = 101 ... ; A-104 = 104, M-101 = 401, E-101 = 501 ...).
Preview only your module:  python3 tools/preview_sheet.py <module> <scratch_dir>
"""
from plan_svg import Sheet, sx, sy, text  # noqa: F401  (also: mtext, rect_el, poly_el, COL, S, MONO, DISPLAY, FONT, f, tw)


def sheets(ex, lay, val):
    s = Sheet(ex, lay, val, 'X000')
    s.frame_and_titleblock('X-000 · Plantilla', 'Ejemplo de lámina adicional', 'X-000')
    s.grid_axes()
    s.layer_existing()
    s.layer_new()
    s.add(text(sx(8.0), sy(8.0), 'contenido de la lámina', 4.0, weight='700'))
    s.side_panel([('h', 'Notas'), ('para', ['Texto de ejemplo.'])])
    return [{'id': 'X000', 'file': 'lava_X000_plantilla.svg', 'title': 'Plantilla', 'order': 999, 'svg': s.render()}]
