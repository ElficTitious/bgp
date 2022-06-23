# Actividad: BGP

Semana 12-13: Sistemas Autónomos y Ruteo, Módulo 4: Redes y Ruteo, CC4303-1

## Ejecución

Para ejecutar es necesario correr cada router en una ventana de terminal distinta, y enviar mensajes al router deseado usando `netcat`.
Cada router necesita como argumentos la IP del router y su puerto, sumado al nombre del archivo en que se encuentran sus tablas de ruta.

**Ejecución:**

Para correr cada router se debe pasar la IP del router y su puerto, sumado al nombre del archivo en que se encuentran sus tablas de ruta.
Adicionalmente, para activar BGP es necesario enviar un mensaje `START_BGP` a ***un solo router** por componente conexa de la red (decisión de diseño), con lo cual comienza a ejecutarse BGP.

Ejemplo:

```bash
python3 router.py 127.0.0.1 8881 rutas/v1/R1.txt
```

## Funcionamiento

La lógica de un router se encuentra dentro del script `router.py`, y todas las funcionalidades auxiliares dentro de `utilities.py`. Puesto que está todo documentado dentro de los respectivos archivos, se procede a explicar las decisiones de diseño.

**Decisiones de diseño:**

Para representar tablas de ruta con BGP se sigue la opción de reemplazar el rango de puertos de cada linea por una ruta ASN. Con lo cual la estructura de cada linea de una tabla de rutas será como sigue:

```[Red destino (CIDR)] [ruta ASN] [IP_siguiente_salto] [Puerto_siguiente_salto] [MTU]```

Para comenzar a ejecutar BGP es necesario enviar un mensaje `START_BGP` a un solo router por componente conexa de la red, y es aquel router el encargado de comunicar al resto de sus vecinos que comienza BGP reenviando el mensaje `START_BGP`. Ahora, puesto que los vecinos volverán a reenviar el mensaje `START_BGP` a sus respectivos vecinos, cada router puede recibir más de un mensaje de este tipo, no obstante la primera vez que lo haga entrará al bloque de código encargado de manejar BGP, y dentro de dicho bloque se descartará cada mensaje `START_BGP` recibido.

Respecto al manejo de tiempo para reconocer un estado estable en BGP, se hace uso del timeout provisto por `socket`, donde de estar mas de 10 segundos en un `recvfrom()` se arrojará un error manejado dentro de un bloque `except` donde se lleva a cabo lo necesario para concluir la ejecución del algoritmo. Si bien se indica que el timer debe reiniciarse cada vez que se envía un mensaje `BGP_ROUTES`, es evidente notar que si el `socket` pasó 10 segundos esperando un mensaje en un `recvfrom()`, luego por consecuencia pasó mas de 10 segundos sin enviar un mensaje `BGP_ROUTES`.

Finalmente, cabe mencionar que al acabar el algoritmo, cada router escribe su tabla de rutas en un archivo de nombre `rutas/v4/R[ASN].txt`, donde `[ASN]` representa el ASN del router en cuestión. De esta manera, si un router de ASN `8881` corre BGP, luego de que el algoritmo acabe escribirá su tabla de rutas en `rutas/v4/R8881.txt`.

