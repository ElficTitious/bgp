from dataclasses import dataclass
import ipaddress

@dataclass
class IPHeader:
  """Data class usada para representar un header IP.

  Attributes:
  -----------
  ip_address (str): Dirección IP donde se encuentra escuchando el router
                    de destino del paquete.
  port (int): Puerto en que se encuentra escuchando el router de destino
              del paquete en la IP ip_address.
  ttl (int): Time To Live.
  id (str): Identificador que permite identificar todos los fragmentos 
            que forman parte de un mismo paquete IP.
  offset (int): Entero que indica a partir el lugar de inicio de la 
                secuencia de bytes contenido en msg, relativo al datagrama IP.
  size (str): Se refiere al tamaño de msg en bytes. Asumimos que este header 
              siempre contiene 8 dígitos. De esta forma si msg es de tamaño 
              300 bytes , entonces se tendrá size='00000300'.
  flag (bool): Etiqueta que toma el valor True si quedan fragmentos después 
               del fragmento actual, y toma el valor False si este es el 
               último fragmento del datagrama original.
  msg (str): Mensaje siendo enviado en el paquete.
  is_start_bgp (bool): Valor booleano que indica si el mensaje es START_BGP.
  """

  ip_address: str
  port: int
  ttl: int
  id: str
  offset: int
  size: str
  flag: bool
  msg: str
  is_start_bgp: bool

  def to_string(self) -> str:
    """Método usado para tranformar esta instancia a string (inversa de
    parse_ip_header). Podríamos hacer un override de __str__, pero nos 
    interesa conservar ese comportamiento.

    Returns:
    --------
    (str): Representación del header como str, debe ser la inversa de
           parse_ip_header. Es decir parse_ip_header(s).to_string() == s
           siempre se cumple.
    """
    return ','.join([self.ip_address, str(self.port), str(self.ttl), self.id,
                     str(self.offset), self.size, '1' if self.flag else '0', self.msg])

@dataclass
class RoutingTableLine:
  """Data class usada para representar una línea de una tabla de ruteo.

  Attributes:
  -----------
  possible_ip_addresses (list[str]): Lista con todas las potenciales direcciones
                                     IP generadas a partir de una red (CIDR).
  asn_route (list[int]): Lista con la ruta ASN
  landing_ip (str): Dirección IP donde redirigir dados los valores anteriores
  landing_port (int): Puerto donde redirigir dados los primeros dos valores y la IP 
                      anterior
  mtu (int): Cantidad máxima de información en bytes que podemos enviar a través del enlace.
  """

  possible_ip_addresses: list[str]
  asn_route: list[int]
  landing_ip: str
  landing_port: int
  mtu: int

class CircularArrayWithPointer:
  """Clase usada para representar un arreglo circular, con un puntero indicando
  cual es el proximo elemento solicitable (solo se puede solicitar un solo elemento
  en un determinado momento).

  Methods:
  --------
  next:
    Retorna el próximo elemento solicitable en el arreglo.
  """

  def __init__(self, data: list):
    self.__array = data
    self.__n = len(data)
    self.__pointer = 0

  def next(self):
    """Método usado para solicitar un elemento del arreglo circular. Éste retorna
    los elementos en orden ascendente dentro de l arreglo, pero una vez llega al
    final, vuelve al comienzo. Si el arreglo tiene largo 0, luego retorna None.

    Returns:
    --------
      Elemento en el arreglo dado por el orden anterior en que se han pedido elementos.
    """

    # Si el arreglo no tiene elementos, retornamos None
    if self.__n == 0:
      return None

    # Si el puntero está alfinal del arreglo, vuelve el puntero al comienzo
    # y retorna el último elemento.
    elif self.__pointer == self.__n - 1:
      prev_pointer = self.__pointer
      self.__pointer = 0
      return self.__array[prev_pointer]

    # De lo contrario aumentamos el puntero en uno y retornamos el elemento en que
    # estaba anteriormente el puntero.
    else:
      prev_pointer = self.__pointer
      self.__pointer += 1
      return self.__array[prev_pointer]

