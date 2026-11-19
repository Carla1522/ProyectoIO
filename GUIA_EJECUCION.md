# Guia de Instalacion y Ejecucion en Otra PC — ECUAPROJECT

Esta guia detalla los requisitos, librerias, comandos paso a paso y soluciones rapidas para ejecutar **ECUAPROJECT** en otra computadora (Windows, Linux o macOS).

---

## 1. Requisitos previos

- **Python:** version `3.10` o superior (probado en Python `3.11` y `3.12`).
  - En Windows, al instalar Python desde [python.org](https://www.python.org/downloads/), marca la casilla **"Add python.exe to PATH"**.
- **Conexion a internet** solo durante la instalacion inicial de paquetes (o si conectas el Copiloto IA con API externa).

Verifica tu version de Python en la terminal:

```powershell
python --version
```

*(En Linux/macOS puede ser `python3 --version`.)*

---

## 2. Preparar la carpeta del proyecto

1. Clona o copia la carpeta `ProyectoIO` en la nueva PC.
2. **No copies `.venv` ni `__pycache__`** de una PC a otra: los entornos virtuales no son portables entre equipos. Si venian en una copia, borralos antes y crealos de nuevo con los pasos de abajo.
3. Abre una terminal dentro de la carpeta raiz `ProyectoIO` (donde esta `app.py` y `requirements.txt`).

---

## 3. Crear entorno virtual e instalar librerias

### Opcion A: Windows (PowerShell — recomendado)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Si PowerShell bloquea `Activate.ps1` por politica de ejecucion, puedes habilitarlo para tu usuario con:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> O ejecutar directamente sin activar el entorno usando `.\.venv\Scripts\python.exe` y `.\.venv\Scripts\pip.exe`.

### Opcion B: Windows (CMD / Simbolo del sistema)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Opcion C: Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Librerias incluidas en `requirements.txt`

Si por alguna razon necesitas instalarlas manualmente en un solo comando:

```bash
pip install "streamlit>=1.49" "pandas>=2.0" "plotly>=5.20" "scipy>=1.11" "openpyxl>=3.1" "reportlab>=4.0" "pdfplumber>=0.11" "requests>=2.31"
```

| Libreria | Version minima | Para que se usa en ECUAPROJECT |
|---|---|---|
| `streamlit` | `1.49` | Interfaz web interactiva (`app.py` y `ui/`) |
| `pandas` | `2.0` | Tablas editables, manipulacion de datos e importacion CSV |
| `plotly` | `5.20` | Diagrama de red CPM, Gantt, campana normal y flujo de caja |
| `scipy` | `1.11` | Distribucion normal (`cdf` y `ppf`) para riesgo PERT |
| `openpyxl` | `3.1` | Exportacion e importacion de archivos Excel (`.xlsx`) |
| `reportlab` | `4.0` | Generacion del informe PDF ejecutivo y Gantt vectorial |
| `pdfplumber` | `0.11` | Lectura e importacion de tablas en archivos PDF digitales |
| `requests` | `2.31` | Llamadas HTTP al Copiloto IA (Gemini / OpenAI) |

---

## 5. Como ejecutar la aplicacion

Con el entorno virtual activado:

```bash
streamlit run app.py
```

O directamente en Windows sin activar `.venv`:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Luego abre en tu navegador:

- **`http://localhost:8501`**

*(Nota: `.streamlit/config.toml` tiene `headless = true`, por lo que en algunos equipos el navegador no se abrira automaticamente; si quieres que intente abrirse solo, ejecuta `streamlit run app.py --server.headless false`.)*

Para detener el servidor en cualquier momento, presiona **`Ctrl + C`** en la terminal.

---

## 6. Configurar el Copiloto IA (opcional)

Sin clave de API, la aplicacion funciona completa en **modo local** (plantillas por sector + catalogo normativo ecuatoriano + planificacion manual PERT).

Si deseas activar la entrevista conversacional con IA en otra PC, crea el archivo `.streamlit/secrets.toml` dentro del proyecto:

```toml
GEMINI_API_KEY = "tu_clave_de_gemini"
# AI_PROVIDER = "gemini"   # auto | gemini | openai | local
# AI_MODEL = "gemini-flash-latest"
```

O usa variables de entorno antes de lanzar Streamlit:

```powershell
# PowerShell (Gemini)
$env:GEMINI_API_KEY="tu_clave"
streamlit run app.py

# PowerShell (OpenAI)
$env:OPENAI_API_KEY="tu_clave"
streamlit run app.py
```

*(Por seguridad, `.streamlit/secrets.toml` esta excluido en `.gitignore` y nunca debe subirse a repositorios publicos.)*

---

## 7. Verificar que todo quedo funcionando (pruebas)

Ejecuta la suite de **94 pruebas unitarias** para comprobar el motor CPM/PERT, presupuesto, validacion, seguridad, importadores y exportadores:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## 8. Archivos de prueba incluidos

Si quieres probar la carga de archivos en el panel lateral **`Guardar / cargar proyecto`**, tienes ejemplos listos en la carpeta `ejemplos/`:

- `ejemplos/ejercicio_1_consultorio_quito.xlsx` (Excel)
- `ejemplos/ejercicio_2_software_pert.csv` (CSV)
- `ejemplos/ejercicio_3_cafeteria_ambato.pdf` (PDF tabular digital)

Formatos aceptados para importar: **`.json`, `.xlsx`, `.csv` y `.pdf`** (maximo `2 MB`).
