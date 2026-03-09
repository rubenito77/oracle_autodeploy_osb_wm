OSB WorkManager Auto Deployment

Automatización para la creación de WorkManagers en Oracle Service Bus (OSB) mediante Jython + WLST.

Este script detecta automáticamente los servicios definidos en los archivos de customización de OSB, verifica los WorkManagers existentes en el dominio WebLogic, y crea los WorkManagers faltantes junto con sus Thread Constraints.

El objetivo es eliminar la creación manual de WorkManagers y mantener el dominio sincronizado con los servicios desplegados.

Características

Descubre automáticamente BusinessServices y ProxyServices

Extrae los WorkManagers existentes desde config.xml

Detecta WorkManagers faltantes

Genera configuración intermedia en .properties

Despliega WorkManagers automáticamente mediante WLST

Crea Thread Constraints

Asigna recursos al cluster de OSB

Genera logs de diagnóstico

Arquitectura
OSB Customization XML
        │
        ▼
Parse XML
(Detecta BusinessServices / ProxyServices)
        │
        ▼
Lectura config.xml
(WorkManagers existentes)
        │
        ▼
Comparación
Servicios vs WorkManagers
        │
        ▼
Generación archivos .properties
        │
        ▼
WLST Deployment
        │
        ▼
Creación automática
WorkManagers + Constraints
Flujo de ejecución

El script ejecuta las siguientes etapas:

Etapa	Descripción
1	Parseo de XML de customización de OSB
2	Extracción de WorkManagers existentes
3	Comparación de servicios vs WorkManagers
4	Generación de archivos .properties
5	Creación de WorkManagers mediante WLST
Estructura del repositorio
deploy_osb/
│
├─ pipeline/
│   └─ XML de customización OSB
│
├─ source/
│   ├─ logs/
│   │   ├─ OSBCustomizationFile.txt
│   │   ├─ workmanagers.txt
│   │   └─ match.txt
│   │
│   ├─ wm_max/
│   │   └─ WM_PS_Max.properties
│   │
│   └─ wm_min/
│       └─ WM_BS_Min.properties
│
└─ deployWM.py
Prerrequisitos
Software requerido

Oracle WebLogic Server

Oracle Service Bus

WLST

Python/Jython (incluido en WLST)

Acceso necesario

Acceso al dominio WebLogic

Acceso al archivo:

/config/config.xml

Permiso de edición del dominio

Variables de entorno

El script obtiene las credenciales desde variables de entorno.

export WLSTUSER=weblogic
export WLSTPASS=password

Esto evita hardcodear credenciales dentro del script.

Configuración

Variables principales dentro del script:

BASE_PATH = "/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb"

PIPELINE_DIR = BASE_PATH + "/pipeline"
LOGS_DIR = BASE_PATH + "/source/logs"

WM_MAX_DIR = BASE_PATH + "/source/wm_max"
WM_MIN_DIR = BASE_PATH + "/source/wm_min"

CONFIG_XML_PATH = "/u01/app/oracle/admin/domains/TESTOSB/config/config.xml"

Configuración WLST:

WLST_URL = "t3://172.21.129.178:6210"

WLST_DOMAIN_PATH = "/SelfTuning/TESTOSB"

CLUSTER_NAME = "OSB_Cluster"
Archivos generados
Logs
source/logs/
Archivo	Descripción
OSBCustomizationFile.txt	Servicios detectados
workmanagers.txt	WorkManagers existentes
match.txt	Diagnóstico de comparación
Properties
source/wm_max/
source/wm_min/
Archivo	Uso
WM_PS_Max.properties	WorkManagers de ProxyService
WM_BS_Min.properties	WorkManagers de BusinessService
Creación de WorkManagers

El script crea automáticamente WorkManagers según el tipo de servicio.

ProxyService

Se crea:

<Servicio>_PS-WorkManager

Constraint asociado:

MaxThreadsConstraint = 1

Ejemplo:

Payment_PS-WorkManager
Payment_PS-WorkManager_MaxThreadsConstraint
BusinessService

Se crea:

<Servicio>_BS-WorkManager

Constraint asociado:

MinThreadsConstraint = 1

Ejemplo:

Customer_BS-WorkManager
Customer_BS-WorkManager_MinThreadsConstraint
Ejecución

Ejecutar desde WLST:

$WL_HOME/common/bin/wlst.sh deployWM.py
Ejemplo de salida
--- ETAPA 1: Parseando archivos de customizacion de OSB ---

--- ETAPA 2: Extrayendo WorkManagers existentes ---

--- ETAPA 3: Comparando servicios y generando archivos .properties ---

--- ETAPA 4: Conectando a WLST y desplegando WorkManagers ---

Resumen final:

=== RESUMEN DE WORKMANAGERS ===

Se crearon los siguientes WorkManagers:
 - Payment_PS-WorkManager
 - Customer_BS-WorkManager

Los siguientes WorkManagers ya existian:
 - Billing_PS-WorkManager
Troubleshooting
Error de conexión WLST

Verificar:

URL correcta

credenciales

acceso al AdminServer

No se crean WorkManagers

Verificar:

XML de customización en pipeline/

coincidencias en match.txt

Error en edición WLST

Si ocurre un error durante la edición del dominio, el script ejecuta automáticamente:

cancelEdit('y')

Esto revierte los cambios.

Consideraciones
Comparación parcial

La comparación usa coincidencia parcial:

if nombre_l in w.lower()

Esto puede considerar existente un WorkManager cuyo nombre contenga el servicio.

No elimina recursos

El script solo crea recursos faltantes.

Nunca elimina ni modifica WorkManagers existentes.

Beneficios

Automatiza la administración de WorkManagers

Reduce errores manuales

Mantiene consistencia entre OSB y WebLogic

Simplifica despliegues en entornos grandes

Autor

Script desarrollado para automatización de administración en entornos Oracle Service Bus / WebLogic.