@dataclass
class BGPRoutes:
  """Data class usada para representar rutas BGP.

  Attributes:
  -----------
  asn_transmitter (int): ASN del router que envía el mensaje.
  asn_routes (list[list[int]]): Lista de rutas ASN, donde cada ruta es a su
                                vez una lista de enteros, representando cada entero
                                un ASN.
  """

  asn_transmitter: int
  asn_routes: list[list[int]]

  def to_string(self) -> str:
    """Método usado para tranformar esta instancia a string, el cual puede ser
    enviado como mensaje BGP en un datagrama.

    Returns:
    --------
    (str): Representación del mensaje como str.
    """
    bgp_msg = f'BGP_ROUTES\n{self.asn_transmitter}\n'
    for route in self.asn_routes:
      bgp_msg += ' '.join([str(asn) for asn in route]) + '\n'

    bgp_msg += 'END_BGP_ROUTES'
    return bgp_msg

def create_BGP_message(routing_table_file_name: str, asn_transmitter: int) -> str:
  """Función encargada de generar el mensaje BGP para un router especifico dado
  por su ASN y su tabla de rutas.

  Parameters:
  -----------
  routing_table_file_name (str): Nombre del archivo que contiene la tabla de ruteo.
  asn_transmitter (int): ASN del router para el cual se genera el mensaje BGP.

  Returns:
  --------
  (str): Mensaje BGP dado por el ASN del router transmisor y su tabla de rutas.
  """

  # Abrimos el archivo que contiene la tabla de rutas y leemos sus lineas
  routing_table_file = open(routing_table_file_name, 'r')
  routing_table_lines = routing_table_file.readlines()

  # Creamos una variable donde almacenar las rutas ASN
  asn_routes = []

  # Iteramos sobre las lineas
  for line in routing_table_lines:

    # Parseamos la línea
    routing_table_line = parse_routing_table_line(line.strip('\n'))

    # Agregamos la ruta ASN
    asn_routes.append(routing_table_line.asn_route)
  
  # Cerramos el archivo con tabla de ruteo
  routing_table_file.close()
  
  # Construimos y retornamos el mensaje BGP
  return BGPRoutes(asn_transmitter, asn_routes).to_string()

def parse_BGP_routes(BGP_routes: str) -> BGPRoutes:
  """Función usada para parsear un mensaje BGP_ROUTES, transformandolo a su representación
  como instancia de la clase BGPRoutes.

  Parameters:
  -----------
  BGP_routes (str): Mensaje BGP_ROUTES a parsear.

  Returns:
  --------
  (BGPRoutes): Instancia de la clase BGPRoutes representando el mismo mensaje pasado
                como parámetro.
  """

  # Separamos el mensaje BGP en sus lineas
  lines = BGP_routes.split('\n')

  # Prescindimos del primer y ultimo elementos (BGP_ROUTES y END_BGP_ROUTES)
  lines.pop(0)
  lines.pop(-1)

  # Guardamos y quitamos el ASN del router emisor
  asn_transmitter = int(lines.pop(0))

  # Generamos las rutas ASN
  asn_routes = []
  for raw_route in lines:
    asn_route = [int(asn) for asn in raw_route.split(' ')]
    asn_routes.append(asn_route)
  
  # Generamos y retornamos la instancia de BGPRoutes
  return BGPRoutes(asn_transmitter, asn_routes)

def parse_routing_table_line(routing_table_line: str) -> RoutingTableLine:
  """Función que dada una linea de una tabla de ruteo, de la forma
  [Red (CIDR)] [Ruta ASN] [IP_Para_llegar] [Puerto_para_llegar] [MTU],
  la parsea retornando una instancia de RoutingTableLine.

  Parameters:
  -----------
  routing_table_line (str): Linea de una tabla de ruteo, la cual debe ser de la forma
                            [Red (CIDR)] [Ruta ASN] [IP_Para_llegar] [Puerto_para_llegar] [MTU].
  
  Returns:
  --------
  (RoutingTableLine): Linea de la tabla de ruteo pasada como parametro, pero parseada y empaquetada
                      en una instancia de la data class RoutingTableLine.
  """

  # Comenzamos por extraer el contenido de la línea en una lista
  routing_table_line_contents_list = routing_table_line.split(' ')

  # Guardamos el contenido en variables ad-hoc
  cidr_net = routing_table_line_contents_list[0]
  asn_route = [int(asn) for asn in routing_table_line_contents_list[1:-3]]
  landing_ip = routing_table_line_contents_list[-3]
  landing_port = int(routing_table_line_contents_list[-2])
  mtu = int(routing_table_line_contents_list[-1])

  # Generamos la lista con todas las potenciales direcciones IP generadas 
  # a partir de la red (CIDR) presente en la linea.
  possible_ip_addresses = [str(ip) for ip in ipaddress.IPv4Network(cidr_net)]

  # Retornamos la instancia de RoutingTableLine
  return RoutingTableLine(possible_ip_addresses, asn_route, 
                          landing_ip, landing_port, mtu)

