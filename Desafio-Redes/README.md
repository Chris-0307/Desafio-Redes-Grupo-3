# Desafio de Redes — Network Compliance Manager

Aplicacion Python para el Cisco Catalyst 8000V con IOS XE. Implementa las cuatro funcionalidades acordadas: auditoria periodica, remediacion automatica, aprovisionamiento remoto y logs/reportes.

## 1. Instalacion en Windows (PowerShell)

Abrir esta carpeta en VS Code. Desde la terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No se necesita activar el entorno virtual ni cambiar la politica de ejecucion de PowerShell. Si ya existe `.env`, no lo sobrescribas. No se incluyen credenciales reales. No subir `.env`, logs ni reportes sin revisar su contenido.

## 2. Prueba sin router

```powershell
.\.venv\Scripts\python.exe main.py --demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --mock
```

La demo automatica recorre las cuatro funcionalidades: auditoria inicial 100%, tres desviaciones, auditoria 0%, tres remediaciones verificadas, auditoria final 100%, cuatro acciones de aprovisionamiento y exportacion JSON/CSV. El simulador no envia solicitudes HTTP; sus estados son locales y se reinician al salir. Los archivos generados llevan el prefijo MOCK o REAL. Los resultados mock no constituyen evidencia de comunicacion real.

En el menu interactivo, selecciona 1, 7, 1, 6, 4 (opciones 2, 3, 4 y 5), 5 y 0. Las opciones 2 y 3 del menu principal repiten ciclos con una pausa de cinco segundos; Ctrl+C vuelve al menu. En modo mock se puede introducir la desviacion antes de activar el ciclo periodico.

## 3. Conexion al router real

