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
import models_opendata as models


###########################################################################
# Published police stations
###########################################################################
class ApiPublishedPoliceStations(webapp2.RequestHandler):

    def get(self):

        self.response.content_type = 'application/json'

        # fill dummy info
        output = dict()
        output['date'] = '1970-01-01'
        output['data'] = []

        mgr = models.PoliceStationManager.getInstance()
        if len(mgr.published_data_date) == 0:
            self.response.body = json.dumps(output, indent=None, separators=(',', ':'))
            return

        client_data_date_str = self.request.get('d')
        latest_data_date = mgr.published_data_date[0]
        if not client_data_date_str:
            output['date'] = latest_data_date.isoformat()
            output['data'] = models.PublishedPoliceStations.get_by_id(latest_data_date.isoformat()).list
        else:
            try:
                cy, cm, cd = client_data_date_str.split('-')
                client_data_date = date(int(cy), int(cm), int(cd))
                if latest_data_date > client_data_date:
                    output['data'] = models.PublishedPoliceStations.get_by_id(latest_data_date.isoformat()).list
                output['date'] = latest_data_date.isoformat()
            except ValueError:
                pass

        self.response.body = json.dumps(output, indent=None, separators=(',', ':'))


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/api/opendata/police_stations', handler=ApiPublishedPoliceStations),
]
