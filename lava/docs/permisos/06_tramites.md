# 06 · Trámites y permisos

**LAVA – Contemporary Fire & BBQ** — local ex-Marna's, Terrazas Lindora (centro comercial abierto en régimen de condominio), Lindora, Santa Ana, San José, Costa Rica  
Anteproyecto v3.0 · 2026-09-25 · documento generado desde los datos del proyecto (`tools/permit_docs.py`)

> **ANTEPROYECTO / PRELIMINAR** — no es un documento constructivo ni una declaración de cumplimiento: todo lo aquí indicado es **a validar por el profesional responsable** (CFIA) y por las ingenierías. Las citas normativas provienen mayormente de fuentes secundarias y se marcan "verificar".

Paso a paso para pasar del anteproyecto a la apertura: quién hace cada trámite, ante qué institución y con qué documentos. Requisitos tomados de fuentes secundarias (sitios municipales e institucionales vistos por buscador): **confirmar los requisitos vigentes con cada institución** antes de iniciar.

## 1. Resumen

| Paso | Trámite | Ante quién | Responsable | Cuándo |
|---:|---|---|---|---|
| 1 | Aprobación del condominio y del propietario / arrendador | Administración / asamblea; propietario registral | Cliente | Antes del APC |
| 2 | Certificado de uso de suelo | Municipalidad de Santa Ana | Cliente | Antes del APC y de la patente |
| 3 | Levantamiento en sitio y ajuste del anteproyecto | — | Arquitecto | Antes de firmar |
| 4 | Contratos de consultoría y planos constructivos firmados | CFIA (APC) | Arquitecto + ingenieros | Paralelo a 1–2 |
| 5 | Revisión institucional en el APC (remodelación) | CFIA, Ministerio de Salud (declaración jurada), Bomberos | Arquitecto | Con 1, 2 y 4 listos |
| 6 | Licencia municipal de construcción | Municipalidad de Santa Ana (APC-M) | Arquitecto + cliente | Después de 5 |
| 7 | Póliza de riesgos del trabajo de la obra, bitácora digital y dirección técnica | INS · CFIA | Contratista · arquitecto | Antes de iniciar obras |
| 8 | Obra, inspecciones y pruebas | Bomberos, municipalidad, proveedor de supresión | Contratista + director técnico | Durante la obra |
| 9 | Informe técnico de la instalación de gas | Bomberos o profesional / inspector acreditado | Ing. mecánico / instalador | Al terminar el gas |
| 10 | Permiso Sanitario de Funcionamiento (PSF) | Ministerio de Salud — Área Rectora de Santa Ana | Operador | Antes de abrir |
| 11 | Patente municipal (licencia de actividad lucrativa) | Municipalidad de Santa Ana | Operador | Después de 10 |
| 12 | Licencia de expendio de bebidas alcohólicas clase C | Municipalidad de Santa Ana | Operador | Con / después de 11 |
| 13 | Permiso de rótulo | Municipalidad + condominio | Cliente | Antes de instalar el rótulo |
| 14 | Arranque de operación | INS, CCSS, Hacienda, Salud | Operador | Antes de abrir |

## 2. Detalle por paso

### Paso 1. Aprobación del condominio y del propietario / arrendador

**Ante quién:** Administración / asamblea; propietario registral · **Responsable:** Cliente · **Cuándo:** Antes del APC  
**Referencia:** Ley 7933 Reguladora de la Propiedad en Condominio arts. 16 y 27 (reforma Ley 10229); reglamento interno; Ley 7527 (arrendamiento) — verificar

Documentos:

- Carta de solicitud (documento 08) con el anteproyecto (láminas A-101…E-101, memoria 01 y especificaciones 02).
- Autorización escrita del propietario registral o arrendador para remodelar y cambiar el uso (la patente también la pide).
- Copia del reglamento del condominio y del manual de inquilinos (requisitos de campanas, grasas, gas, horarios, rótulos).

Notas:

- Obras en elementos comunes o que los afectan requieren aprobación: cubierta y losa (ductos, ventiladores, chimenea), ventana sur (PS-1), fachada y rótulos, conexión a la red de gas, uso de baños comunes y cuarto de basura.
- Si el reglamento restringe el destino (café → restaurante con fuego sólido), el cambio de destino requiere ≥2/3 del valor (art. 27 reformado, verificar).
- El cliente no tiene el plano del centro comercial: pedir a la administración el plano de conjunto con baños comunes, cuarto de basura, acometidas (gas, electricidad, agua), cubierta y sistemas de protección contra incendios.

### Paso 2. Certificado de uso de suelo

**Ante quién:** Municipalidad de Santa Ana · **Responsable:** Cliente · **Cuándo:** Antes del APC y de la patente  
**Referencia:** Municipalidad de Santa Ana — Usos de suelo; Plan Regulador (1991 y reformas / nuevo plan en adopción) — verificar

Documentos:

- Formulario en línea; número de finca filial (folio real) y plano catastrado.
- Actividad: "restaurante con venta de bebidas alcohólicas" (clase C).

