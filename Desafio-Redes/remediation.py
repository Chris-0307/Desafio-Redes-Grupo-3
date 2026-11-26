"""Remediacion de parametros conocidos; siempre verifica mediante GET."""
from copy import deepcopy
from ipaddress import IPv4Interface
from uuid import uuid4
from time import perf_counter
from audit import audit_configuration
from provisioning import KEY, interface_path, find_interface


def repair(client, results):
    outcomes = []
    for row in results:
        if row['compliant']:
            continue
        start = perf_counter()
        name, field, expected = row['interface'], row['parameter'], row['expected']
        status = None
        try:
            path = interface_path(name)
            current = find_interface(client, name)
            if not current or field == 'existence':
                raise ValueError('Interfaz ausente; usar aprovisionamiento inicial autorizado')
            if current.get('type') != 'iana-if-type:softwareLoopback':
                raise ValueError('Tipo de interfaz inesperado; no se modifica')
            if field in ('description', 'enabled'):
                status = client.patch(path, {KEY: [{'name': name, field: expected}]})
            elif field == 'ipv4':
                # Plain PATCH fusiona listas y puede dejar la IP incorrecta.
                # RFC 8072: reemplazar solo el contenedor IPv4, preservando otros campos.
                ipv4 = deepcopy(current.get('ietf-ip:ipv4', {}))
                ip = IPv4Interface(expected[0])
                ipv4['address'] = [{'ip': str(ip.ip), 'netmask': str(ip.netmask)}]
                payload = {'ietf-yang-patch:yang-patch': {'patch-id': str(uuid4()), 'edit': [
                    {'edit-id': 'restore-ipv4', 'operation': 'replace', 'target': '/ietf-ip:ipv4',
                     'value': {'ietf-ip:ipv4': ipv4}}]}}
                status = client.yang_patch(path, payload)
            else:
                raise ValueError('Parametro no soportado')
            verified = any(r['interface'] == name and r['parameter'] == field and r['compliant']
                           for r in audit_configuration(client))
            error = None if verified else 'GET posterior no confirma el valor esperado'
        except Exception as exc:
            verified, error = False, str(exc)
        outcomes.append({'interface': name, 'parameter': field, 'success': verified,
                         'http_status': status, 'seconds': round(perf_counter()-start, 4), 'error': error})
    return outcomes
