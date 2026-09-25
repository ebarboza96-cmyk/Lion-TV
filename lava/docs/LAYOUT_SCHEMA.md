# Esquema de datos del test-fit LAVA

Todas las herramientas (validador, plano 2D, recorrido 3D, informe) leen los mismos dos archivos:

- `data/existing.json`: condiciones existentes extraídas del PDF de Marna's (no se edita salvo corrección de levantamiento).
- `data/layout.json`: propuesta LAVA (demoliciones, muros nuevos, equipos, mobiliario, rutas).

## Sistema de coordenadas

- Unidades: metros.
- Origen: eje de columnas **A** (X = 0) y eje de fila **1** (Y = 0, coincide con la cara exterior del muro norte).
- X crece hacia la fachada / entrada (este). Y crece hacia el ala de servicio (sur).
- "Norte" = parte superior del PDF original (no es norte geográfico).
- Rectángulos: `[x0, y0, x1, y1]` alineados a ejes.

Referencias útiles (de `existing.json`):

| Elemento | Coordenadas |
|---|---|
| Franja principal (cocina + salón) interior | X −0.085 … 16.285, Y 0.116 … 4.986 (4.87 m de fondo) |
| Ala de servicio, tramo norte | X −0.085 … 4.11, Y 4.986 … 6.456 |
| Ala de servicio, tramo sur | X 0.0 … 4.51, Y 6.456 … 11.486 |
| División cocina/barra actual (a demoler) | X 6.298 … 6.398 |
| Puerta principal (doble, 2.00 m) | X 16.3, Y 1.643 … 3.643, abre hacia adentro |
| Columna B1 (sobresale al salón) | X 7.5 … 8.1, Y hasta 0.30 |
| Columna A2 (sobresale al ala) | X −0.315 … 0.315, Y 8.186 … 8.816 |
| Envolvente columna A1 + ductos | X −0.865 … 0.865, Y −0.564 … 0.866 |

## `layout.json`

```jsonc
{
  "meta": {"name": "...", "strategy": "...", "version": "..."},
  "demolish": [ {"id": "IP-KB", "note": "..."} ],            // ids de existing.walls (o {"id","rect"} parcial)
  "new_walls": [ {"id": "NW1", "rect": [...], "type": "glass_partition|partition|low_wall",
                  "role": "kitchen_dining_partition", "h": 2.7, "base_h": 1.0, "note": "..."} ],
  "new_openings": [ {"id": "ND1", "type": "door|double_acting_door|sliding_door|service_door|pass_window|opening",
                     "rect": [...], "width": 0.9, "hinge": [x,y], "closed_to": [x,y], "swing_to": [x,y],
                     "label": "P-1", "conditional": false, "note": "..."} ],
  "zones": [ {"id": "A|B|C|D|E", "name": "...", "poly": [[x,y],...], "color": "#hex", "prep": true} ],
  "equipment": [ {"id": "H1", "key": "parrilla", "label": "Parrilla 150", "cat": "fire|cold|prep|wash|storage|smoker|bar|delivery|hood|misc",
                  "rect": [...], "h": 0.9, "front": "N|S|E|W|none", "clear": 1.2, "tbv": true,
                  "overhead": false, "stack_with": "id", "note": "..."} ],
  "tables": [ {"id": "T1", "rect": [...], "seats": 2, "type": "2top|4top", "joinable_with": ["T2"]} ],
  "chairs": [ {"id": "CH1", "rect": [...], "table": "T1", "facing": "N|S|E|W"} ],
  "banquettes": [ {"id": "BQ1", "rect": [...], "seats": 8, "back": "N|S|E|W"} ],
  "points": {"entrance": [x,y], "...": [x,y]},
  "routes": [ {"id": "R-clean", "kind": "clean|dirty|guest|server|delivery|fuel", "label": "...",
               "pts": [[x,y],...], "min_width": 1.0} ],
  "checks": [ ["entrance", "barra_front", 1.1] ],
  "decor": [ {"type": "slat_wall|sign|poster|sconce|pendant|planter|firewood_niche", "rect": [...], "text": "LAVA", "h": 2.4} ],
  "notes": ["..."]
}
```

### Claves de equipo (`key`)

Obligatorias: `fridge_2d`, `freezer_1d`, `mesa_fria`, `mesa_1`, `mesa_2`, `shelf_4`, `sink_2t`, `mop_sink`, `handwash`,
`parrilla`, `cocina_4q`, `plancha`, `freidora_1`, `freidora_2`, `hood`, `smoker`, `fuel_storage`, `barra`, `pos`, `pass`,
`delivery_staging`. Opcionales: `holding`, `mesa_opt`, `trash`, `ice`, `back_bar`, `host`.

`front` indica la cara de trabajo; `clear` el despeje libre exigido delante de ella (el validador lo comprueba).
`overhead: true` = elemento en altura (campana, repisa de pase) que no ocupa piso.
`tbv: true` = DIMENSION TO VERIFY.

## Herramientas

```bash
python3 tools/validate.py data/layout.json          # choques, despejes, anchos de ruta, campana, visibilidad
python3 tools/render_png.py data/layout.json out.png  # vista rápida de trabajo
python3 tools/overlay_check.py <pdf> out.png         # superpone la geometría sobre el PDF original
```
