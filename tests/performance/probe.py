"""Finite-timeout outage probe; executed only inside the disposable API container."""
import argparse
import json
import time
import urllib.error
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--path',default='/api/health')
args=parser.parse_args()
start=time.perf_counter()
try:
    response=urllib.request.urlopen('http://127.0.0.1:8000'+args.path,timeout=6)
    status=response.status
except urllib.error.HTTPError as error:
    status=error.code
except Exception as error:
    status=type(error).__name__
print(json.dumps({'path':args.path,'status':status,'elapsed_s':round(time.perf_counter()-start,3)}))
