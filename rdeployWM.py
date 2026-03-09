# -*- coding: utf-8 -*-
# =======================================================================================
#
# Script para la creacion de WorkManagers en base a los servicios desplegados en el OSB.
#
# El flujo de ejecucion es el siguiente:
# 1. Parsea los archivos de customizacion de OSB para obtener los servicios de negocio y proxy.
# 2. Extrae los WorkManagers existentes del config.xml del dominio.
# 3. Compara los servicios encontrados con los WorkManagers existentes.
# 4. Genera archivos .properties para los WorkManagers que no existen.
# 5. Se conecta a WLST y crea los WorkManagers y sus constraints.
#
# =======================================================================================

from java.io import FileInputStream, File, ByteArrayInputStream
from java.util import Properties, Date
from javax.management import ObjectName
from java.text import SimpleDateFormat
from java.nio.file import Files, StandardCopyOption
from javax.xml.parsers import DocumentBuilderFactory
from javax.xml.xpath import XPathFactory, XPathConstants
import os, sys, traceback, codecs, re, jarray

# =======================================================================================
# CONFIGURACION
# =======================================================================================
# Rutas
BASE_PATH = "/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb"
PIPELINE_DIR = os.path.join(BASE_PATH, "pipeline")
LOGS_DIR = os.path.join(BASE_PATH, "source/logs")
WM_MAX_DIR = os.path.join(BASE_PATH, "source/wm_max")
WM_MIN_DIR = os.path.join(BASE_PATH, "source/wm_min")
CONFIG_XML_PATH = "/u01/app/oracle/admin/domains/TESTOSB/config/config.xml"

# Archivos de salida
CUSTOMIZATION_FILE = os.path.join(LOGS_DIR, "OSBCustomizationFile.txt")
EXISTING_WM_FILE = os.path.join(LOGS_DIR, "workmanagers.txt")
MATCH_FILE = os.path.join(LOGS_DIR, "match.txt")
WM_PROXY_PROPERTIES = os.path.join(WM_MAX_DIR, "WM_PS_Max.properties")
WM_BUSINESS_PROPERTIES = os.path.join(WM_MIN_DIR, "WM_BS_Min.properties")

# Configuracion WLST
WLST_URL = "t3://172.21.129.178:6210"
WLST_USER = os.environ["WLSTUSER"]
WLST_PASS = os.environ["WLSTPASS"]
WLST_DOMAIN_PATH = "/SelfTuning/TESTOSB"
CLUSTER_NAME = "OSB_Cluster"

# =======================================================================================
# FUNCIONES AUXILIARES
# =======================================================================================

def parse_osb_customization_files(input_dir, output_file):
    """
    ETAPA 1: Parsea los XML de customizacion de OSB para encontrar referencias
    a BusinessService y ProxyService, y escribe los resultados en un archivo.
    """
    print "--- ETAPA 1: Parseando archivos de customizacion de OSB ---"
    factory = DocumentBuilderFactory.newInstance()
    factory.setNamespaceAware(True)
    builder = factory.newDocumentBuilder()
    xpath = XPathFactory.newInstance().newXPath()
    xml_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".xml")]

    resultados_globales = {"BusinessService": [], "ProxyService": []}
    for archivo_entrada in xml_files:
        try:
            doc = builder.parse(archivo_entrada)
            nodes = xpath.evaluate("//*[local-name()='refsToSearch']", doc, XPathConstants.NODESET)
            for i in range(nodes.getLength()):
                ref = nodes.item(i)
                tipo = xpath.evaluate("./*[local-name()='type']/text()", ref).strip()
                path = xpath.evaluate("./*[local-name()='path']/text()", ref).strip()
                if tipo and path:
                    nombre = path.split("/")[-1]
                    if tipo in resultados_globales:
                        resultados_globales[tipo].append(nombre)
        except Exception, e:
            print "Advertencia: No se pudo parsear el archivo %s: %s" % (archivo_entrada, e)

    f = codecs.open(output_file, "w", "utf-8")
    try:
        for tipo, nombres in resultados_globales.items():
            f.write(u"%s: %d\n" % (tipo, len(nombres)))
            for nombre in nombres:
                f.write(u"Nombre: %s\n" % nombre)
            f.write(u"\n")
    finally:
        f.close()
    print "Archivo de customizacion generado en: %s" % output_file
    return resultados_globales

