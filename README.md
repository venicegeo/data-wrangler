# data-wrangler


A vagrant configuration implementing GeoServer, MongoDB, and GeoServer, used to ingest a CSV file of sources and display compatible files in GeoServer.


## Requirements

Vagrant needs to be installed on the host machine.

## Setup

Inside of the data wrangler folder there is a list of sources, when vagrant is initialized ("vagrant up") it will pull the image, download all of the software, then execute the example script. 

The example script will call the database.py file and add all fields in the CSV to Mongo (updating existing Data_URLs), and update all existing Mongo collections (none on first run).

The CSV file should be updated if needed prior to first run. 

### Field Names
#### Required
* import_name - What the file will be saved as, and what the collection will be in MongoDB.  This and the Data_URL should be unique. 
* data_url - The exact URL to pull a file from, this won't handle redirects nor currently supports header information or authentication (other than basic authentication through the URL). 
* header - The script doesn't try to 'sniff' the header so if it is NOT on the first row it needs to be defined.  ('0' is the first row).
* data_format - The script will currently work with the examples in the Sources.csv (note not ALL of the sources will import into GeoServer only files compatible with the GeoServer Importer extension.
#### Optional
* url - A root Url where the data owner lives.
* data_key - Used as an "Index" for uploading data.
* data_date - This gets updated when the file downloads or can be provided here as a long integer (yyyymmddHHMMSS) where 2:34:26 PM JAN 24, 2016 would be 20160124023426. 
* refresh_rate - An order of magnitude (0 seconds, 1 Minutes etc.) when subsequent calls to the database.Update_date() function should download new data.  (This needs some work with PostGIS compat.)
* anything else added will simply be a new field in mongo, or column in postgis.

## Initialize

Change directory to the location of the vagrant file. 

```
vagrant up

```