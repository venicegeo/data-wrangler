# copy files
sudo mkdir -p /config/mongo

sudo chown -R vagrant:vagrant /config
sudo cp -R /vagrant/datawrangler /config
sudo chown -R vagrant:vagrant /config/datawrangler
sudo chmod 755 /config/datawrangler/DataSources

# https://docs.mongodb.org/master/tutorial/install-mongodb-on-red-hat/

# Add mongo repo
sudo echo "[mongodb-org-3.2]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/7/mongodb-org/3.2/x86_64/
gpgcheck=0
enabled=1" > /etc/yum.repos.d/mongodb-org-3.2.repo 

# Install mongod
sudo yum install -y mongodb-org
chown mongod:mongod /config/mongo/

# Required if using selinux
# sudo semanage port -a -t mongod_port_t -p tcp 27017
  
# Ensure mongod on startup
chkconfig mongod on
  
# Restart mongo
sudo sh -c 'service mongod start ; true'

# update python (2.7)
sudo yum install python -y

# install pip
sudo easy_install pip

# Add mongo repo
sudo echo "[mongodb-org-3.2]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/7/mongodb-org/3.2/x86_64/
gpgcheck=0
enabled=1" > /etc/yum.repos.d/mongodb-org-3.2.repo 

# add gdal (for importing etc.)
sudo yum install gdal -y
sudo yum install gdal-devel -y
sudo yum install gdal-python -y

# pip install python reqs
sudo pip install pymongo
sudo pip install requests
sudo pip install xlrd 
sudo pip install unicodecsv


# setup geoserver
sudo yum install tomcat -y
sudo yum install unzip -y
wget -O /config/geoserver.zip http://downloads.sourceforge.net/project/geoserver/GeoServer/2.8.1/geoserver-2.8.1-war.zip?r=http%3A%2F%2Fsourceforge.net%2Fprojects%2Fgeoserver%2Ffiles%2FGeoServer%2F2.8.1%2F&ts=1451930791&use_mirror=skylineservers	
wget -O /config/importer.zip http://downloads.sourceforge.net/project/geoserver/GeoServer/2.8.1/extensions/geoserver-2.8.1-importer-plugin.zip?r=http%3A%2F%2Fsourceforge.net%2Fprojects%2Fgeoserver%2Ffiles%2FGeoServer%2F2.8.1%2Fextensions%2F&ts=1451920154&use_mirror=iweb
wait
unzip /config/geoserver.zip -d /config/geoserver
unzip /config/importer.zip -d /config/importer 
sudo mv /config/geoserver/geoserver.war /usr/share/tomcat/webapps/
sudo /bin/systemctl restart tomcat.service
sudo rm -rf /config/geoserver
sudo rm -rf /config/geoserver.zip
sudo mv -f /config/importer/* /usr/share/tomcat/webapps/geoserver/WEB-INF/lib/ 
sudo rm -rf /config/importer
sudo rm -rf /config/importer.zip
sudo chown tomcat:tomcat /usr/share/tomcat/webapps/geoserver/WEB-INF/lib/

sudo /bin/systemctl restart tomcat.service
sudo /bin/systemctl enable tomcat.service

# setup postgis
sudo rpm -ivh http://yum.postgresql.org/9.4/redhat/rhel-7-x86_64/pgdg-redhat94-9.4-2.noarch.rpm
sudo yum install postgresql94 postgresql94-server postgresql94-libs postgresql94-contrib -y
sudo yum install postgis2_94 -y
sudo -u postgres /usr/pgsql-9.4/bin/pg_ctl initdb -D /var/lib/pgsql/9.4/data
sudo /bin/systemctl start postgresql-9.4.service
sudo /bin/systemctl enable postgresql-9.4.service

sudo -u postgres /usr/pgsql-9.4/bin/psql -c "CREATE ROLE importer LOGIN PASSWORD 'importer';"
sudo -u postgres /usr/pgsql-9.4/bin/psql -c "CREATE DATABASE imports WITH OWNER importer;"
sudo -u postgres /usr/pgsql-9.4/bin/psql -d "imports" -c "CREATE EXTENSION postgis;"
sudo -u postgres /usr/pgsql-9.4/bin/psql -d "imports" -c "SELECT postgis_full_version();"

sudo -u vagrant sh -c "cd /config/datawrangler ; ./example.py"