def extract_existing_work_managers(config_file, output_file):
    """
    ETAPA 2: Extrae los nombres de los WorkManagers existentes del config.xml,
    hace un backup del archivo y guarda los nombres en un archivo de texto.
    """
    print "--- ETAPA 2: Extrayendo WorkManagers existentes de %s ---" % config_file
    # Backup del config.xml
    try:
        fecha_hora = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss").format(Date())
        backup_file_path = os.path.join(os.path.dirname(config_file), "config_backup_%s.xml" % fecha_hora)
        origen = File(config_file).toPath()
        destino = File(backup_file_path).toPath()
        Files.copy(origen, destino, jarray.array([StandardCopyOption.REPLACE_EXISTING], StandardCopyOption))
        print "Backup de config.xml creado en: %s" % backup_file_path
    except Exception, e:
        raise Exception("Error al crear el backup de config.xml: " + str(e))

    f = open(config_file, "r")
    try:
        contenido = f.read()
    finally:
        f.close()

    # Limpiar XML para un parseo mas facil
    contenido = re.sub(r"<\?xml.*?\?>", "", contenido).strip()
    contenido = re.sub(r'xmlns="[^"]+"', "", contenido)
    contenido = "<root>%s</root>" % contenido

    bais = ByteArrayInputStream(contenido.encode("utf-8"))
    doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(bais)
    xpath = XPathFactory.newInstance().newXPath()
    nodes = xpath.evaluate("//work-manager/name/text()", doc, XPathConstants.NODESET)

    workmanagers = [nodes.item(i).getNodeValue().strip() for i in range(nodes.getLength()) if nodes.item(i).getNodeValue()]
    workmanagers.sort()

    f = codecs.open(output_file, "w", "utf-8")
    try:
        for nombre in workmanagers:
            f.write("%s\n" % nombre)
    finally:
        f.close()

    print "WorkManagers existentes guardados en: %s" % output_file
    return workmanagers

def _generate_properties_file(path, items, cluster):
    """
    Helper para escribir un archivo .properties con la lista de WMs.
    """
    f = codecs.open(path, "w", "utf-8")
    try:
        f.write("workmanager.count=%d\n" % len(items))
        idx = 1
        for nombre in items:
            f.write("workmanager.%d.name=%s\n" % (idx, nombre))
            f.write("workmanager.%d.cluster=%s\n" % (idx, cluster))
            f.write("workmanager.%d.max=1\n" % idx)
            idx += 1
    finally:
        f.close()
    print "Archivo de propiedades generado en: %s" % path

def compare_and_generate_properties(osb_services, existing_wms, match_file, proxy_props_file, business_props_file, cluster):
    """
    ETAPA 3: Compara los servicios OSB con los WMs existentes, identifica los que faltan
    y genera los archivos .properties correspondientes.
    """
    print "--- ETAPA 3: Comparando servicios y generando archivos .properties ---"
    nombres_osb = []
    for tipo, nombres in osb_services.items():
        for nombre in nombres:
            nombres_osb.append((tipo, nombre))

    no_existen = []
    f_match = codecs.open(match_file, "w", "utf-8")
    try:
        f_match.write("=== Diagnostico WorkManagers ===\n")
        for tipo, nombre in nombres_osb:
            nombre_l = nombre.lower()
            encontrado = False
            for w in existing_wms:
                if nombre_l in w.lower():
                    encontrado = True
                    break

            if not encontrado:
                no_existen.append((tipo, nombre))
                f_match.write("NO EXISTE: Tipo=%s, Nombre=%s\n" % (tipo, nombre))
            else:
                f_match.write("EXISTE: Tipo=%s, Nombre=%s\n" % (tipo, nombre))
    finally:
        f_match.close()

    proxies_a_crear = [n for t, n in no_existen if t == "ProxyService"]
    businesses_a_crear = [n for t, n in no_existen if t == "BusinessService"]

    _generate_properties_file(proxy_props_file, proxies_a_crear, cluster)
    _generate_properties_file(business_props_file, businesses_a_crear, cluster)

    print "Diagnostico guardado en: %s" % match_file

