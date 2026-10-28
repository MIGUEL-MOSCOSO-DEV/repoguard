# RepoGuard

A local Git repository inspector for staged secrets, oversized files and repository hygiene.

[![CI](https://github.com/MIGUEL-MOSCOSO-DEV/repoguard/actions/workflows/ci.yml/badge.svg)](https://github.com/MIGUEL-MOSCOSO-DEV/repoguard/actions/workflows/ci.yml) · [Descargas](https://github.com/MIGUEL-MOSCOSO-DEV/repoguard/releases/latest) · [MIT](LICENSE)

Inspecciona el contenido que está preparado para Git antes de subirlo. Trabaja sobre los blobs del índice y reporta ubicaciones, sin mostrar los valores de posibles credenciales.

## Qué incluye

- Detección de claves privadas, tokens de GitHub, claves de AWS, secretos de Stripe y asignaciones sospechosas.
- Avisos de archivos de entorno, archivos grandes, conflictos y metadatos ausentes.
- Salida legible o JSON, alcance preparado o índice completo y exclusiones explícitas.
- Hook pre-commit opcional, sin sobrescribir uno existente ni cambiar core.hooksPath.

## Descargar para Windows

En [Releases](https://github.com/MIGUEL-MOSCOSO-DEV/repoguard/releases/latest) encontrarás RepoGuard.exe y su archivo SHA256SUMS.txt. Es una aplicación portable para Windows 10/11 de 64 bits: no necesita instalar Python ni permisos de administrador. Ejecuta el programa desde tu terminal; --help muestra los comandos disponibles. Los ejecutables no tienen firma digital.

## Ejecutar desde el código

Necesitas Python 3.11 o superior. También necesitas Git instalado y disponible en PATH. Crea un entorno virtual para mantener las dependencias separadas.

```sh
git clone https://github.com/MIGUEL-MOSCOSO-DEV/repoguard.git
cd repoguard
python -m venv .venv
```

En Windows:

```powershell
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe launch.py --help
```

En Linux o macOS puedes usar .venv/bin/python. Las pruebas de la lógica se ejecutan en Windows y Linux.

## Uso

Dentro de un repositorio, ejecuta repoguard scan para revisar cambios preparados. --all revisa todos los archivos del índice; --json produce salida estructurada y --strict hace fallar también las advertencias. --path RUTA va antes de scan si quieres inspeccionar otro directorio. No lee archivos sin seguimiento ni versiones anteriores del historial.

- repoguard init crea .repoguard.toml con max_file_mb = 5 e ignore = []. Puedes cambiar el límite entre 1 y 100 MB y añadir patrones de rutas a ignore.
- repoguard hook --install crea .git/hooks/pre-commit solo si no hay otro hook ni una configuración core.hooksPath. El hook usa la instalación actual: conserva ese ejecutable o entorno.
- Códigos de salida: 0 sin fallos de las reglas activas; 1 hallazgos que bloquean; 2 error de ejecución o configuración.
- El modo binario se detecta por bytes nulos; los archivos que superan el límite se reportan sin analizar su contenido.

## Datos y privacidad

La instalación comienza sin registros de demostración. La inspección es local. No envía archivos a un servicio ni almacena los posibles valores detectados. La configuración opcional queda en .repoguard.toml y el hook, si lo instalas, en el directorio Git.

## Alcance actual

Es un detector por patrones, no una garantía de ausencia de secretos ni un antivirus. Puede producir falsos positivos y omitir formatos desconocidos, archivos binarios o contenido excluido. No revoca credenciales, reescribe historial ni modifica los archivos inspeccionados. Si un secreto se publicó, rótalo en el proveedor correspondiente. Git debe estar instalado para usar el programa, incluido el ejecutable portable.

## Desarrollo y pruebas

```sh
python -m pip install . -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
```

Las pruebas usan directorios y datos temporales. GitHub Actions verifica formato y pruebas en Windows y Linux y construye un ejecutable de Windows como artefacto del workflow. No hay una aplicación web ni un servidor remoto requerido.

## Generar el ejecutable

Desde Windows, con las dependencias de desarrollo instaladas:

```sh
python -m PyInstaller --noconfirm --clean --onefile --name RepoGuard launch.py
```

El resultado queda en dist/RepoGuard.exe. PyInstaller construye para el sistema donde se ejecuta; para generar Windows necesitas construir desde Windows. Los archivos de compilación y los datos locales se excluyen de Git.

## Estructura

scanner.py consulta el índice y analiza blobs; cli.py implementa salida, configuración e instalación opcional del hook.

## Contribuir

Abre un issue con el sistema operativo, la versión y los pasos para reproducir el problema. No incluyas archivos privados, contraseñas ni bases reales. Para cambiar reglas de negocio, añade una prueba que describa el caso.

Creado por [Miguel Moscoso](https://github.com/MIGUEL-MOSCOSO-DEV). Licencia MIT.
