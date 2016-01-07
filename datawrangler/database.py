#!/usr/bin/python
import pymongo
import subprocess
import sys
import os
import re
import getpass
import requests
import json
import csv
from zipfile import ZipFile
from osgeo import ogr
import xlrd
import unicodecsv 
import datetime
import math
from chardet.universaldetector import UniversalDetector


class DB:

    def __init__(self,
                 user=None,
                 password=None,
                 host='127.0.0.1',
                 port=27017,
                 database='geodata',
                 temp_dir = "./DataSources",
                 csv_file = None):
        self.user = user
        self.password = password
        self.geoserver_user = None
        self.geoserver_password = None
        self.host = host
        self.port = port
        self.connection = pymongo.MongoClient()
        self.database = self.connection["default"]
        self.temp_dir = temp_dir
        if database:
            self.database = self.get_database(database)

        #These mappings are to handle conversions between functions.
        #This is used to specifiy which files are found in an 'archive'
        self.compressed_formats = {'esri shapefile': 'shp',
                                   'kmz': 'kml',
                                   'zipped_geojson': 'geojson',
                                   'zipped_geonames': 'txt',
                                   'zipped_csv': 'csv',
                                   'shp': 'shp'}
        #This is used to specify what the downloaded file extension should be.
        self.download_formats = {'json': 'json',
                                 'esri shapefile': 'zip',
                                 'shp': 'zip',
                                 'kmz': 'zip',
                                 'kml': 'kml',
                                 'zipped_geojson': 'zip',
                                 'zipped_csv': 'zip',
                                 'xls': 'xls',
                                 'xlsx': 'xlsx',
                                 'csv': 'csv',
                                 'tsv': 'tsv',
                                 'txt': 'txt',
                                 'zipped_geonames': 'zip'}
        #Tells geoserver what to expect NOT all of these are actually supported like TSV.
        self.geoserver_importer_formats = {'json': 'json',
                                           'esri shapefile': 'shapefile',
                                           'shp': 'zip',
                                           'kmz': 'zip',
                                           'kml': 'kml',
                                           'zipped_geojson': 'geojson',
                                           'zipped_csv': 'csv',
                                           'xls': 'xls',
                                           'xlsx': 'xlsx',
                                           'csv': 'csv',
                                           'tsv': 'tsv',
                                           'txt': 'txt',
                                           'zipped_geonames': 'zip'}
        #Used for OGR conversions
        self.ogr_formats = {'shp':'ESRI Shapefile','kml': 'kml'}
        #If using 'mongoimport' these will be used to tell the tool what the file will be.
        self.mongoimport_mapped_formats = {'json': 'json',
                                           'esri shapefile': 'json',
                                           'kmz': 'json',
                                           'zipped_geojson': 'json',
                                           'xls': 'csv',
                                           'xlsx': 'csv',
                                           'csv': 'csv',
                                           'tsv': 'tsv',
                                           'txt': 'tsv',
                                           'zipped_csv': 'csv',
                                           'zipped_geonames': 'tsv'}
        self.mongoimport_supported_formats = ['csv','tsv','json']
        if not self.database.country_codes.find_one():
            self.import_file(os.path.abspath('./country_codes.tsv'),'tsv',collection="country_codes")
        if csv_file:
            self.import_file(os.path.abspath(csv_file),'csv',collection="data_sources",data_key="import_name",compare="data_date")
        self.update_data()

    def __del__(self):
        self.connection.close()

    def connect(self):
        if self.connection.HOST == self.host and self.connection.PORT == self.port:
            return True
        else:
            self.connection = pymongo.MongoClient(self.host, self.port)
            try:
                self.connection.server_info()
                return True
            except pymongo.errors, message:
                self.connection = None
                print(message)
                print("Failed to Connect")
                return False

    def get_database(self, database):
        if not self.connect():
            return None
        if self.database.name == database:
            return self.database
        else:
            return self.connection[database]

    def import_file(self, file_paths, file_format, collection=None, data_key=None, compare=None, header=None):
        if type(file_paths) is not list:
            file_paths = [file_paths]

        if not collection:
            collection = os.path.splitext(os.path.basename(file_paths[0]))[0]

        ## This was optionally if wishing to use mongoimport as opposed to importing the files with a custom routine.
        # if 'win32' in sys.platform:
        #     bin_dir = r"C:\Program Files\MongoDB\Server\3.2\bin"
        # elif 'linux' in sys.platform:
        #     bin_dir = "/usr/bin"
        # else:
        #     print("Current operating system is not supported")
        #     return False

        # shapefiles are expected to be a zipped file
        if file_format.lower() in self.compressed_formats:
            new_file_paths = []
            for file_path in file_paths:
                new_file_paths += self.convert_compressed_format(file_path, file_format)
            file_paths = new_file_paths
        # excel files are converted to csv
        elif 'xls' in file_format.lower():
            new_file_paths = []
            for file_path in file_paths:
                new_file_paths += self.convert_from_excel(file_path)
            file_paths = new_file_paths

        import_file_format = self.mongoimport_mapped_formats.get(file_format.lower())

        for file_path in file_paths:
            doc_count = 0
            print "Importing " + file_path + " into " + collection + "..."
            if os.path.getsize(file_path) > 16000000:
                    print "The json is too large to import into MongoDB."
                    continue
            with open(file_path, 'r') as data_file:
                if import_file_format.lower() == 'json':
                    enc_det = detect_encoding(data_file)
                    if enc_det.get('encoding'):
                        print "Encoding detected: " + enc_det.get('encoding')
                        json_data = json.load(data_file, encoding=enc_det.get('encoding'))
                    else:
                        json_data = json.load(data_file)
                    if type(json_data) != 'list':
                        json_data = [json_data]
                    for json_obj in json_data:
                        self.submit_document(json_obj,collection, data_key=data_key,compare=compare)
                        doc_count += 1
                elif import_file_format.lower() in ['csv','tsv']:
                    try:
                        header = int(header)
                    except:
                        header = 0
                    if header != 0:
                        data_file.seek(0)
                        read_line_number(data_file,(header-1))
                    try:
                        header_data = data_file.readline()
                        dialect = csv.Sniffer().sniff(header_data, ['\t',',',';'])
                    except:
                        print "Unable to determine the proper delimeter."
                        print "Please check the file " + file_path + " and try again."
                        continue
                    csv_data = csv.reader([header_data], dialect)
                    header_row = next(csv_data)
                    print "Header detected as: " + str(header_row)
                    dict_reader = csv.DictReader(data_file,header_row)
                    for row in dict_reader:
                        if self.submit_document(row, collection, data_key=data_key):
                            doc_count += 1
            self.database.data_sources.update_one({'import_name':collection},{"$set":{"local_file_path":file_paths}})
            print("Imported " + str(doc_count) + " documents into " + collection + ".")

            ## This was optionally if wishing to use mongoimport as opposed
            ## to importing the files with a custom routine.
            # print file_path
            # execute = [os.path.join(bin_dir,"mongoimport"),
            #            "--host", self.host,
            #            "--port", str(self.port),
            #            "-d", self.database.name,
            #            "-c", collection,
            #            "--type", import_file_format,
            #            "--file", file_path]
            # if file_format.lower() != "json":
            #     execute.append("--headerline")
            # if data_key:
            #     execute += ["--upsertFields",data_key]
            # if os.path.isfile(os.path.join(bin_dir,"mongoimport")):
            #     subprocess.call(execute)
            # else:
            #     print("Mongo tools not found")

    #Document is actually a python dict
    def submit_document(self, document, collection, data_key=None, compare=None):
        collection = self.database[collection]
        if document.get(data_key):
            try:
                collection.update_one({data_key:document.get(data_key)},{"$set":document}, upsert=True)
            except Exception as e:
                if 'e11000' in e.message.lower():
                    return False
                else:
                    print e
                    print e.message
                return False
        else:
            try:
                collection.insert_one(document)
            except Exception as e:
                if 'e11000' in e.message.lower():
                    return False
                else:
                    print e
                    return False
        return True

    def upload_to_geoserver(self,
                            host='127.0.0.1',
                            port='8080',
                            workspace=None,
                            targetStore=None,
                            source=None,
                            username=None,
                            password=None):
        self.geoserver_user = username
        self.geoserver_user = username
        self.geoserver_password = password
        protocol = 'http'
        if '443' in str(port):
            protocol = 'https'
        payload = {
            "import": {
                "targetWorkspace": {
                    "workspace": {
                        "name": workspace
                    }
                },
                "targetStore": {
                    "dataStore": {
                        "name": targetStore
                    }
                },
                "data": {
                    "type": "file",
                    "file": source
                }
            }
        }
        collection = os.path.splitext(os.path.basename(source))[0]
        authentication = requests.auth.HTTPBasicAuth(self.geoserver_user,self.geoserver_password)
        url = '{}://{}:{}/geoserver/rest/imports'.format(protocol, host, port)
        exists_url = '{}://{}:{}/geoserver/rest/layers/{}.html'.format(protocol, host, port, collection)
        r = requests.get(exists_url, verify=False, auth=authentication)
        if r.status_code == 401:
            if self.geoserver_user is None or self.geoserver_password is None:
                self.geoserver_user = raw_input("Enter geoserver username:")
                self.geoserver_password = getpass.getpass("Enter geoserver password:")
                authentication = requests.auth.HTTPBasicAuth(self.geoserver_user,self.geoserver_password)
        if r.status_code == 200:
            print "The " + source + " service already exists."
        r = requests.post(url, json=payload, verify=False, auth=authentication)
        if r.status_code == 401:
            if self.geoserver_user is None or self.geoserver_password is None:
                self.geoserver_user = raw_input("Enter geoserver username:")
                self.geoserver_password = getpass.getpass("Enter geoserver password:")
                authentication = requests.auth.HTTPBasicAuth(self.geoserver_user,self.geoserver_password)
            r = requests.post(url, json=payload, verify=False, auth=authentication)
        if "Target store does not exist" in r.text:
            print "The target store does not exist"
            ds_url = '{}://{}:{}/geoserver/rest/workspaces/sde/datastores'.format(protocol, host, port)
            ds_payload = {
                "dataStore" : {
                    "name" : "imports",
                    "type" : "PostGIS",
                    "enabled" : True,
                    "workspace" : {
                        "name" : "sde",
                        "href" : "{}:\/\/{}:{}\/geoserver\/rest\/workspaces\/sde.json".format(protocol,host,port)
                    },
                    "connectionParameters" : {
                        "entry" : [{
                                "@key" : "schema",
                                "$" : "public"
                            }, {
                                "@key" : "Evictor run periodicity",
                                "$" : "300"
                            }, {
                                "@key" : "Max open prepared statements",
                                "$" : "50"
                            }, {
                                "@key" : "encode functions",
                                "$" : "false"
                            }, {
                                "@key" : "preparedStatements",
                                "$" : "false"
                            }, {
                                "@key" : "database",
                                "$" : "imports"
                            }, {
                                "@key" : "host",
                                "$" : "localhost"
                            }, {
                                "@key" : "Loose bbox",
                                "$" : "true"
                            }, {
                                "@key" : "Estimated extends",
                                "$" : "true"
                            }, {
                                "@key" : "fetch size",
                                "$" : "1000"
                            }, {
                                "@key" : "Expose primary keys",
                                "$" : "false"
                            }, {
                                "@key" : "validate connections",
                                "$" : "true"
                            }, {
                                "@key" : "Support on the fly geometry simplification",
                                "$" : "true"
                            }, {
                                "@key" : "Connection timeout",
                                "$" : "20"
                            }, {
                                "@key" : "create database",
                                "$" : "false"
                            }, {
                                "@key" : "port",
                                "$" : "5432"
                            }, {
                                "@key" : "passwd",
                                "$" : "importer"
                            }, {
                                "@key" : "min connections",
                                "$" : "1"
                            }, {
                                "@key" : "dbtype",
                                "$" : "postgis"
                            }, {
                                "@key" : "namespace",
                                "$" : "http:\/\/geoserver.sf.net"
                            }, {
                                "@key" : "max connections",
                                "$" : "10"
                            }, {
                                "@key" : "Evictor tests per run",
                                "$" : "3"
                            }, {
                                "@key" : "Test while idle",
                                "$" : "true"
                            }, {
                                "@key" : "user",
                                "$" : "importer"
                            }, {
                                "@key" : "Max connection idle time",
                                "$" : "300"
                            }
                        ]
                    },
                    "_default" : False,
                    "featureTypes" : "{}:\/\/{}:{}\/geoserver\/rest\/workspaces\/sde\/datastores\/imports\/featuretypes.json".format(protocol,host,port)
                }
            }
            ds_r = requests.post(ds_url, json=ds_payload, verify=False, auth=authentication)
            if ds_r.status_code == 201:
                print "A datastore was successfully created."
                r = requests.post(url, json=payload, verify=False, auth=authentication)
            else:
                return False
        import_task = r.json().get('import')
        tasks = import_task.get('tasks')
        if tasks:
            requests.post(import_task.get('href'), verify=False, auth=authentication)
            t_r = requests.get(import_task.get('href'), verify=False, auth=authentication).json()
            for task in t_r.get('import').get('tasks'):
                if task.get('state')== "NO_CRS":
                    requests.put(import_task.get('href'),
                                 json = {'layer':{'srs':'EPSG:4326'}},
                                 verify=False,
                                 auth=authentication)
                elif task.get('state')== "RUNNING":
                    print "The " + source + " import task is currently running."
                elif task.get('state')== "COMPLETED":
                    print "The " + source + " task completed."
                elif task.get('state')== "PENDING":
                    print "The " + source + " task completed."
                    print "The return value was: " + str(task)
        else:
            print "The file: " + source + " was not a valid source."

    def get_source_data(self, url, local_filename="downloaded_file"):
        if not url:
            print "A data_url must exist to download and import the data."
        print "Downloading " + local_filename + " from " + url
        r = requests.get(url, stream=True)
        if int(r.status_code) >= 400:
            print str(url) + " returned " + str(int(r.status_code)) + " and is invalid."
            return None
        data_path = os.path.join(self.temp_dir,local_filename)
        if not os.path.isdir(data_path):
            os.mkdir(data_path)
        with open(os.path.join(data_path,local_filename), 'wb') as f:
            total_size = r.headers.get('content-length')
            if total_size:
                total_size = float(total_size)
            written_content = 0
            chunk_size=4096
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    written_content += chunk_size
                    print_status(written_content, total_size)
        print("\nFinished downloading " + local_filename + ".")
        return os.path.abspath(os.path.join(data_path,local_filename))

    ##When implementing this the user should only have permissions to a limited set
    ##set of directories to prevent absolute file paths from being extracted. (i.e./etc/hosts)
    def extract_data(self, zip_file):
        zips = ['.zip','.gz','.kmz']
        for ext in zips:
            if ext in os.path.splitext(os.path.basename(zip_file))[1]:
                zip_folder = working_folder(zip_file)
                with ZipFile(zip_file,'r') as zip:
                    zip.extractall(zip_folder)
                return zip_folder

    def convert_compressed_format(self, file_path, format):
        extracted_path = self.extract_data(file_path)
        files = self.get_files_by_type(extracted_path,self.compressed_formats.get(format))
        file_paths = []
        for file_name in files:
            if self.compressed_formats.get(format) in self.ogr_formats:
                file_paths += [os.path.join(self.convert_to_json(os.path.join(file_name), self.ogr_formats.get(self.compressed_formats.get(format))))]
            else:
                file_paths += [file_name]
        return file_paths

    def convert_from_excel(self, file_path):
        csv_folder = working_folder(file_path)
        book = xlrd.open_workbook(file_path)
        sheet_names = book.sheet_names()
        file_paths = []
        for sheet_name in sheet_names:
            csv_path = os.path.join(csv_folder,sheet_name)+'.csv'
            with open(csv_path, 'w') as csv_file:
                csv_writer = unicodecsv.writer(csv_file, quoting=unicodecsv.QUOTE_ALL)
                sheet = book.sheet_by_name(sheet_name)
                for row_num in range(sheet.nrows):
                    csv_writer.writerow(sheet.row_values(row_num))
            file_paths += [csv_path]
        return file_paths

    def update_data(self):
        for source in self.database.data_sources.find():
            now = int('{:%Y%m%d%H%M%S}'.format(datetime.datetime.now()))
            collection_name = source.get('import_name')
            if now < long(self.get_expiration(source.get('data_date'),source.get('refresh_rate'))):
                continue
            local_filename = collection_name + '.' + self.download_formats.get(source.get('data_format').lower())
            collection = self.database[collection_name]
            downloaded_file = None
            if not collection.find_one():
                downloaded_file = self.get_source_data(source.get('data_url').lower(),local_filename=local_filename)
            if downloaded_file:
                self.import_file(downloaded_file,source.get('data_format'),collection=collection_name,header=source.get('header'))
            source['data_date'] = now
            source['local_file_paths'] = downloaded_file
            self.submit_document(source, 'data_sources', data_key='import_name')

    def get_expiration(self, date, mag):
        """
        :param date: The date to calculate the expiration from.
        :param mag: The order of magnitude for expiration (0=sec,1=min,...).
        :return: An integer representing the expiration.
        """
        if not mag:
            mag = 7
        if not date:
            date = 0
        return long(long(date)+math.pow(100,float(mag)))

    def convert_to_json(self, file_path, format):
        driver = ogr.GetDriverByName(format)
        json_path = file_path + ".json"
        with open(json_path, 'w') as json_file:
            driver_source = driver.Open(file_path)
            features_dict = {"type": "FeatureCollection",
                             "features": []
                             }
            for layer in driver_source:
                for feature in layer:
                    features_dict["features"].append(json.loads(feature.ExportToJson()))
            json.dump(features_dict, json_file)
        return json_path

    def get_files_by_type(self, directory, type):
        files = []
        for file_name in os.listdir(directory):
            if file_name.endswith(type):
                files += [os.path.join(directory,file_name)]
        return files


def read_line_number(input_file, line):
    i = 0
    input_file.seek(0)
    while i < line:
        input_file.readline()
        i += 1
    return input_file.readline()


def working_folder(file_path):
    folder = os.path.join(os.path.dirname(file_path),os.path.splitext(os.path.basename(file_path))[0])
    if not os.path.isdir(folder):
        os.mkdir(folder)
    return folder


def print_status(size, total_size):
    if not total_size:
        sys.stdout.write('\r')
        sys.stdout.write("Unknown Size: {} downloaded".format(size))
        sys.stdout.flush()
        return
    status = (size/total_size)*100
    percent = int(status)
    if percent > 100:
        percent = 100
    if size > total_size:
        size = total_size
    sys.stdout.write('\r')
    sys.stdout.write("[%-50s] %d%%, %d of %d" % ('='*int(percent/2), percent,size, total_size))
    sys.stdout.flush()

#note that this resets the file cursor
def detect_encoding(open_file):
    detector = UniversalDetector()
    for line in open_file.readlines():
        detector.feed(line)
        if detector.done: break
    detector.close()
    open_file.seek(0)
    return detector.result


def main():
    print "database doesn't have a main method."


if __name__ == "__main__":
    main()


# Copyright 2015, RadiantBlue Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.