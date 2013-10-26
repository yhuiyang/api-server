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

# GAE imports
from webapp2_extras.routes import RedirectRoute
from google.appengine.api import urlfetch

# local imports
from handlers_admin_base import BaseHandler
import models_zip3 as models


class Zip3Handler(BaseHandler):

    def get(self):

        zipMgr = models.Zip3Manager.getInstance()
        county_entity_list = []
        for county_key in zipMgr.county_key_list:
            county_entity_list.append(county_key.get())

        params = {
            'app_name': 'Open data - Taiwan Township Zip Code',
            'url': zipMgr.url,
            'counties': county_entity_list,
        }
        self.render_response('od_zip3.html', **params)

    def post(self):

        url = self.request.get('url')
        if url:
            response = urlfetch.fetch(url)
            if response.status_code == 200:

                zipMgr = models.Zip3Manager.getInstance()
                zipMgr.url = url
                zipMgr.county_key_list = []

                processed_county = []

                csv_big5 = response.content
                csv_utf8 = csv_big5.decode('big5')
                line_list = csv_utf8.splitlines()
                for line in line_list:
                    columns = line.rstrip().split(',')
                    zipcode = columns[0]
                    county_township = columns[1]

                    head, sep, tail = county_township.partition(u'縣')
                    if sep and tail:
                        county = head + sep
                        township = tail
                    else:
                        head, sep, tail = county_township.partition(u'市')
                        if sep and tail:
                            county = head + sep
                            township = tail
                        else:
                            logging.warning('Skip saving %s' % county_township)
                            continue

                    if county not in processed_county:
                        processed_county.append(county)
                        CountyEntity = models.County.getInstance(county)
                        CountyEntity.township_list = []
                        zipMgr.county_key_list.append(CountyEntity.key)
                    else:
                        CountyEntity = models.County.getInstance(county)
                    CountyEntity.township_list.append(models.Township(name=township, zip_string=zipcode))
                    CountyEntity.put()
                zipMgr.put()

        self.redirect_to('zip3')


###########################################################################
# Routes
###########################################################################
routes = [
    RedirectRoute(r'/opendata/zip3', handler=Zip3Handler, name='zip3', strict_slash=True),
]
