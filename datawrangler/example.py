#!/usr/bin/python
import database

def main():

    ##run once using a CSV
    db = database.DB(host='localhost',port=27017, database='geodata', csv_file='./Sources.csv')

    ##subsequent runs without a CSV will use the data that exists.
    # db = database.DB(host='localhost',port=27017, database='geodata')

    sources = db.database.data_sources.find()
    for source in sources:
        file_names = source.get('local_file_path')
        if file_names:
            for file_name in file_names:
                print "Uploading the file: " + file_name
                db.upload_to_geoserver(host='192.168.20.20',
                                       port=8080,
                                       workspace='sde',
                                       targetStore='imports',
                                       source=file_name,
                                       username='admin',
                                       password='geoserver')

if __name__ == "__main__":
    main()

## example code for using pymongo to read collections.
import pymongo
client = pymongo.MongoClient('localhost',27017)
db = client.geodata
sources = db.data_sources.find()
print sources[0]