def _create_wm_and_constraints(base_path, wm_name, cluster, min_threads, max_threads):
    """
    Crea un WorkManager y sus constraints (Min/Max Threads) si no existen.
    Retorna True si el WM fue creado, False si ya existia.
    """
    max_name = wm_name + "_MaxThreadsConstraint"
    min_name = wm_name + "_MinThreadsConstraint" # Asumiendo nombre para MinThreads

    # Crear MaxThreadsConstraint si es necesario
    if max_threads is not None and getMBean(base_path + "/MaxThreadsConstraints/" + max_name) is None:
        print "Creando MaxThreadsConstraint: %s" % max_name
        cd(base_path)
        cmo.createMaxThreadsConstraint(max_name)
        cd(base_path + "/MaxThreadsConstraints/" + max_name)
        cmo.setCount(int(max_threads))
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

    # Crear MinThreadsConstraint si es necesario
    if min_threads is not None and getMBean(base_path + "/MinThreadsConstraints/" + min_name) is None:
        print "Creando MinThreadsConstraint: %s" % min_name
        cd(base_path)
        cmo.createMinThreadsConstraint(min_name)
        cd(base_path + "/MinThreadsConstraints/" + min_name)
        cmo.setCount(int(min_threads))
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

    # Crear WorkManager si no existe
    if getMBean(base_path + "/WorkManagers/" + wm_name) is None:
        print "Creando WorkManager: %s" % wm_name
        cd(base_path)
        cmo.createWorkManager(wm_name)
        cd(base_path + "/WorkManagers/" + wm_name)
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

        # Asignar constraints
        if max_threads is not None:
            cmo.setMaxThreadsConstraint(getMBean(base_path + "/MaxThreadsConstraints/" + max_name))
        if min_threads is not None:
            cmo.setMinThreadsConstraint(getMBean(base_path + "/MinThreadsConstraints/" + min_name))

        return True # Creado
    return False # Ya existia

def deploy_work_managers_from_properties(wlst_config, props_business_file, props_proxy_file):
    """
    ETAPA 4: Se conecta a WLST y crea los WorkManagers definidos en los
    archivos .properties.
    """
    print "--- ETAPA 4: Conectando a WLST y desplegando WorkManagers ---"
    connect(wlst_config['user'], wlst_config['pass'], wlst_config['url'])
    edit()
    startEdit()

    workmanagers_creados = []
    workmanagers_existentes = []

    try:
        try:
            # Procesar Business Services
            props_bs = Properties()
            fis = FileInputStream(props_business_file)
            try:
                props_bs.load(fis)
            finally:
                fis.close()

            count_bs = int(props_bs.getProperty("workmanager.count", "0"))
            print "Procesando %d BusinessService WorkManagers..." % count_bs
            for i in range(1, count_bs + 1):
                name = props_bs.getProperty("workmanager.%d.name" % i)
                cluster = props_bs.getProperty("workmanager.%d.cluster" % i)
                wm_name = name + "_BS-WorkManager"

                if _create_wm_and_constraints(wlst_config['domain_path'], wm_name, cluster, 1, None):
                    workmanagers_creados.append(wm_name)
                else:
                    workmanagers_existentes.append(wm_name)

            # Procesar Proxy Services
            props_ps = Properties()
            fis = FileInputStream(props_proxy_file)
            try:
                props_ps.load(fis)
            finally:
                fis.close()

            count_ps = int(props_ps.getProperty("workmanager.count", "0"))
            print "Procesando %d ProxyService WorkManagers..." % count_ps
            for i in range(1, count_ps + 1):
                name = props_ps.getProperty("workmanager.%d.name" % i)
                cluster = props_ps.getProperty("workmanager.%d.cluster" % i)
                wm_name = name + "_PS-WorkManager"

                if _create_wm_and_constraints(wlst_config['domain_path'], wm_name, cluster, None, 1):
                    workmanagers_creados.append(wm_name)
                else:
                    workmanagers_existentes.append(wm_name)

            save()
            activate()
            print "Cambios guardados y activados en WebLogic."

        except Exception, e:
            print "ERROR durante el despliegue de WorkManagers. Cancelando edicion..."
            cancelEdit('y')
            # Re-lanza la excepcion para que el bloque principal la capture
            raise e
    finally:
        disconnect()
        print "Desconectado de WLST."

    return workmanagers_creados, workmanagers_existentes

