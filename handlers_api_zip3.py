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
import json

# GAE imports
import webapp2

# local imports
import models_zip3 as models


###########################################################################
# Published police stations
###########################################################################
class ApiZip3Handler(webapp2.RequestHandler):

    def get(self):

        county_list = []

        zipMgr = models.Zip3Manager.getInstance()
        for county_key in zipMgr.county_key_list:
            county_entity = county_key.get()
            county_dict = dict()
            county_dict['county'] = county_key.id().decode('utf8')
            township_list = []
            for township_entity in county_entity.township_list:
                township_dict = dict()
                township_dict['township'] = township_entity.name
                township_dict['zip'] = township_entity.zip_string
                township_list.append(township_dict)
            county_dict['townships'] = township_list
            county_list.append(county_dict)

        self.response.body = json.dumps(county_list, indent=None, separators=(',', ':'))


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/api/opendata/zip3', handler=ApiZip3Handler),
]
