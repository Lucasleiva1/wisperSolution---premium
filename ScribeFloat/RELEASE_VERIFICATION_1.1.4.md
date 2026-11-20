# Verificación de Whisper Solution v1.1.4

Fecha: 20 de noviembre de 2026. Entorno comprobado: Windows 10 x64.

## Resultado

Las comprobaciones terminaron correctamente. El instalador real se ejecutó y se verificó la copia instalada, no solamente la aplicación en desarrollo.

- Versión del código: 1.1.4; ejecutable: 1.1.4.0; instalador: 1.1.4.
- Ejecutable independiente: arranque normal desde el acceso directo del escritorio, modelo cargado y ventana nativa visible con TOPMOST activado.
- Sonidos instalados idénticos a los originales por SHA-256. Decodificación y reproducción completadas: inicio de 0,887 segundos y parada de 8,030 segundos.
- Ventana: recuperación del panel y la cápsula frente a otra ventana TOPMOST, sin cambiar el foco ni la posición; orden de ajustes correcto.
- Botones: captura real del micrófono iniciada y detenida con dos clics en la cápsula; REC del panel también inicia y detiene la captura.
- Abrir panel, copiar, guardar, limpiar, configuración, ajustes visuales, cancelar, modo cápsula, minimizar y cerrar: correctos.
- Transcripción local sin Internet, usando CUDA y el modelo incluido. Frase generada localmente: «Esta es una prueba de transcripción. El micrófono funciona correctamente.» Reconocimiento correcto de la frase completa.
- Logo transparente aprobado por el usuario. Icono incrustado con siete resoluciones, entre 16 y 256 píxeles. El acceso directo usa el icono versionado instalado.
- Firma Ed25519 del actualizador, checksum SHA-256 y rechazo de una firma manipulada: correctos.

Las pruebas de botones ejecutan el código extraído del ejecutable instalado con el controlador de pruebas de Qt, usando sus archivos y modelo instalados. El pegado hacia otras aplicaciones se aisló para evitar escribir en ventanas del usuario; el portapapeles se restauró tras probar Copiar.

La compilación detectó una DLL ICU incompatible tomada de otra herramienta del entorno. Se corrigió la búsqueda de DLL durante la compilación y se agregó una comprobación que rechaza bibliotecas ajenas. La compilación final y la instalada superaron las pruebas.

## Artefacto

`Whisper-Solution-Setup-v1.1.4.exe` (1.828.829.686 bytes). Se incluyen checksum y firma, más alias técnicos para el actualizador existente.

SHA-256: `7f8ac158850a00532363c33ca2281c8c830a4ea02b4e2a206cf97db6d93092c2`
