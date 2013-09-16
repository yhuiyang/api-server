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
from datetime import datetime

# GAE imports
import webapp2
from google.appengine.api import background_thread
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from webapp2_extras.routes import RedirectRoute

# local imports
import opendata_models as models


###########################################################################
# Open data
###########################################################################
class ProcessHandler(webapp2.RequestHandler):

    def put(self):

        self.response.status_int = 200

        type = self.request.get('type')
        logging.debug('type: ' + type)
        if type == 'police_stations':
            keySafe = self.request.get('keySafe')
            action = self.request.get('action')
            logging.debug('action: ' + action)
            if action == 'populate':
                background_thread.start_new_background_thread(
                    parse_police_stations_raw_data_and_populate_into_datastore, [keySafe])
            elif action == 'clean':
                background_thread.start_new_background_thread(clean_up_police_stations_in_datastore)
            else:
                self.response.status_int = 400
        else:
            self.response.status_int = 400


def parse_police_stations_raw_data_and_populate_into_datastore(keySafe):

    if keySafe:
        raw_data = ndb.Key(urlsafe=keySafe).get()
        if raw_data:
            if raw_data.get_state() == models.STATE_UNPARSED:

                start_time = datetime.now()

                raw_data.set_state(models.STATE_PROCESSING)
                raw_data.put()

                reader = blobstore.BlobReader(raw_data.blob_key)
                for line in reader:
                    split = line.split(',')
                    station = models.PoliceStation()
                    station.name = split[0]
                    station.tel = split[1]
                    station.address = split[2]
                    station.xy = [float(split[3]), float(split[4])]
                    station.latlng = ndb.GeoPt(lat=float(split[5]), lon=float(split[6]))
                    station.put()

                raw_data.set_state(models.STATE_PARSED)
                raw_data.put()

                end_time = datetime.now()
                delta = end_time - start_time
                logging.debug('Total spend time: %s sec' % delta.total_seconds())
            else:
                logging.warning('Raw data is processing or was parsed, skip action now!')
        else:
            logging.warning('Can not find police stations raw data by this key!')
    else:
        logging.warning('No raw data key provided!')


def clean_up_police_stations_in_datastore():

    logging.debug('Clean up police stations')


###########################################################################
# Routes
###########################################################################
routes = [
    RedirectRoute(r'/opendata', handler=ProcessHandler, name='process-opendata', strict_slash=True),
]
