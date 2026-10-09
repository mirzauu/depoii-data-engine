import urllib.request
import json
import urllib.parse
import sqlite3

def test_query():
    where_clause = "Address LIKE '%DWIGHT%' AND ZipCode = 11231"
    params = {
        'where': where_clause,
        'outFields': 'Borough,Block,Lot,Address,ZipCode,BldgArea,OwnerName,YearBuilt,AssessTot',
        'resultRecordCount': 5,
        'f': 'json'
    }
    url = 'https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode())
        print('Matches found on Dwight St:', len(data.get('features', [])))
        for f in data.get('features', []):
            print(f['attributes'])

if __name__ == '__main__':
    test_query()