Notas:

- Lo exigen la licencia de construcción y la patente. Confirmar qué plan regulador rige al presentar.

### Paso 3. Levantamiento en sitio y ajuste del anteproyecto

**Ante quién:** — · **Responsable:** Arquitecto · **Cuándo:** Antes de firmar  
**Referencia:** —

Documentos:

- Formulario 07 completo, fotos y medidas; fichas técnicas de equipos.

Notas:

- Actualizar `data/existing.json` / `data/layout.json` con lo medido y regenerar láminas y documentos.

### Paso 4. Contratos de consultoría y planos constructivos firmados

**Ante quién:** CFIA (APC) · **Responsable:** Arquitecto + ingenieros · **Cuándo:** Paralelo a 1–2  
**Referencia:** Ley 833 art. 83; Reglamento de Contratación de Servicios de Consultoría del CFIA — verificar

Documentos:

- Contrato de consultoría registrado por cada profesional (arquitectura; mecánica: extracción, gas, hidrosanitario, supresión; electricidad; estructural si hay penetraciones y soportes).
- Planos constructivos firmados digitalmente: arquitectura (A-1xx…A-3xx), seguridad humana (A-104), mecánica (M-101/M-102 + planta de cubierta), eléctrica (E-101), estructural si aplica; especificaciones y memorias de cálculo.

Notas:

- Es obra mayor: no aplica la boleta de obra menor (modifica sistemas eléctricos y mecánicos).

### Paso 5. Revisión institucional en el APC (remodelación)

**Ante quién:** CFIA, Ministerio de Salud (declaración jurada), Bomberos · **Responsable:** Arquitecto · **Cuándo:** Con 1, 2 y 4 listos  
**Referencia:** DE 36550-MP-MIVAH-S-MEIC reformado por DE 43318; RNPCI 2023 (Bomberos); DE 43318 declaración jurada Salud ≤300 m² — verificar

Documentos:

- Proyecto en APC modalidad REMODELACIÓN con estado existente (A-102) y propuesto.
- Declaración jurada de los profesionales ante Salud (área del local 107.65 m² ≤ 300 m²; confirmar área tasada).
- Formulario y memoria de Bomberos: lámina A-104 + memoria 03 + láminas de gas, extracción y supresión.
- Uso de suelo, autorización del condominio y del propietario (pasos 1–2).

Notas:

- CFIA, Salud y Bomberos revisan en paralelo; las observaciones se atienden por reingreso.
- La declaración jurada de Salud obliga a cumplir el DE 37308-S: resolver antes baños comunes (autorización), residuos y lavamanos.

### Paso 6. Licencia municipal de construcción

**Ante quién:** Municipalidad de Santa Ana (APC-M) · **Responsable:** Arquitecto + cliente · **Cuándo:** Después de 5  
**Referencia:** Ley 833 art. 74; Municipalidad de Santa Ana — Permisos de construcción (APC-M) — verificar

Documentos:

- Planos aprobados en el APC; uso de suelo conforme; póliza de riesgos del trabajo de la obra (INS).
- Propietario y solicitante al día con tributos municipales y CCSS; pago del impuesto de construcción (≈1 % del valor tasado).

Notas:

- Plazo reportado ≈15 días hábiles. No se puede iniciar la obra sin licencia.

### Paso 7. Póliza de riesgos del trabajo de la obra, bitácora digital y dirección técnica

**Ante quién:** INS · CFIA · **Responsable:** Contratista · arquitecto · **Cuándo:** Antes de iniciar obras  
**Referencia:** Reglamento Especial de la Bitácora (CFIA); Ley 6727 / INS riesgos del trabajo — verificar

Documentos:

- Bitácora digital abierta en el APC (≈₡10 000 con la tasación).
- Director técnico o inspector designado.
- Póliza RT de los trabajadores de la obra.

Notas:

- La bitácora se cierra ≤30 días después de terminar y se custodia 10 años.

### Paso 8. Obra, inspecciones y pruebas

**Ante quién:** Bomberos, municipalidad, proveedor de supresión · **Responsable:** Contratista + director técnico · **Cuándo:** Durante la obra  
**Referencia:** RNPCI 2023; NFPA 96 / 17A / 54 — verificar

Documentos:

- Pruebas: hermeticidad del gas, aceptación de la supresión (con corte de gas y energía), balance de extracción y reposición, pruebas eléctricas, estanqueidad de desagües.
- Certificados del proveedor de supresión y del instalador de gas.
- Planos conforme a obra.

Notas:

- Horario de obras, acarreos y protección de áreas comunes según el reglamento del condominio (08).

### Paso 9. Informe técnico de la instalación de gas

**Ante quién:** Bomberos o profesional / inspector acreditado · **Responsable:** Ing. mecánico / instalador · **Cuándo:** Al terminar el gas  
**Referencia:** DE 41150-MINAE-S y DE 41151-MINAE-S (RTCR 490:2017); RTCR 482:2015 — verificar

