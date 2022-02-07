#!/usr/bin/env python
#
# api_gen.py - generates scitags API json from Google Sheet
#
# Author: Marian Babik
# Copyright CERN 2022
#

import csv
import json
import os.path
import sys
import collections
import datetime

import requests

GOOGLE_SHEET_CSV='https://docs.google.com/spreadsheets/d/e/2PACX-1vSKhv6z0Vo12Ty8p_xehteu290PIxClVlwRTDgCG1B4U5y25A5msNT38MO8sT9cTW1CkPdTck5gK55a/pub?gid=1072770680&single=true&output=csv'
GOOGLE_SHEET_HEADERS = 3
SCITAGS_API = 'http://api.scitags.org/'
API_VERSION = 1
API_FILE = 'api_n.json'

if __name__ == '__main__':
    print("Running in {}".format(os.getcwd()))
    print("Fetching CSV ...")
    csv_req = requests.get(GOOGLE_SHEET_CSV)
    if csv_req.status_code != 200 or not csv_req.text:
        print('Failed to get/read Google Sheet CSV file')
        sys.exit(-1)
    csv_text = csv_req.text

    #api_req = requests.get(SCITAGS_API)
    #if api_req.status_code != 200 or not api_req.text:
    #    print('Failed to get/read scitags API json')
    #    sys.exit(-1)
    # api_prev = json.loads(api_req.text)
    if os.path.exists(API_FILE):
        with open(API_FILE, 'r') as api_f:
            api_prev = json.load(api_f)
    else:
        print("Failed to find local API file, initial build")
        api_prev = dict()
        api_prev['experiments'] = list()

    api_new = dict()
    with open('scitags.csv', 'w') as csv_file:
        csv_file.write(csv_text)

    sciences = dict()
    activities = collections.defaultdict(list)
    with open('scitags.csv', 'r') as csv_file:
        reader = csv.reader(csv_file)
        for count, row in enumerate(reader):
            if count < GOOGLE_SHEET_HEADERS:
                continue
            if row[1] and row[2]:
                sciences[row[1].lower()] = int(row[2])
            if row[7] and row[8] and row[9]:
                activities[row[7].lower()].append([row[8].strip().lower(), int(row[9])])
    print("Loaded: {} sciences".format(len(sciences)))
    print("Loaded: {} activities".format(sum([len(a) for a in activities.keys()])))

    api_new['experiments'] = list()
    for k, v in sciences.items():
        entry = dict()
        entry['expName'] = k
        entry['expId'] = v
        entry['activities'] = list()
        if k in activities.keys():
            for item in activities[k]:
                ac_entry = dict()
                ac_entry['activityName'] = item[0]
                ac_entry['activityId'] = item[1]
                entry['activities'].append(ac_entry)
        api_new['experiments'].append(entry)

    api_diff = False
    if not api_prev['experiments']:
        api_diff = True
    pairs = zip(api_new['experiments'], api_prev['experiments'])
    for x, y in pairs:
        if x != y:
            print('Diff #:', x, y)
            api_diff = True
            break
        ac_pairs = zip(x['activities'], y['activities'])
        for ax, ay in ac_pairs:
            if ax != ay:
                print('Diff #:', ax, ay)
                api_diff = True
                break

    if not api_diff:
        print('No changes detected, exiting')
        sys.exit(0)
    else:
        api_new['version'] = API_VERSION
        api_new['modified'] = "{}+00:00".format(datetime.datetime.utcnow().isoformat())
        with open(API_FILE, 'w') as api_f:
            api_f.write(json.dumps(api_new, indent=4))
        print('Changes saved')
