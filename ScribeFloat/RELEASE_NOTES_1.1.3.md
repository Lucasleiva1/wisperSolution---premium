## Whisper Solution 1.1.3

Esta versión mejora la disponibilidad y la interacción de la cápsula flotante.

### Cambios principales

- La cápsula y el panel se mantienen en el nivel nativo **siempre visible** de Windows.
- Recuperación automática del estado `TOPMOST` si Windows lo pierde al cambiar de ventana, monitor, escritorio o modo de pantalla.
- Nuevo control de cierre en el punto derecho de la cápsula.
- El punto de cierre cambia a rojo al posar el cursor y muestra la ayuda **Cerrar**.
- El botón **ABRIR** aparece únicamente al posar el cursor sobre la zona central de ondas.
- Pasar el cursor sobre el micrófono o el cierre ya no despliega **ABRIR**.
- Se conserva el clic directo del micrófono para iniciar y detener la grabación.

### Actualización y compatibilidad

- Publicación marcada como `latest` para que el actualizador integrado la detecte.
- Se incluyen instaladores con los nombres **Whisper Solution** y **ScribeFloat Premium** para conservar compatibilidad con versiones anteriores.
- Cada instalador incluye checksum SHA-256 y firma Ed25519 verificable.
