import sys
import socket
import time
from utilities import *
from random import randint

if __name__ == '__main__':

  # Instanciamos el socket
  conn_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

  # Definimos el tamaño de buffer
  buff_size = 1024

  # Parseamos los argumentos
  try:

    if len(sys.argv) == 4:

      router_IP = sys.argv[1]
      router_port = int(sys.argv[2])  # En este caso usamos esta variable como el ASN del router
      routing_table_file_name = sys.argv[3]

    # Si no se pasan correctamente los argumentos levantamos una exepción
    else:
      raise Exception(f'Expected 3 arguments, {len(sys.argv) - 1} were given')

  except Exception as err:
    print(err)

  # Si no se levanta ningun error proseguimos
  else:

    # Por precisión en terminología, definimos el ASN del router en una variable aparte, aunque
    # es lo mismo que el puerto en que escucha
    router_asn = router_port

    # Hacemos que el socket escuche de forma no bloqueante en el par (router_IP, router_port)
    conn_socket.bind((router_IP, router_port))

    # Instanciamos una tabla de ruteo de tipo RoundRobinRoutingTable
    round_robin_routing_table = RoundRobinRoutingTable(routing_table_file_name)

    # Creamos el diccionario donde almacenar los fragmentos
    fragment_dict = {}

    # Generamos los vecinos
    neighbor_addresses = get_neighbor_addresses(routing_table_file_name)

    # Recibimos paquetes de forma indefinida
    while True:
      
      # Recibimos un datagrama
      ip_header_buffer, _ = conn_socket.recvfrom(buff_size)

      # Parseamos su contenido
      ip_header = parse_ip_header(ip_header_buffer.decode())

      # Si el mensaje contenido en el datagrama es un START_BGP, se comienza
      # a ejecutar BGP.
      if ip_header.is_start_bgp:
        
        # Seteamos el timeout
        conn_socket.settimeout(10)

        # Creamos el contenido del mensaje BGP_ROUTES
        bgp_routes_msg = create_BGP_message(routing_table_file_name, router_asn)

        # Y guardamos igualmente la hoja de rutas existente al comienzo del proceso
        # como un objeto de tipo BGPRoutes
        bgp_routes = parse_BGP_routes(bgp_routes_msg)

        # Enviamos las rutas conocidas a todos los vecinos y avisamos que comienza
        # BGP (decisión de diseño).
        for neighbor_address in neighbor_addresses:

          # Cremos el mensaje BGP_START
          start_bgp_msg = IPHeader(
            neighbor_address[0], neighbor_address[1], 10, str(randint(1, 1000)),
            0, '00000009', False, 'START_BGP', True
          ).to_string()

          # Le agregamos los headers al mensaje BGP_ROUTES
          bgp_routes_msg_with_headers = IPHeader(
            neighbor_address[0], neighbor_address[1], 10, str(randint(1, 1000)),
            0, generate_ip_header_size(len(bgp_routes_msg.encode())), False,
            bgp_routes_msg, False
          ).to_string()

          # Enviamos ambos mensajes
          conn_socket.sendto(start_bgp_msg.encode(), neighbor_address)
          conn_socket.sendto(bgp_routes_msg_with_headers.encode(), neighbor_address)

        # Iteramos mientras no se haga timeout (en cuyo caso sabemos que pasaron
        # 10 segundos desde que se envió el último mensaje BGP_ROUTES)
        while True:

          # Recibimos rutas BGP dentro de un try, catch, else block para aprovechar
          # el timeout del socket. De hacer timeout sabemos que pasaron 10 segundos
          # desde el último envio de BGP_ROUTES y por ende se acaba BGP. Ahora, si
          # se recibe un START_BGP emitido por un vecino en la primera ronda de mensajes,
          # simplemente lo descartamos y seguimos con la siguiente iteración
          try:
            recvd_bgp_message, _ = conn_socket.recvfrom(buff_size)
            recvd_bgp_message = parse_ip_header(recvd_bgp_message.decode())

          # Si llegamos al except es por que se generó un timeout se acaba BGP
          # y rompemos el ciclo y quitamos el timeout
          except:

            # Generamos la nueva tabla de rutas
            resulting_table_after_bgp = generate_and_write_routing_table(
              routing_table_file_name, f'rutas/v4/R{router_asn}.txt',
              bgp_routes
            )

            # Imprimimos el contenido de dicha tabla de rutas
            print(resulting_table_after_bgp)

            # Instanciamos una nueva tabla de ruteo de tipo RoundRobinRoutingTable
            round_robin_routing_table = RoundRobinRoutingTable(f'rutas/v4/R{router_asn}.txt')

            # Quitamos el timeout
            conn_socket.settimeout(None)
            break
            
          else:
            # Si el mensaje es START_BGP, lo descartamos y seguimos con la siguiente
            # iteración
            if recvd_bgp_message.is_start_bgp:
              continue

            # De lo contrario tiene que ser un mensaje BGP_ROUTES y debemos procesarlo
            recvd_bgp_routes = parse_BGP_routes(recvd_bgp_message.msg)
            modified_routes = False  # Acá guardamos si es que se modifica la tabla de rutas
            for asn_route in recvd_bgp_routes.asn_routes:

              # Si la ruta contiene el ASN del router actual, la descarto
              if router_asn in asn_route:
                continue
              
              # Iteramos sobre la lista de rutas del router y vemos si tenemos una entrada para
              # el ASN de destino de la ruta asn_route
              known = False
              found_index: int  # variable donde guardar la ruta que coincide (de coincidir una)
              for asn_route_this_router, i in zip(bgp_routes.asn_routes, range(len(bgp_routes.asn_routes))):
                if asn_route[0] == asn_route_this_router[0]:
                  known = True
                  found_index = i
                  break
              
              # Si el ASN de destino no está en la tabla de rutas, agrego la ruta con
              # el ASN del router como ASN de origen
              if not known:
                extended_asn_route = asn_route + [router_asn]  # Extendemos la ruta
                bgp_routes.asn_routes.append(extended_asn_route)
                modified_routes = True

              # Si el ASN de destino si está en la tabla de rutas, me quedo con la
              # ruta mas corta
              if known:
                # Agregamos el ASN del router como ASN de origen y comparamos
                extended_asn_route = asn_route + [router_asn]
                if len(extended_asn_route) < len(bgp_routes.asn_routes[found_index]):
                  bgp_routes.asn_routes[found_index] = extended_asn_route
                  modified_routes = True

            # Saliendo del for loop revisamos todas las entradas en el mensaje BGP_ROUTES,
            # luego si es que se modificó la tabla de rutas en el proceso, comunicamos los
            # cambios a los vecinos
            if modified_routes:
              for neighbor_address in neighbor_addresses:

                # Le agregamos los headers a las rutas
                bgp_routes_msg = IPHeader(
                  neighbor_address[0], neighbor_address[1], 10, str(randint(1, 1000)),
                  0, generate_ip_header_size(len(bgp_routes.to_string().encode())), False,
                  bgp_routes.to_string(), False
                ).to_string()

                # Enviamos el mensaje
                conn_socket.sendto(bgp_routes_msg.encode(), neighbor_address)

        # Pasamos a la siguiente iteración
        continue    

        # Al finalizar bgp se habrá actualizado la tabla de ruteo, y debemos tambien
        # reinicializar la round_robin_routing_table

      # Si el TTL del paquete es menor o igual a 0, luego ignoramos el paquete y 
      # seguimos a la siguiente iteración (puede ser menor a cero si se inicializa
      # un paquete con un número negativo --lo cual es un error pero lo prevenimos
      # igualmente--)
      if ip_header.ttl <= 0:
        continue

      # Si el datagrama es para este router, intentamos reensamblar, y si aquello es
      # satisfactorio, imprimimos el mensaje en pantalla
      if ip_header.ip_address == router_IP and ip_header.port == router_port:

        # Si no tenemos una llave para la id del datagram recibido la creamos y la
        # mapeamos a una lista vacía.
        if ip_header.id not in fragment_dict:
          fragment_dict[ip_header.id] = []

        # Agregamos el datagrama a la lista e intentamos reensamblar
        fragment_dict[ip_header.id].append(ip_header_buffer.decode())
        reassembled_datagram = reassemble_ip_packet(fragment_dict[ip_header.id])

        # Si el resultado de intentar reensamblar el datagrama no es None, imprimimos
        # el mensaje en pantalla y quitamos la llave junto con su lista asociada para
        # poder recibir el mensaje nuevamente
        if reassembled_datagram is not None:
          fragment_dict.pop(ip_header.id)
          print(parse_ip_header(reassembled_datagram).msg)

      # De lo contrario buscamos como redirigir en la tabla de rutas
      else:

        # Generamos el siguiente salto
        forward_address_link_mtu = next_hop(
          round_robin_routing_table,
          (ip_header.ip_address, ip_header.port)
        )

        # Si el forward adress es None, luego no se encontró como redirigir en la
        # tabla de ruta, e imprimimos un mensaje informando aquello
        if forward_address_link_mtu is None:
          print('No hay rutas hacia', (ip_header.ip_address, ip_header.port), 
                'para paquete', ip_header.ip_address)
        
        # De lo contrario, se encontró una forma de redirigir, e informamos aquello
        else:
          forward_address, link_mtu = forward_address_link_mtu
          print('redirigiendo paquete', ip_header.ip_address, 'con destino final',
                (ip_header.ip_address, ip_header.port), 'desde', (router_IP, router_port),
                'hacia', forward_address)

          # Decrementamos el TTL
          ip_header.ttl -= 1

          # Fragmentamos el paquete
          fragments = fragment_ip_packet(ip_header_buffer.decode(), link_mtu)

          # Realizamos la dirección para cada fragmento
          for fragment in fragments:
            conn_socket.sendto(fragment.encode(), forward_address)




