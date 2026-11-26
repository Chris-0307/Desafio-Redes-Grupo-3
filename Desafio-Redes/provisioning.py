"""Operaciones limitadas a las interfaces de laboratorio."""
from ipaddress import IPv4Interface
import os
from audit import get_interfaces, normalize_addresses, load_golden_config

BASE = 'ietf-interfaces:interfaces'
KEY = 'ietf-interfaces:interface'
MOTD = 'Cisco-IOS-XE-native:native/banner/motd'
ALLOWED = {'Loopback100', 'Loopback101'}


def interface_path(name):
    if name not in ALLOWED:
        raise ValueError('Solo se permiten Loopback100 y Loopback101')
    return f'{BASE}/interface={name}'


def find_interface(client, name):
    interface_path(name)
    return next((i for i in get_interfaces(client) if i['name'] == name), None)


def interface_payload(name, description, address, enabled=True):
    interface_path(name)
    ip = IPv4Interface(address)
    return {KEY: [{'name': name, 'description': description,
                   'type': 'iana-if-type:softwareLoopback', 'enabled': enabled,
                   'ietf-ip:ipv4': {'address': [{'ip': str(ip.ip), 'netmask': str(ip.netmask)}]}}]}


def create_loopback(client, name, description, address, enabled=True):
    if find_interface(client, name) is not None:
        raise ValueError(f'{name} ya existe; no se sobrescribe')
    # POST sobre el contenedor padre crea una entrada de la lista.
    status = client.post(BASE, interface_payload(name, description, address, enabled))
    current = find_interface(client, name)
    if not current or current.get('description') != description or current.get('enabled', True) != enabled or normalize_addresses(current) != [str(IPv4Interface(address))]:
        raise ValueError('POST aceptado, pero la configuracion no pudo verificarse')
    return status


def setup_managed(client):
    policy = load_golden_config()['interfaces'][0]
    ip = policy['ipv4']
    return create_loopback(client, policy['name'], policy['description'], f"{ip['ip']}/{ip['netmask']}", policy['enabled'])


def change_description(client, name, description):
    if name != 'Loopback101':
        raise ValueError('Aprovisionamiento: usar Loopback101 para no competir con auditoria')
    if not find_interface(client, name):
        raise ValueError('Primero crea la interfaz')
    status = client.patch(interface_path(name), {KEY: [{'name': name, 'description': description}]})
    if (find_interface(client, name) or {}).get('description') != description:
        raise ValueError('PATCH aceptado, pero descripcion no verificada')
    return status


def put_description(client, description):
    """PUT de una hoja: no reemplaza la interfaz completa."""
    name = 'Loopback101'
    if not find_interface(client, name):
        raise ValueError('Primero crea Loopback101')
    status = client.put(interface_path(name) + '/description', {'ietf-interfaces:description': description})
    if (find_interface(client, name) or {}).get('description') != description:
        raise ValueError('PUT aceptado, pero descripcion no verificada')
    return status


def update_banner(client, message):
    if not getattr(client, 'is_mock', False) and os.getenv('ALLOW_BANNER', 'false').lower() != 'true':
        raise ValueError('Banner global bloqueado: habilitar solo en instancia dedicada')
    status = client.put(MOTD, {'Cisco-IOS-XE-native:motd': {'banner': message}})
    current = client.get(MOTD, params={'content': 'config'})
    if current.get('Cisco-IOS-XE-native:motd', {}).get('banner') != message:
        raise ValueError('PUT aceptado, pero banner no verificado')
    return status
