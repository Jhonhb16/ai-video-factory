"""Doblaje y edicion de videos de cliente.

Producto distinto del canal propio: aqui NO se genera nada, se transforma un
video que ya existe. El video manda y nosotros nos adaptamos a el.

Flujo completo (ver runner.py):
  1. transcribir  - whisper saca el texto con tiempos y detecta el idioma
  2. adaptar      - se ADAPTA al español ajustando al hueco de cada bloque
  3. voz          - se genera, se MIDE y se corrige lo que no cabe
  4. planos       - se detecta que hay en pantalla en cada momento
  5. tarjetas     - se sustituyen los carteles de texto del idioma original
  6. graficos     - rotulos y franjas de datos, siempre fuera de la imagen
  7. montaje      - camara, capas, mezcla y union

Lo que hace este modulo distinto de un doblaje automatico: no deja NI UNA
palabra del idioma original en pantalla.
"""
