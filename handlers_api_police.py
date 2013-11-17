#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013, YH Yang <yhuiyang@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# python imports
import logging
import json
from datetime import date

# GAE imports
import webapp2

# local imports
import models_police as models


###########################################################################
# Published police stations
###########################################################################
class ApiPublishedPoliceStations(webapp2.RequestHandler):

    def get(self):

        INVALID_DATE = date(1970, 1, 1)
        INVALID_REV = 0

        self.response.content_type = 'application/json'

        # init output data
        output = dict()

        mgr = models.PoliceStationManager.getInstance()
        if len(mgr.meta_list) == 0:
            output['date'] = INVALID_DATE.isoformat()
            output['rev'] = INVALID_REV
            output['data'] = []
            self.response.body = json.dumps(output, indent=None, separators=(',', ':'))
            return

        # check what is latest date and rev
        latest_date, latest_rev = mgr.getLatestDateAndRevision(INVALID_DATE, INVALID_REV)
        output['date'] = latest_date.isoformat()
        output['rev'] = latest_rev

        # check client date and rev
        client_date_str = self.request.get('d', default_value=INVALID_DATE.isoformat())
        client_rev_str = self.request.get('r', default_value=str(INVALID_REV))
        client_query_str = self.request.get('q', default_value=0)  # 0: query all; not 0: query date/rev only
        try:
            cy, cm, cd = client_date_str.split('-')
            client_date = date(int(cy), int(cm), int(cd))
            client_rev = int(client_rev_str)
        except ValueError:
            client_date = INVALID_DATE
            client_rev = INVALID_REV

        fill_data = False
        if latest_date > client_date:
            fill_data = True
        elif latest_date == client_date and latest_rev > client_rev:
            fill_data = True
        if fill_data and int(client_query_str) == 0:
            strId = latest_date.isoformat() + 'r' + str(latest_rev)
            output['data'] = models.PublishedPoliceStations.get_by_id(strId).list
        else:
            output['data'] = []

        self.response.body = json.dumps(output, indent=None, separators=(',', ':'))


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/api/opendata/police_stations', handler=ApiPublishedPoliceStations),
]