def deployWM():
    """
    Funcion principal que orquesta todo el proceso.
    """
    try:
        # ETAPA 1
        osb_services = parse_osb_customization_files(PIPELINE_DIR, CUSTOMIZATION_FILE)

        # ETAPA 2
        existing_wms = extract_existing_work_managers(CONFIG_XML_PATH, EXISTING_WM_FILE)

        # ETAPA 3
        compare_and_generate_properties(osb_services, existing_wms, MATCH_FILE, WM_PROXY_PROPERTIES, WM_BUSINESS_PROPERTIES, CLUSTER_NAME)

        # ETAPA 4
        wlst_config = {
            'url': WLST_URL,
            'user': WLST_USER,
            'pass': WLST_PASS,
            'domain_path': WLST_DOMAIN_PATH
        }
        creados, existentes = deploy_work_managers_from_properties(wlst_config, WM_BUSINESS_PROPERTIES, WM_PROXY_PROPERTIES)

        # RESUMEN FINAL
        print "\n=== RESUMEN DE WORKMANAGERS ==="
        if creados:
            print "Se crearon los siguientes WorkManagers:"
            for wm in creados:
                print "  - %s" % wm
        else:
            print "No se crearon WorkManagers nuevos."

        if existentes:
            print "\nLos siguientes WorkManagers ya existian o no necesitaron creacion:"
            for wm in existentes:
                print "  - %s" % wm

        print "Script finalizado con exito."

    except Exception, e:
        print "ERROR FATAL en la ejecucion: %s" % e
        traceback.print_exc()
        print "Script finalizado con error."
        # El disconnect y cancelEdit se manejan en las funciones internas

deployWM()


oracle@tsoladm0:/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb$ cat rdeployWM.py
# -*- coding: utf-8 -*-
# =======================================================================================
#
# Script para la creacion de WorkManagers en base a los servicios desplegados en el OSB.
#
# El flujo de ejecucion es el siguiente:
# 1. Parsea los archivos de customizacion de OSB para obtener los servicios de negocio y proxy.
# 2. Extrae los WorkManagers existentes del config.xml del dominio.
# 3. Compara los servicios encontrados con los WorkManagers existentes.
# 4. Genera archivos .properties para los WorkManagers que no existen.
# 5. Se conecta a WLST y crea los WorkManagers y sus constraints.
#
# =======================================================================================

from java.io import FileInputStream, File, ByteArrayInputStream
from java.util import Properties, Date
from javax.management import ObjectName
from java.text import SimpleDateFormat
from java.nio.file import Files, StandardCopyOption
from javax.xml.parsers import DocumentBuilderFactory
from javax.xml.xpath import XPathFactory, XPathConstants
import os, sys, traceback, codecs, re, jarray

# =======================================================================================
# CONFIGURACION
# =======================================================================================
# Rutas
BASE_PATH = "/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb"
PIPELINE_DIR = os.path.join(BASE_PATH, "pipeline")
LOGS_DIR = os.path.join(BASE_PATH, "source/logs")
WM_MAX_DIR = os.path.join(BASE_PATH, "source/wm_max")
WM_MIN_DIR = os.path.join(BASE_PATH, "source/wm_min")
CONFIG_XML_PATH = "/u01/app/oracle/admin/domains/TESTOSB/config/config.xml"

# Archivos de salida
CUSTOMIZATION_FILE = os.path.join(LOGS_DIR, "OSBCustomizationFile.txt")
EXISTING_WM_FILE = os.path.join(LOGS_DIR, "workmanagers.txt")
MATCH_FILE = os.path.join(LOGS_DIR, "match.txt")
WM_PROXY_PROPERTIES = os.path.join(WM_MAX_DIR, "WM_PS_Max.properties")
WM_BUSINESS_PROPERTIES = os.path.join(WM_MIN_DIR, "WM_BS_Min.properties")

