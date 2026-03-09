#!/bin/bash

#set -x

wrkdir=/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb/pipeline
bin=/u01/app/oracle/product/fmw/OSBS/OSB12c/oracle_common/common/bin
shdir=/u01/app/oracle/admin/scripts/00-gitlab/SERVICEBUS/deploy_osb

## Cargo variables de entorno enviadas por GITLab
export $(xargs < ${wrkdir}/data)
echo $WLSTUSER

ls -l ${wrkdir}/*.jar  | awk '{ print $9 }' | while read arch
do
 echo "Instalando en Weblogic $arch ...."
 nombre="`echo $arch |  awk -F/ '{ print $5 }' | awk -F.jar '{ print $1 }'`"
 ${bin}/wlst.sh ${shdir}/rdeployWM.py
 ${bin}/wlst.sh ${shdir}/deployOSB.py "${arch}" "${nombre}"

done
