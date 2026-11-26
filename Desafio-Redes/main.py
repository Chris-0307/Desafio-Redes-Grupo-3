"""Network Compliance Manager: CLI para laboratorio Cisco IOS XE."""
import argparse
import os
import time
import json
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.text import Text
from audit import audit_configuration
from remediation import repair
from provisioning import (setup_managed, create_loopback, change_description,
                          put_description, update_banner)
from restconf_client import RestconfClient
from mock_router import MockRouter
from reporting import Reporter

console = Console()


def display_results(results):
    table = Table(title='Network Compliance Audit')
    for name in ['Interface', 'Parameter', 'Expected', 'Actual', 'Status']:
        table.add_column(name)
    for r in results:
        table.add_row(r['interface'], r['parameter'], Text(str(r['expected'])), Text(str(r['actual'])),
                      '[green]PASS[/green]' if r['compliant'] else '[red]FAIL[/red]')
    console.print(table)
    percentage = 100 * sum(r['compliant'] for r in results)/len(results) if results else None
    console.print(f'Compliance: {percentage:.2f}%' if percentage is not None else 'Compliance: N/A')


def cycle(client, reporter, heal=False):
    reporter.last_compliance = None
    results = audit_configuration(client)
    display_results(results)
    reporter.audit(results)
    if heal and any(not r['compliant'] for r in results):
        outcomes = repair(client, results)
        reporter.remediation(outcomes)
        reporter.last_compliance = None  # Until the final GET succeeds.
        final = audit_configuration(client)
        reporter.remediation([], final)
        display_results(final)
        return final
    return results


def run_periodic(client, reporter, interval, heal=False):
    print(f'Auditoria periodica cada {interval}s despues de cada ciclo. Ctrl+C para volver al menu.')
    try:
        while True:
            try:
                cycle(client, reporter, heal)
            except Exception as exc:
                reporter.last_compliance = None
                reporter.event('error', f'Ciclo fallido: {exc}', 'ERROR')
            time.sleep(interval)
    except KeyboardInterrupt:
        print('\nServicio detenido.')


def provision(client, reporter, action, *args):
    status = action(client, *args)
    reporter.event('provisioning', f'{action.__name__}: HTTP {status}, verificado mediante GET', http_status=status)


def report(reporter):
    print(json.dumps(reporter.summary(), indent=2, ensure_ascii=False))
    for path in reporter.export():
        print(f'Exportado: {path}')


def provisioning_menu(client, reporter):
    while True:
        print('\n1. Crear Loopback100 segun Golden Config (preparacion)\n2. Crear Loopback101 (POST)\n3. Cambiar descripcion Loopback101 (PATCH)\n4. Reemplazar descripcion Loopback101 (PUT)\n5. Actualizar MOTD (PUT, solo instancia dedicada)\n0. Volver')
        option = input('Opcion: ').strip()
        if option == '0':
            return
        try:
            if option == '1':
                provision(client, reporter, setup_managed)
            elif option == '2':
                address = input('IPv4/prefijo [10.101.0.1/32]: ').strip() or '10.101.0.1/32'
                provision(client, reporter, create_loopback, 'Loopback101', 'Remote Provisioning Demo', address)
            elif option == '3':
                provision(client, reporter, change_description, 'Loopback101', input('Nueva descripcion: '))
            elif option == '4':
                provision(client, reporter, put_description, input('Nueva descripcion: '))
            elif option == '5':
                provision(client, reporter, update_banner, input('Nuevo banner: '))
            else:
                print('Opcion invalida')
        except Exception as exc:
            reporter.event('error', f'Aprovisionamiento fallido: {exc}', 'ERROR')


def menu(client, reporter, interval):
    while True:
        print('\n=== NETWORK COMPLIANCE MANAGER ===')
        print('1. Auditoria manual\n2. Auditoria periodica (solo lectura)\n3. Self-Healing periodico\n4. Aprovisionamiento remoto\n5. Logs y reportes\n6. Self-Healing de un ciclo')
        if getattr(client, 'is_mock', False):
            print('7. Introducir desviaciones simuladas')
        print('0. Salir')
        option = input('Opcion: ').strip()
        try:
            if option == '0':
                report(reporter)
                return
            elif option == '1':
                cycle(client, reporter)
            elif option in ('2', '3'):
                run_periodic(client, reporter, interval, option == '3')
            elif option == '4':
                provisioning_menu(client, reporter)
            elif option == '5':
                report(reporter)
            elif option == '6':
                cycle(client, reporter, True)
            elif option == '7' and getattr(client, 'is_mock', False):
                client.simulate_drift('all')
                reporter.event('simulation', 'Desviaciones introducidas localmente', 'WARNING')
            else:
                print('Opcion invalida')
        except Exception as exc:
            reporter.event('error', f'Operacion fallida: {exc}', 'ERROR')


def demo(client, reporter):
    cycle(client, reporter)
    client.simulate_drift('all')
    reporter.event('simulation', 'Cambio externo simulado: descripcion, enabled e IPv4', 'WARNING')
    cycle(client, reporter, True)
    provision(client, reporter, create_loopback, 'Loopback101', 'Remote Provisioning Demo', '10.101.0.1/32')
    provision(client, reporter, change_description, 'Loopback101', 'Configured remotely by Python')
    provision(client, reporter, put_description, 'PUT demo')
    provision(client, reporter, update_banner, 'Authorized lab demo')
    report(reporter)


def main():
    load_dotenv(interpolate=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', action='store_true', help='Usar router real')
    parser.add_argument('--mock', action='store_true', help='Usar simulador (por defecto)')
    parser.add_argument('--demo', action='store_true', help='Demo completa, solo mock')
    parser.add_argument('--audit', action='store_true', help='Ejecutar una auditoria y salir')
    parser.add_argument('--drift', action='store_true', help='Introducir dos desviaciones mock y auditar')
    parser.add_argument('--interval', type=float, default=float(os.getenv('AUDIT_INTERVAL', '5')))
    args = parser.parse_args()
    if args.interval < 1 or not args.interval < float('inf'):
        parser.error('El intervalo debe ser finito y >= 1 segundo')
    if args.real and (args.mock or args.demo or args.drift):
        parser.error('--real no se combina con opciones simuladas')
    try:
        client = RestconfClient() if args.real else MockRouter()
        reporter = Reporter('REAL' if args.real else 'MOCK')
        reporter.event('start', 'Modo RESTCONF real' if args.real else 'Modo simulado: no hay trafico RESTCONF')
        if args.demo:
            demo(client, reporter)
        elif args.audit or args.drift:
            if args.drift:
                client.simulate_drift()
            cycle(client, reporter)
            report(reporter)
        else:
            menu(client, reporter, args.interval)
    except (KeyboardInterrupt, EOFError):
        print('\nPrograma terminado.')
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
