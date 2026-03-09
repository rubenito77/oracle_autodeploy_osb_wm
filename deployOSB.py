from java.util import HashMap
from java.util import HashSet
from java.util import ArrayList
from java.io import FileInputStream

from com.bea.wli.sb.util import Refs
from com.bea.wli.config.customization import Customization
from com.bea.wli.sb.management.importexport import ALSBImportOperation

from os.path import exists

import sys
import os

#=======================================================================================
# Funcion para deployar
#=======================================================================================

def importToALSBDomain():
    try:
        SessionMBean = None

        connectToServer(importUser, importPassword, adminUrl)
        print "    [INFO] Iniciando el deploy de \033[95m", importJar, "\033[0m en el servidor \033[95m", adminUrl, "\033[0m "
        theBytes = readBinaryFile(importJar)
        print "    [INFO] Leyendo archivo \033[95m", importJar, "\033[0m..."
        sessionName = createSessionName(paquete)
        print "    [INFO] Creando sesion \033[95m", sessionName, "\033[0m..."
        SessionMBean = getSessionManagementMBean(sessionName)
        print "    \033[92m[OK] Sesion creada \033[0m"
        ALSBConfigurationMBean = findService(String("ALSBConfiguration.").concat(sessionName), "com.bea.wli.sb.management.configuration.ALSBConfigurationMBean")
        print "    [INFO] Servicio MBean ALSBConfiguration encontrado \033[95m", ALSBConfigurationMBean, "\033[0m..."
        ALSBConfigurationMBean.uploadJarFile(theBytes)
        print "    \033[92m[OK] El JAR se subio al server correctamente \033[0m "
        print "    [INFO] Aplicando el jar al server..."
        alsbJarInfo = ALSBConfigurationMBean.getImportJarInfo()
        alsbImportPlan = alsbJarInfo.getDefaultImportPlan()
        alsbImportPlan.setPassphrase(passphrase)
        alsbImportPlan.setPreserveExistingEnvValues(True)
        importResult = ALSBConfigurationMBean.importUploaded(alsbImportPlan)

        if exists(customFile):
            print "    [INFO] Aplicando el archivo de customizacion", customFile
            iStream = FileInputStream(customFile)
            customizationList = Customization.fromXML(iStream)
            ALSBConfigurationMBean.customize(customizationList)
        else:
            print "    [INFO] No existe archivo de customizacion"

        print "    [INFO] Activando los cambios en el server"

        SessionMBean.activateSession(sessionName, "Se aplicaron los cambios del paquete " + paquete)
        print "    \033[92m[OK] El deploy del archivo", importJar, "se ejecuto correctamente \033[0m"
    except:
        print "    \033[91m**************************************************************************\033[0m "
        print "    \033[91m[ERROR] Error no esperado:\033[0m"
        print "    \033[91m[ERROR]", sys.exc_info()[0], "\033[0m"
        print "    \033[91m**************************************************************************\033[0m "
        if SessionMBean != None:
            SessionMBean.discardSession(sessionName)
        raise


#=======================================================================================
# Conexion al Admin Server
#=======================================================================================

def connectToServer(username, password, url):
    connect(username, password, url)
    domainRuntime()

#=======================================================================================
# Lectura del jar
#=======================================================================================
def readBinaryFile(fileName):
    file = open(fileName, 'rb')
    bytes = file.read()
    return bytes

#=======================================================================================
# Generacion del nombre de la sesion
#=======================================================================================
def createSessionName(paquete):
    sessionName = String(paquete + "-" + Long(System.currentTimeMillis()).toString())
    return sessionName

#=======================================================================================
# Creacion de la sesion en el OSB
#=======================================================================================
def getSessionManagementMBean(sessionName):
    SessionMBean = findService("SessionManagement", "com.bea.wli.sb.management.configuration.SessionManagementMBean")
    SessionMBean.createSession(sessionName)
    return SessionMBean

# Script que se ejecuta inicialmente
try:
    importPort = os.environ["PUERTO"]
    adminUrl = "t3://tsoladm0.mngt.osde.ar:" + importPort
    importUser = os.environ["OSBUSER"]
    importJar = sys.argv[1]
    paquete = sys.argv[2]
    importPassword = os.environ["OSBPASS"]
    passphrase = ""
    customFile = importJar.replace('.jar', '.xml')

    importToALSBDomain()

except:
    print "    \033[91m**************************************************************************\033[0m "
    print "    \033[91m[ERROR] No se pudo realizar el deploy\033[0m"
    print "    \033[91m[ERROR]", sys.exc_info()[0], "\033[0m"
    print "    \033[91m**************************************************************************\033[0m "
    dumpStack()
    raise

