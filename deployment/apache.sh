#!/bin/sh
# This script assembles all the various apache configs provided by this
# project and others for usage by an IEM webfarm node

APPS="/opt"
CONFD="/etc/httpd/conf.d/"

cp -f /opt/iem/deployment/apache_configs/*.conf $CONFD

cp -f $APPS/sustainablecorn/config/apache-vhost.conf $CONFD/sustainablecorn.conf
cp -f $APPS/dep/config/apache-vhost.conf $CONFD/dailyerosion.conf
cp -f $APPS/datateam/config/datateam-vhost.conf $CONFD/datateam.conf
cp -f $APPS/datateam/config/datateam.inc $CONFD/datateam.inc
cp -f $APPS/weather.im/config/weather-im-vhost.conf $CONFD
cp -f $APPS/iem/config/mesonet.inc $CONFD
cp -f $APPS/iem/config/00iem.conf $CONFD
cp -f $APPS/iem/config/00iem-ssl.conf $CONFD
cp -f $APPS/vendor/conf/vendor.conf $CONFD
cp -f $APPS/weppwebsite/etc/apache_vhost.conf $CONFD/wepp.conf
cp -f $APPS/cocorahs/config/apache-vhost.conf $CONFD/cocorahs.conf
cp -f $APPS/nwnwebsite/deployment/schoolnet8-vhost.conf $CONFD/iem-schoolnet8.conf
cp -f $APPS/depbackend/config/apache-vhost.conf $CONFD/depbackend.conf
echo "Header set X-IEM-ServerID $(hostname)" > $CONFD/iemvs.conf

# Finally, reload httpd
systemctl reload httpd