class RoundRobinRoutingTable:
  """Clase usada para representar tablas de ruteo, añadiendo la funcionalidad
  de alternar forwarding de paquetes cuando existen varias rutas posibles para
  un mismo paquete.
  """

  def __init__(self, routing_table_file_name: str):
    self.__routing_table_file_name = routing_table_file_name
    self.__table = {}

  def __generate_entry(self, destination_address: tuple[str, int]):
    """Método privado usado para generar la entrada asociada a una dirección de
    destino en una instancia de esta clase. Esta entrada sera del tipo
    CircularArrayWithPointer. Notemos que si no se encuentra una forma de hacer
    forward para la dirección de destino, el arreglo circular será vacío, y al hacerle
    next se obtendrá None, que es el comportamiento deseado.

    Parameters:
    -----------
    destination_address (tuple[str, int]): Dirección de destino para la cual generar
                                           la entrada.
    """

    # Desempaquetamos la dirección de destino por facilidad de uso
    destination_ip, destination_port = destination_address

    # Creamos la lista con la cual inicializar la instancia de CircularArrayWithPointer
    forward_adresses_mtu_list = []

    # Abrimos el archivo que contiene la tabla de ruteo y leemos sus lineas
    routing_table_file = open(self.__routing_table_file_name, 'r')
    routing_table_lines = routing_table_file.readlines()

    # Iteramos sobre las lineas
    for line in routing_table_lines:

      # Parseamos la línea
      routing_table_line = parse_routing_table_line(line.strip('\n'))

      # Revisamos si en la linea actual se indica como hacer forward para la dirección de destino
      if (destination_ip in routing_table_line.possible_ip_addresses and 
          destination_port in routing_table_line.asn_route):
      
        # De ser el caso agregamos la dirección a la cual hacer forward a la lista con la cual inicializar
        # el CircularArrayWithPointer, y asi mismo el MTU del enlace
        next_hop_ip, next_hop_port = (routing_table_line.landing_ip, routing_table_line.landing_port)
        link_mtu = routing_table_line.mtu
        forward_adresses_mtu_list.append(((next_hop_ip, next_hop_port), link_mtu))

    # Cerramos el archivo con tabla de ruteo
    routing_table_file.close()

    # Finalmente inicializamos la entrada asociada a esta dirección de destino
    self.__table[destination_address] = CircularArrayWithPointer(forward_adresses_mtu_list)

  def next_hop(self, destination_address: tuple[str, int]) -> tuple[tuple[str, int], int] | None:
    """Método usado para, dada la lista de ruteo con que se instancia este
    objeto, y la dirección de destino pasada como parámetro, obtener el próximo salto
    en el arreglo circular de posibles formas de hacer forward, junto con el MTU del enlace.
    Si no existe una entrada en el diccionario subyacente, este se genera antes de retornar. 
    Notemos que si no existe una forma de hacer forward, por la manera en que está implementado 
    el método encargado de generar el arreglo circular, y el comportamiento del arreglo circular 
    al estar vacío, se retorna None (que es el comportamiento esperado).

    Parameters:
    -----------
    destination_address (tuple[str, int]): Par (destination_ip, destination_port) para el cual
                                           se busca hacer forward.

    Returns:
    --------
    (tuple[tuple[str, int], int] | None): Próxima manera de hacer forward junto con el MTU del
                                          enlace, donde de existir una se retorna 
                                          ((next_hop_IP, next_hop_port), link_mtu). Ahora, si no
                                          existe una forma de hacer forward, el arreglo circular 
                                          subyacente estará vacio y por ende se retornará None.
    """
    if destination_address in self.__table:
      return self.__table[destination_address].next()
    
    else:
      self.__generate_entry(destination_address)
      return self.__table[destination_address].next()