Modificar `.env` con host (sin https://), puerto, usuario, contrasena y, si existe, ruta al certificado/CA confiable en ROUTER_CA_BUNDLE. Dejar VERIFY_SSL=true para validar TLS. Si no hay otra opcion, VERIFY_SSL=false permite pruebas temporales en el laboratorio con certificado autofirmado, pero no verifica la identidad del servidor. No hacerlo en produccion. No utilizar credenciales que ya fueron expuestas; generar nuevas.

```powershell
.\.venv\Scripts\python.exe main.py --real --audit
```

Esto es solo lectura. Si retorna HTTP 401, comprobar credenciales/permisos y vigencia de la sesion. Si retorna 404, comprobar modelo YANG instalado. Si el entorno requiere VPN, conectarse primero. Una auditoria sin Loopback100 reportara ausencia; esto no implica un fallo de autenticacion.

### Habilitar escritura exclusivamente con autorizacion

El modo real bloquea escrituras por defecto (ALLOW_WRITES=false). Confirmar que la instancia es dedicada o que el administrador autorizo expresamente los recursos de laboratorio. Comprobar que Loopback100 y Loopback101 estan libres y las direcciones propuestas no se usan. Si existen interfaces ajenas con esos nombres, NO activar escrituras; solicitar una instancia limpia. No usar este programa para modificar interfaces de administracion. ALLOW_BANNER=true se reserva exclusivamente para instancias dedicadas autorizadas, dado que el MOTD es global.

Despues de comprobar lo anterior, configurar ALLOW_WRITES=true y ejecutar:

```powershell
.\.venv\Scripts\python.exe main.py --real
```

1. Menu 4, opcion 1: crear Loopback100 con Golden Config. Si ya existe una interfaz propia de pruebas, verificarla primero y no recrearla. El programa no sobrescribe interfaces existentes por POST.
2. Menu 1: comprobar el cumplimiento inicial.
3. Menu 3: iniciar Self-Healing periodico (Ctrl+C para detenerlo y volver al menu).
4. Desde Postman, introducir una desviacion en Loopback100. Ver el PATCH automatico y GET de comprobacion en Python.
5. Detener el servicio y usar menu 4, opcion 2 para crear Loopback101; opciones 3 y 4 para modificar su descripcion via PATCH y PUT. Opcion 5 para el banner, solo en una instancia dedicada.
6. Menu 5: mostrar y exportar reporte. Menu 0: exportar y salir.

### Prueba Postman (solo Loopback100 propia)

Method: PATCH
URL: `https://HOST:PUERTO/restconf/data/ietf-interfaces:interfaces/interface=Loopback100`
Authorization: Basic Auth con las credenciales actuales.
Headers: Accept y Content-Type = `application/yang-data+json`.
Body raw JSON:

```json
{
  "ietf-interfaces:interface": [
    {"name": "Loopback100", "enabled": false, "description": "Cambio externo de prueba"}
  ]
}
```

Enviar mientras esta activo el Self-Healing. La aplicacion debe detectar ambos cambios, enviar PATCH y verificar por GET. Si el router rechaza el formato, consultar la revision YANG y ejemplos de la version instalada. Para verificar independientemente por SSH: `show running-config interface Loopback100` y `show ip interface brief`. No guardar cambios globales ni modificar credenciales del router.

## 4. Archivos

- `main.py`: CLI, ciclos periodicos y demo.
- `restconf_client.py`: sesion HTTPS y operaciones RESTCONF, con proteccion de escritura.
- `audit.py`: compara descripcion, estado administrativo e IPv4 contra JSON de referencia.
- `remediation.py`: correccion y verificacion por GET; la ausencia de una interfaz se reporta para preparacion manual, no se crea automaticamente.
- `provisioning.py`: POST de Loopbacks, PATCH y PUT de descripcion, PUT de banner opcional.
- `reporting.py`: logs JSON por linea, estadisticas, reportes JSON y CSV por sesion.
- `mock_router.py`: simulador local en memoria.
- `config/golden_config.json`: politica de Loopback100 (Loopback101 queda fuera de la auditoria).
- `tests/`: pruebas unitarias y de integracion local.

## 5. Consideraciones tecnicas y limitaciones

- Los modelos elegidos son `ietf-interfaces`, `ietf-ip` y `Cisco-IOS-XE-native` (banner). Se usa GET con `content=config`; para `enabled` ausente se aplica el valor predeterminado true del modelo IETF, sujeto a comprobar desviaciones del fabricante.
- La remediacion de IPv4 usa PATCH con `application/yang-patch+json` (RFC 8072) para reemplazar solo el contenedor IPv4, ya que un PATCH de fusion podria conservar la direccion incorrecta. Requiere soporte del servidor. Si no lo admite, se registra fallo y no se intenta reemplazar toda la interfaz. Validar la representacion de direcciones y el soporte YANG Patch en el IOS XE real. El banner tambien puede variar segun revision del modelo.
- No hay validacion real de IOS XE todavia: el Sandbox rechazaba la autenticacion. Los endpoints y cuerpos son candidatos basados en los modelos y deben comprobarse en una instancia autorizada. El mock valida la logica de la aplicacion, no implementa un servidor HTTPS ni certifica compatibilidad con Cisco.
- Se cuentan observaciones de desviacion por parametro y ciclo, no incidentes unicos; se cuentan remediaciones por parametro. El tiempo promedio mide PATCH y comprobaciones asociadas, no el tiempo completo desde la introduccion de una anomalia. El cumplimiento es el ultimo verificado, no una medicion continua. Las estadisticas corresponden a la sesion actual. Los ciclos periodicos se ejecutan en primer plano; Ctrl+C vuelve al menu. En modo real, Postman actua como cliente externo mientras el ciclo se ejecuta.
- No ejecutar dos instancias de remediacion sobre las mismas interfaces. No usar en produccion. Revisar y limpiar los recursos de prueba con el administrador al terminar.

## 6. Fuentes tecnicas

- RFC 8040 RESTCONF: https://www.rfc-editor.org/rfc/rfc8040
- RFC 8072 YANG Patch: https://www.rfc-editor.org/rfc/rfc8072
- RFC 8343 Interfaces: https://www.rfc-editor.org/rfc/rfc8343
- Cisco IOS XE 17.9 RESTCONF: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/179/b_179_prog_restconf.html
- Cisco DevNet Sandbox: https://developer.cisco.com/site/sandbox/