# Configuracion WLST
WLST_URL = "t3://172.21.129.178:6210"
WLST_USER = os.environ["WLSTUSER"]
WLST_PASS = os.environ["WLSTPASS"]
WLST_DOMAIN_PATH = "/SelfTuning/TESTOSB"
CLUSTER_NAME = "OSB_Cluster"

# =======================================================================================
# FUNCIONES AUXILIARES
# =======================================================================================

def parse_osb_customization_files(input_dir, output_file):
    """
    ETAPA 1: Parsea los XML de customizacion de OSB para encontrar referencias
    a BusinessService y ProxyService, y escribe los resultados en un archivo.
    """
    print "--- ETAPA 1: Parseando archivos de customizacion de OSB ---"
    factory = DocumentBuilderFactory.newInstance()
    factory.setNamespaceAware(True)
    builder = factory.newDocumentBuilder()
    xpath = XPathFactory.newInstance().newXPath()
    xml_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".xml")]

    resultados_globales = {"BusinessService": [], "ProxyService": []}
    for archivo_entrada in xml_files:
        try:
            doc = builder.parse(archivo_entrada)
            nodes = xpath.evaluate("//*[local-name()='refsToSearch']", doc, XPathConstants.NODESET)
            for i in range(nodes.getLength()):
                ref = nodes.item(i)
                tipo = xpath.evaluate("./*[local-name()='type']/text()", ref).strip()
                path = xpath.evaluate("./*[local-name()='path']/text()", ref).strip()
                if tipo and path:
                    nombre = path.split("/")[-1]
                    if tipo in resultados_globales:
                        resultados_globales[tipo].append(nombre)
        except Exception, e:
            print "Advertencia: No se pudo parsear el archivo %s: %s" % (archivo_entrada, e)

    f = codecs.open(output_file, "w", "utf-8")
    try:
        for tipo, nombres in resultados_globales.items():
            f.write(u"%s: %d\n" % (tipo, len(nombres)))
            for nombre in nombres:
                f.write(u"Nombre: %s\n" % nombre)
            f.write(u"\n")
    finally:
        f.close()
    print "Archivo de customizacion generado en: %s" % output_file
    return resultados_globales

def extract_existing_work_managers(config_file, output_file):
    """
    ETAPA 2: Extrae los nombres de los WorkManagers existentes del config.xml,
    hace un backup del archivo y guarda los nombres en un archivo de texto.
    """
    print "--- ETAPA 2: Extrayendo WorkManagers existentes de %s ---" % config_file
    # Backup del config.xml
    try:
        fecha_hora = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss").format(Date())
        backup_file_path = os.path.join(os.path.dirname(config_file), "config_backup_%s.xml" % fecha_hora)
        origen = File(config_file).toPath()
        destino = File(backup_file_path).toPath()
        Files.copy(origen, destino, jarray.array([StandardCopyOption.REPLACE_EXISTING], StandardCopyOption))
        print "Backup de config.xml creado en: %s" % backup_file_path
    except Exception, e:
        raise Exception("Error al crear el backup de config.xml: " + str(e))

    f = open(config_file, "r")
    try:
        contenido = f.read()
    finally:
        f.close()

    # Limpiar XML para un parseo mas facil
    contenido = re.sub(r"<\?xml.*?\?>", "", contenido).strip()
    contenido = re.sub(r'xmlns="[^"]+"', "", contenido)
    contenido = "<root>%s</root>" % contenido

    bais = ByteArrayInputStream(contenido.encode("utf-8"))
    doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(bais)
    xpath = XPathFactory.newInstance().newXPath()
    nodes = xpath.evaluate("//work-manager/name/text()", doc, XPathConstants.NODESET)

    workmanagers = [nodes.item(i).getNodeValue().strip() for i in range(nodes.getLength()) if nodes.item(i).getNodeValue()]
    workmanagers.sort()

    f = codecs.open(output_file, "w", "utf-8")
    try:
        for nombre in workmanagers:
            f.write("%s\n" % nombre)
    finally:
        f.close()

    print "WorkManagers existentes guardados en: %s" % output_file
    return workmanagers