def parse_ip_header(ip_header: str) -> IPHeader:
  """Función encargada de, dado un header IP representado como
  un string de la forma:
    [Dirección IP],[Puerto],[TTL],[ID],[Offset],[Tamaño],[FLAG],[mensaje]
  retornar un objeto de la data class IPHeader.

  Parameters:
  -----------
  ip_header (str): Header IP representado como un string de la forma 
                   [Dirección IP],[Puerto],[TTL],[ID],[Offset],[Tamaño],[FLAG],[mensaje]
  
  Returns:
  --------
  (IPHeader): Instancia de la data class representando el mismo header ip
              pasado como parámetro
  """

  # Extraemos el contenido del header
  packet_contents_list = ip_header.split(',')

  # Guardamos la itnerpretación del contenido en variables ad-hoc
  ip_address = packet_contents_list[0]
  port = int(packet_contents_list[1])
  ttl = int(packet_contents_list[2])
  id = packet_contents_list[3]
  offset = int(packet_contents_list[4])
  size = packet_contents_list[5]
  # Asumimos que el FLAG será solo 0 o 1
  flag = True if packet_contents_list[6] == '1' else False 
  msg = packet_contents_list[7]
  is_start_bgp = (msg.strip('\n') == 'START_BGP')

  # Retornamos el contenido empaquetado en una instancia de IPHeader
  return IPHeader(ip_address, port, ttl, id, offset, size, flag, msg, is_start_bgp)

def next_hop(round_robin_routing_table: RoundRobinRoutingTable, 
             destination_address: tuple[str, int]) -> tuple[tuple[str, int], int] | None:
  """Función que dada una tabla de ruteo de tipo Round Robin, y un par
  (destination_ip, destination_port), retorna la siguiente manera de hacer forward y el MTU del
  enlace usando la tabla de ruteo subyacente a la instancia de RoundRobinRoutingTable pasada como parámetro.
  De encontrar una dirección donde redirigir se retorna dicho par, de lo contrario se retorna None.

  Parameters:
  -----------
  round_robin_routing_table (RoundRobinRoutingTable): Instancia de tipo RoundRobinRoutingTable, la cual
                                                      contiene la tabla de ruteo a ser revisada.
  destination_address (tuple[str, int]): Par (destination_ip, destination_port) a buscar en la
                                         tabla de ruteo.
  
  Returns:
  --------
  (tuple[tuple[str, int], int] | None): De encontrar una o más direcciones donde redirigir, se retorna 
                                        la siguiente dirección en el arreglo circular subyacente junto
                                        con el MTU del enlace, que será de la forma
                                        ((next_hop_IP, next_hop_port), link_mtu), pero de recorrer la 
                                        tabla completa y no encontrar una ruta apropiada, se retorna None.
  """

  return round_robin_routing_table.next_hop(destination_address)

def generate_ip_header_size(size: int) -> str:
  """Función auxiliar usada para generar el largo de un mensaje inmerso dentro de un
  header IP siguiendo la convención de 8 digitos.

  Parameters:
  -----------
  size (int): Largo de un mensaje a convertir al formato correcto de 8 digitos

  Returns:
  --------
  (str): Mismo largo que el pasado como parámetro pero en el formato correcto para
         usar como size dentro de un paquete IP.
         Ejemplo: generate_ip_header_size(255) -> '00000255'
  """
  
  size_in_correct_format = f'{size}'

  # Mientras size_in_correct_format no tenga 8 digitos agregamos un 0 al comienzo
  while len(size_in_correct_format) < 8:
    size_in_correct_format = '0' + size_in_correct_format
  
  return size_in_correct_format