Documentos:

- Informe técnico de inspección de la instalación de gas (tubería, reguladores, conectores, artefactos, detector).

Notas:

- Se exige para el PSF a establecimientos con GLP; la red del centro comercial puede ser GLP o gas natural: Red de gas del centro comercial (tipo de gas y presión: VERIFY). Confirmar qué informe aplica.

### Paso 10. Permiso Sanitario de Funcionamiento (PSF)

**Ante quién:** Ministerio de Salud — Área Rectora de Santa Ana · **Responsable:** Operador · **Cuándo:** Antes de abrir  
**Referencia:** DE 43432-S (PSF, Anexo 3 primera vez); DE 37308-S (servicios de alimentación) — verificar

Documentos:

- Declaración jurada (Anexo 3) del cumplimiento del DE 37308-S; clasificación por grupo de riesgo (CIIU 5610).
- Informe técnico de gas (paso 9).
- Autorización de uso de los baños comunes y del cuarto de basura (carta 08).

Notas:

- La inspección de Salud es posterior al permiso: la declaración debe ser veraz desde el primer día.
- Personal manipulador de alimentos con capacitación / carné vigente (verificar requisito actual).

### Paso 11. Patente municipal (licencia de actividad lucrativa)

**Ante quién:** Municipalidad de Santa Ana · **Responsable:** Operador · **Cuándo:** Después de 10  
**Referencia:** Municipalidad de Santa Ana — Licencia de actividad lucrativa — verificar

Documentos:

- Formulario único; cédulas del solicitante y del propietario; certificación literal de la propiedad; autorización del dueño registral.
- Póliza RT (INS); CCSS al día; PSF; inscripción en Hacienda; uso de suelo conforme; tributos municipales al día.

### Paso 12. Licencia de expendio de bebidas alcohólicas clase C

**Ante quién:** Municipalidad de Santa Ana · **Responsable:** Operador · **Cuándo:** Con / después de 11  
**Referencia:** Ley 9047 art. 4 (clase C) y art. 9; Reglamento a la Ley 9047; Municipalidad de Santa Ana — verificar

Documentos:

- Formulario con firma autenticada; CCSS, póliza RT y FODESAF al día; patente (paso 11).
- Planta con 14 mesas y 36 asientos, cocina equipada; menú con ≥10 opciones durante todo el horario.

Notas:

- Restricciones por zonificación y distancia (100 m de centros educativos, infantiles, de adultos mayores y de salud): confirmar cómo se aplican a la clase C en un centro comercial.
- Algunos reglamentos piden ≥8 mesas y ≥32 asientos y limitan banquetas de barra a 1/3 de las sillas (LAVA no tiene banquetas).

### Paso 13. Permiso de rótulo

**Ante quién:** Municipalidad + condominio · **Responsable:** Cliente · **Cuándo:** Antes de instalar el rótulo  
**Referencia:** Municipalidad de Santa Ana — Instalación de rótulos; reglamento del condominio — verificar

Documentos:

- Formulario; personería jurídica (≤1 mes); croquis a escala con estructura y anclaje; montaje fotográfico en la fachada; área del rótulo y frente del local; aprobación del condominio.

Notas:

- Circuito eléctrico propio del rótulo exterior (E-101).

### Paso 14. Arranque de operación

**Ante quién:** INS, CCSS, Hacienda, Salud · **Responsable:** Operador · **Cuándo:** Antes de abrir  
**Referencia:** INS, CCSS, Ministerio de Hacienda — verificar

Documentos:

- Póliza de riesgos del trabajo del personal; inscripción patronal (CCSS); inscripción tributaria.
- Plan de emergencias integrado al del condominio; contratos de limpieza de ductos (mensual por combustible sólido) y mantenimiento de supresión (semestral); control de plagas.

## 3. Instituciones que revisan el proyecto

| Institución | Qué revisa | Documentos del paquete |
|---|---|---|
| CFIA (APC) | Responsabilidad profesional, contratos, juego completo de planos | 00, 01, 02, todas las láminas |
| Ministerio de Salud | Declaración jurada (≤300 m²) de cumplimiento del DE 37308-S; luego el PSF | 01 §9, 02 §4/§11, A-106, M-101 |
| Bomberos | Seguridad humana, egreso, extintores, supresión, gas, extracción (RNPCI + NFPA) | 03, A-104, M-102, 04 |
| Municipalidad de Santa Ana | Uso de suelo, licencia de construcción, patente, licores, rótulo | 01, 06 |
| Condominio Terrazas Lindora | Obras en elementos comunes, servicios comunes, horarios, rótulos | 08 |

Banderas del anteproyecto (se mantienen literalmente en inglés en láminas y documentos):

- **EXTRACTION / MAKE-UP AIR / FIRE SUPPRESSION TO BE ENGINEERED**
- **SOLID-FUEL SMOKER - LOCATION / FLUE / FIRE CODE TO BE VALIDATED**
- **DIMENSION TO VERIFY**
- **VERIFY ON SITE**