def _generate_properties_file(path, items, cluster):
    """
    Helper para escribir un archivo .properties con la lista de WMs.
    """
    f = codecs.open(path, "w", "utf-8")
    try:
        f.write("workmanager.count=%d\n" % len(items))
        idx = 1
        for nombre in items:
            f.write("workmanager.%d.name=%s\n" % (idx, nombre))
            f.write("workmanager.%d.cluster=%s\n" % (idx, cluster))
            f.write("workmanager.%d.max=1\n" % idx)
            idx += 1
    finally:
        f.close()
    print "Archivo de propiedades generado en: %s" % path

def compare_and_generate_properties(osb_services, existing_wms, match_file, proxy_props_file, business_props_file, cluster):
    """
    ETAPA 3: Compara los servicios OSB con los WMs existentes, identifica los que faltan
    y genera los archivos .properties correspondientes.
    """
    print "--- ETAPA 3: Comparando servicios y generando archivos .properties ---"
    nombres_osb = []
    for tipo, nombres in osb_services.items():
        for nombre in nombres:
            nombres_osb.append((tipo, nombre))

    no_existen = []
    f_match = codecs.open(match_file, "w", "utf-8")
    try:
        f_match.write("=== Diagnostico WorkManagers ===\n")
        for tipo, nombre in nombres_osb:
            nombre_l = nombre.lower()
            encontrado = False
            for w in existing_wms:
                if nombre_l in w.lower():
                    encontrado = True
                    break

            if not encontrado:
                no_existen.append((tipo, nombre))
                f_match.write("NO EXISTE: Tipo=%s, Nombre=%s\n" % (tipo, nombre))
            else:
                f_match.write("EXISTE: Tipo=%s, Nombre=%s\n" % (tipo, nombre))
    finally:
        f_match.close()

    proxies_a_crear = [n for t, n in no_existen if t == "ProxyService"]
    businesses_a_crear = [n for t, n in no_existen if t == "BusinessService"]

    _generate_properties_file(proxy_props_file, proxies_a_crear, cluster)
    _generate_properties_file(business_props_file, businesses_a_crear, cluster)

    print "Diagnostico guardado en: %s" % match_file

def _create_wm_and_constraints(base_path, wm_name, cluster, min_threads, max_threads):
    """
    Crea un WorkManager y sus constraints (Min/Max Threads) si no existen.
    Retorna True si el WM fue creado, False si ya existia.
    """
    max_name = wm_name + "_MaxThreadsConstraint"
    min_name = wm_name + "_MinThreadsConstraint" # Asumiendo nombre para MinThreads

    # Crear MaxThreadsConstraint si es necesario
    if max_threads is not None and getMBean(base_path + "/MaxThreadsConstraints/" + max_name) is None:
        print "Creando MaxThreadsConstraint: %s" % max_name
        cd(base_path)
        cmo.createMaxThreadsConstraint(max_name)
        cd(base_path + "/MaxThreadsConstraints/" + max_name)
        cmo.setCount(int(max_threads))
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

    # Crear MinThreadsConstraint si es necesario
    if min_threads is not None and getMBean(base_path + "/MinThreadsConstraints/" + min_name) is None:
        print "Creando MinThreadsConstraint: %s" % min_name
        cd(base_path)
        cmo.createMinThreadsConstraint(min_name)
        cd(base_path + "/MinThreadsConstraints/" + min_name)
        cmo.setCount(int(min_threads))
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

    # Crear WorkManager si no existe
    if getMBean(base_path + "/WorkManagers/" + wm_name) is None:
        print "Creando WorkManager: %s" % wm_name
        cd(base_path)
        cmo.createWorkManager(wm_name)
        cd(base_path + "/WorkManagers/" + wm_name)
        set('Targets', jarray.array([ObjectName("com.bea:Name=" + cluster + ",Type=Cluster")], ObjectName))

        # Asignar constraints
        if max_threads is not None:
            cmo.setMaxThreadsConstraint(getMBean(base_path + "/MaxThreadsConstraints/" + max_name))
        if min_threads is not None:
            cmo.setMinThreadsConstraint(getMBean(base_path + "/MinThreadsConstraints/" + min_name))

        return True # Creado
    return False # Ya existia