def fragment_ip_packet(ip_packet: str, mtu: int) -> list[str]:
  """Función encargada de fragmentar un paquete IP dado como parametro para que quepa
  a través de un enlace con el MTU dado.

  Parameters:
  -----------
  ip_packet (str): Paquete IP a fragmentar.
  mtu (int): MTU mediante el cual fragmentar el paquete IP.

  Returns:
  --------
  (list[str]): Lista que contiene al paquete IP fragmentado usando el MTU pasado como
               parámetro.
  """

  # Si el largo en bytes del paquete es menor o igual a MTU, csgnifica que 
  # cabe completo por el enalce y por ende no es necesario fragmentarlo.
  if len(ip_packet.encode()) <= mtu:
    return [ip_packet]

  # De lo contrario es necesario llevar a cabo fragmentación.
  else:

    # Creamos un lista donde guardar los fragmentos
    fragments_list = []

    # Parseamos el paquete IP
    parsed_ip_packet = parse_ip_header(ip_packet)

    # Guardamos el mensaje total
    msg = parsed_ip_packet.msg

    # Para cada fragmento se heradan los campos [Dirección IP],[Puerto],[TTL] e [ID]
    ip_address = parsed_ip_packet.ip_address
    port = parsed_ip_packet.port
    ttl = parsed_ip_packet.ttl
    id = parsed_ip_packet.id

    # Creamos una variable donde almacenar el offset dentro de este mensaje; puede darse,
    # si ip_packet es un fragmento, que offset_in_msg != parsed_ip_packet.offset
    offset_in_msg = 0

    # Iteramos mientras no hayamos recorrido el mensaje completo
    while offset_in_msg < len(msg.encode()):

      # Calculamos los headers para el fragmento actual
      curr_frag_offset = parsed_ip_packet.offset + offset_in_msg
      curr_frag_size = '00000000'  # Usamos 8 ceros como placeholder
      # Por defecto seteamos el flag como True, ahora, si el paquete original no es fragmento,
      # luego ponemos el flag del último fragmento como False
      curr_frag_flag = True
      curr_frag_flag_as_str = '1'

      # Construimos el fragment header solo para calcular su largo en bytes
      fragment_header = f'{ip_address},{port},{ttl},{id},{curr_frag_offset},{curr_frag_size},{curr_frag_flag_as_str},'
      fragment_header_len = len(fragment_header.encode())

      # Calculamos el largo maximo de mensaje que se puede introducir en el fragmento actual
      curr_fragment_max_msg_len = mtu - fragment_header_len

      # Construimos el mensaje a incluir en el fragmento
      curr_frag_msg = (msg.encode())[offset_in_msg:offset_in_msg + curr_fragment_max_msg_len]

      # Asignamos el valor correcto de size
      curr_frag_size = generate_ip_header_size(len(curr_frag_msg))

      # Construimos el fragmento y lo agregamos a la lista
      curr_fragment = IPHeader(
        ip_address, port, ttl, id, curr_frag_offset,
        curr_frag_size, curr_frag_flag, curr_frag_msg.decode(), False
      )
      fragments_list.append(curr_fragment)

      # Actualizamos offset_in_msg
      offset_in_msg += len(curr_frag_msg)

    # Si el paquete original no era un fragmento, marcamos el FLAG del último
    # fragmento como False
    if not parsed_ip_packet.flag:
      fragments_list[-1].flag = False

    # Finalmente hacemos un map a la lista de fragmentos pasando cada fragmento
    # a su representación como string, y la retornamos
    fragments_list = list(map(lambda ip_header: ip_header.to_string(), fragments_list))
    return fragments_list

def reassemble_ip_packet(fragment_list: list[str]) -> str | None:
  """Función encargada de reensamblar un paquete IP a partir de una lista
  de sus fragmentos. Si la lista de fragmentos está incompleta se retorna
  None.

  Parameters:
  -----------
  fragment_list (list[str]): Lista de fragmentos a ensamblar.

  Returns:
  --------
  (str | None): Si la lista de fragmentos está completa, luego se
                retorna el paquete IP reensamblado, de lo contrario se
                retorna None.
  """

  # Primero mapeamos la lista a instancias de la clase IPHeader
  fragment_list = list(map(parse_ip_header, fragment_list))

  # Luego la ordenamos de manera ascendente por el offset
  fragment_list = sorted(fragment_list, key=lambda ip_header: ip_header.offset)

  # Creamos una variable booleana donde almacenar el valor de verdad indicando
  # que la lista de fragmentos está completa. Una primera condición que se debe
  # cumplir es que el primer fragmento tenga offset 0, por lo que inicializamos
  # la variable con el valor de verdad de aquella proposición.
  fragment_list_is_complete = (fragment_list[0].offset == 0)

  # A continuación hacemos una pasada por la lista revisando que esté completa
  # y aprovechando de reensamblar el mensaje
  i = 0
  total_msg = fragment_list[0].msg
  while fragment_list_is_complete and i < len(fragment_list) - 1:

    # Almacenamos el fragmento actual y el siguiente
    curr_frag = fragment_list[i]
    next_frag = fragment_list[i+1]

    # Añadimos el siguiente pedazo del mensaje
    total_msg += next_frag.msg

    # Se debe cumplir en cada posición que el offset del fragmento igual, mas
    # el largo de su mensaje, sea igual al offset del siguiente fragmento. Donde
    # si no se cumple dicha condición, podemos setear fragment_list_is_complete
    # a False y romper el ciclo
    if curr_frag.offset + int(curr_frag.size) != next_frag.offset:
      fragment_list_is_complete = False
      break

    # Si no se rompe el ciclo aumentamos el contador en 1
    i += 1

  # Una última condición que debe cumplirse es que el flag del último fragmento sea
  # 0 (o en este caso False --los fragmentos están representados como IPHeader--).
  # Luego si se satisface lo contrario podemos setear fragment_list_is_complete a False
  if fragment_list[-1].flag:
    fragment_list_is_complete = False
  
  # Si la lista de fragmentos estaba completa, luego podemos reensamblar el mensaje
  if fragment_list_is_complete:

    # Creamos el paquete reensamblado primero como una instancia de IPHeader, para luego
    # pasarlo a string y retornarlo. Podemos tomar los headers del primer fragmento, donde
    # lo único que habría que cambiar es el flag a 0, y el tamaño al largo total del mensaje.
    fst_frag = fragment_list[0]
    reassembled_ip_packet = IPHeader(
      fst_frag.ip_address, fst_frag.port, fst_frag.ttl, fst_frag.id,
      fst_frag.offset, generate_ip_header_size(len(total_msg.encode())),
      False, total_msg, False
    )
    return reassembled_ip_packet.to_string()

def get_neighbor_addresses(routing_table_file_name: str) -> list[tuple[str, int]]:
  """Función encargada de generar una lista con la dirección de cada
  vecino para un router especifico dada su su tabla de rutas inicial.

  Parameters:
  -----------
  routing_table_file_name (str): Nombre del archivo que contiene la tabla de ruteo.

  Returns:
  --------
  (list[tuple[str, int]]): Lista con la dirección de cada vecino del router dado
                            por su tabla de rutas inicial.
  """

  # Abrimos el archivo que contiene la tabla de rutas y leemos sus lineas
  routing_table_file = open(routing_table_file_name, 'r')
  routing_table_lines = routing_table_file.readlines()

  # Creamos una variable donde almacenar las direcciones
  neighbor_adresses = []

  # Iteramos sobre las lineas
  for line in routing_table_lines:

    # Parseamos la línea
    routing_table_line = parse_routing_table_line(line.strip('\n'))

    # Agregamos la dirección
    neighbor_adresses.append(
      (routing_table_line.landing_ip, routing_table_line.landing_port)
    )

  # Cerramos el archivo con tabla de ruteo
  routing_table_file.close()
  
  # Retornamos la lista de direcciones
  return neighbor_adresses

def generate_and_write_routing_table(routing_table_file_name: str, result_file_name: str, bgp_routes: BGPRoutes) -> str:
  """Función encargada de generar una nueva tabla de rutas a partir de un objeto
  de tipo BGPRoutes, la cual es escrita en el archivo result_file_name.

  Parameters:
  -----------
  routing_table_file_name (str): Nombre del archivo que contiene la tabla de ruteo.
  result_file_name (str): Nombre de archivo donde escribir la tabla de ruteo resultante
  bgp_routes (BGPRoutes): Mensaje de tipo BGP_ROUTES con la información necesaria
                          para generar la hoja de rutas.

  Returns:
  --------
  (str): Contenido de la tabla de ruteo resultante.
  """

  # Abrimos el archivo que contiene la tabla de rutas y leemos sus lineas
  routing_table_file = open(routing_table_file_name, 'r')
  routing_table_lines = routing_table_file.readlines()
  parsed_routing_table_lines = list(map(
    lambda line: parse_routing_table_line(line.strip('\n')),
    routing_table_lines
  ))

  # Cerramos el archivo con tabla de ruteo
  routing_table_file.close()

  # Creamos las lineas, donde por simplicidad asumimos que la Red (CIDR) es 
  # siempre 127.0.0.0/24, con MTU igual a 1000.
  lines = ''
  for asn_route in bgp_routes.asn_routes:
    landing_ip: str
    landing_port: int
    for parsed_line in parsed_routing_table_lines:
      if asn_route[-2] == parsed_line.asn_route[0]:
        landing_ip = parsed_line.landing_ip
        landing_port = parsed_line.landing_port
        break

    # Creamos la linea
    lines += f'127.0.0.0/24 {" ".join([str(asn) for asn in asn_route])} {landing_ip} {landing_port} 1000\n'
  
  # Quitamos el último salto de linea
  lines = lines[:-1]

  # escribimos las lineas
  with open(result_file_name, "w") as routing_table_result_file:
    routing_table_result_file.write(lines)

  # Retornamos el contenido de la tabla de ruteo
  return lines