def deploy_work_managers_from_properties(wlst_config, props_business_file, props_proxy_file):
    """
    ETAPA 4: Se conecta a WLST y crea los WorkManagers definidos en los
    archivos .properties.
    """
    print "--- ETAPA 4: Conectando a WLST y desplegando WorkManagers ---"
    connect(wlst_config['user'], wlst_config['pass'], wlst_config['url'])
    edit()
    startEdit()

    workmanagers_creados = []
    workmanagers_existentes = []

    try:
        try:
            # Procesar Business Services
            props_bs = Properties()
            fis = FileInputStream(props_business_file)
            try:
                props_bs.load(fis)
            finally:
                fis.close()

            count_bs = int(props_bs.getProperty("workmanager.count", "0"))
            print "Procesando %d BusinessService WorkManagers..." % count_bs
            for i in range(1, count_bs + 1):
                name = props_bs.getProperty("workmanager.%d.name" % i)
                cluster = props_bs.getProperty("workmanager.%d.cluster" % i)
                wm_name = name + "_BS-WorkManager"

                if _create_wm_and_constraints(wlst_config['domain_path'], wm_name, cluster, 1, None):
                    workmanagers_creados.append(wm_name)
                else:
                    workmanagers_existentes.append(wm_name)

            # Procesar Proxy Services
            props_ps = Properties()
            fis = FileInputStream(props_proxy_file)
            try:
                props_ps.load(fis)
            finally:
                fis.close()

            count_ps = int(props_ps.getProperty("workmanager.count", "0"))
            print "Procesando %d ProxyService WorkManagers..." % count_ps
            for i in range(1, count_ps + 1):
                name = props_ps.getProperty("workmanager.%d.name" % i)
                cluster = props_ps.getProperty("workmanager.%d.cluster" % i)
                wm_name = name + "_PS-WorkManager"

                if _create_wm_and_constraints(wlst_config['domain_path'], wm_name, cluster, None, 1):
                    workmanagers_creados.append(wm_name)
                else:
                    workmanagers_existentes.append(wm_name)

            save()
            activate()
            print "Cambios guardados y activados en WebLogic."

        except Exception, e:
            print "ERROR durante el despliegue de WorkManagers. Cancelando edicion..."
            cancelEdit('y')
            # Re-lanza la excepcion para que el bloque principal la capture
            raise e
    finally:
        disconnect()
        print "Desconectado de WLST."

    return workmanagers_creados, workmanagers_existentes

def deployWM():
    """
    Funcion principal que orquesta todo el proceso.
    """
    try:
        # ETAPA 1
        osb_services = parse_osb_customization_files(PIPELINE_DIR, CUSTOMIZATION_FILE)

        # ETAPA 2
        existing_wms = extract_existing_work_managers(CONFIG_XML_PATH, EXISTING_WM_FILE)

        # ETAPA 3
        compare_and_generate_properties(osb_services, existing_wms, MATCH_FILE, WM_PROXY_PROPERTIES, WM_BUSINESS_PROPERTIES, CLUSTER_NAME)

        # ETAPA 4
        wlst_config = {
            'url': WLST_URL,
            'user': WLST_USER,
            'pass': WLST_PASS,
            'domain_path': WLST_DOMAIN_PATH
        }
        creados, existentes = deploy_work_managers_from_properties(wlst_config, WM_BUSINESS_PROPERTIES, WM_PROXY_PROPERTIES)

        # RESUMEN FINAL
        print "\n=== RESUMEN DE WORKMANAGERS ==="
        if creados:
            print "Se crearon los siguientes WorkManagers:"
            for wm in creados:
                print "  - %s" % wm
        else:
            print "No se crearon WorkManagers nuevos."

        if existentes:
            print "\nLos siguientes WorkManagers ya existian o no necesitaron creacion:"
            for wm in existentes:
                print "  - %s" % wm

        print "Script finalizado con exito."

    except Exception, e:
        print "ERROR FATAL en la ejecucion: %s" % e
        traceback.print_exc()
        print "Script finalizado con error."
        # El disconnect y cancelEdit se manejan en las funciones internas

deployWM()
