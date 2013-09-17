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
from datetime import date, datetime

# GAE imports
import webapp2
from webapp2_extras.routes import RedirectRoute
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.blobstore import BlobInfo
from google.appengine.api import background_thread
from google.appengine.ext import ndb

# local imports
from handlers_admin_base import BaseHandler
import models_opendata as models


###########################################################################
# Open data
###########################################################################
class ODGetUploadUrl(webapp2.RequestHandler):

    def get(self):

        # the url to post to blobstore is dynamically generated by GAE,
        # when blob upload completed, GAE will invoke our callback handler
        # registered on the success_path
        success_path = self.uri_for('opendata-collection')
        upload_url = [blobstore.create_upload_url(success_path)]

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(upload_url)


class ODCollectionHandler(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    def get(self):

        ps_list = []
        qry = models.PoliceStationRawData.query()
        for q in qry:
            ps = dict()
            blob_info = BlobInfo(q.blob_key)
            ps['filename'] = blob_info.filename
            ps['filesize'] = blob_info.size
            ps['uploadDatetime'] = blob_info.creation
            ps['datadate'] = q.date
            ps['parse_state'] = q.get_state()
            ps['keySafe'] = q.key.urlsafe()
            ps_list.append(ps)

        params = {
            'app_name': 'Open Data Collection',
            'police_stations': ps_list,
        }
        self.render_response('opendata_collection.html', **params)

    def post(self):

        type = self.request.get('type')
        if type == 'police_stations':
            upload_files = self.get_uploads('data-file')
            data_date = self.request.get('data-date')
            if len(upload_files) == 1 and data_date:
                blob_info = upload_files[0]
                blob_key = blob_info.key()
                logging.debug(blob_info)

                raw_data = models.PoliceStationRawData()
                raw_data.blob_key = blob_key
                y, m, d = data_date.split('-')
                raw_data.date = date(int(y), int(m), int(d))

                raw_data.put()

        self.redirect_to('opendata-collection')

    def put(self):

        self.response.status_int = 200

        type = self.request.get('type')
        if type == 'police_stations':
            keySafe = self.request.get('keySafe')
            action = self.request.get('action')
            if action == 'populate':
                background_thread.start_new_background_thread(
                    self.parse_police_stations_raw_data_and_populate_into_datastore, [keySafe])
            elif action == 'clean':
                background_thread.start_new_background_thread(self.clean_up_police_stations_in_datastore, [keySafe])
            else:
                self.response.status_int = 400
        else:
            self.response.status_int = 400

    def parse_police_stations_raw_data_and_populate_into_datastore(self, keySafe):
        if keySafe:
            raw_data = ndb.Key(urlsafe=keySafe).get()
            if raw_data:
                if raw_data.get_state() == models.STATE_UNPARSED:

                    start_time = datetime.now()
                    add_count = 0

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
                        add_count += 1

                    raw_data.set_state(models.STATE_PARSED)
                    raw_data.put()

                    end_time = datetime.now()
                    delta = end_time - start_time
                    logging.info('Create %d police station entities spend: %s sec' % (add_count, delta.total_seconds()))
                else:
                    logging.warning('Raw data is processing or was parsed, skip action now!')
            else:
                logging.warning('Can not find police stations raw data by this key!')
        else:
            logging.warning('No raw data key provided!')

    def clean_up_police_stations_in_datastore(self, keySafe):

        if keySafe:
            raw_data = ndb.Key(urlsafe=keySafe).get()
            if raw_data:
                if raw_data.get_state() == models.STATE_PARSED:
                    start_time = datetime.now()
                    delete_count = 0
                    has_more = True
                    next_cursor = None

                    raw_data.set_state(models.STATE_PROCESSING)
                    raw_data.put()

                    qry = models.PoliceStation.query()
                    while has_more:
                        result_page, next_cursor, has_more = qry.fetch_page(100, start_cursor=next_cursor)
                        for ps in result_page:
                            ps.key.delete()
                            delete_count += 1

                    raw_data.set_state(models.STATE_UNPARSED)
                    raw_data.put()

                    end_time = datetime.now()
                    delta = end_time - start_time
                    logging.info('Delete %d police station entities spend: %s sec' %
                                 (delete_count, delta.total_seconds()))
                else:
                    logging.warning('Raw data is unparsed or in process, skip action now!')
            else:
                logging.warning('Can not find police stations raw data by this key!')
        else:
            logging.warning('No raw data key provided!')


class ODPoliceStationsHandler(BaseHandler):

    PAGE_SIZE = 10

    def get(self):

        websafe = self.request.get('c', default_value=None)
        forward = True if self.request.get('f', default_value='1') == '1' else False
        logging.debug('c=%s, f=%s' % (websafe, forward))

        qry = models.PoliceStation.query()
        cursor = ndb.Cursor.from_websafe_string(websafe) if websafe else None
        logging.debug(cursor)
        pager = [dict(), dict()]
        if forward:
            result_page, next_cursor, more = qry.fetch_page(self.PAGE_SIZE, start_cursor=cursor)
            pager[0]['disabled'] = not websafe
            pager[0]['link'] = '?c=' + websafe + '&f=0' if websafe else '#'
            pager[1]['disabled'] = not more
            pager[1]['link'] = '?c=' + ndb.Cursor.to_websafe_string(next_cursor) + '&f=1' if more else '#'
        else:
            result_page, next_cursor, more = qry.fetch_page(self.PAGE_SIZE, end_cursor=cursor)
            pager[0]['disabled'] = not more
            pager[0]['link'] = '#' if not more else '?c=' + ndb.Cursor.to_websafe_string(next_cursor) + '&f=0'
            pager[1]['disabled'] = False
            pager[1]['link'] = '?c=' + websafe + '&f=1'

        params = {
            'app_name': 'Open Data - Police Stations',
            'police_stations': result_page,
            'p': pager,
        }
        self.render_response('opendata_police_stations.html', **params)


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/opendata/get_upload_url', ODGetUploadUrl),
    RedirectRoute(r'/opendata/police_stations', handler=ODPoliceStationsHandler, name='opendata-police-stations',
                  strict_slash=True),
    RedirectRoute(r'/opendata', handler=ODCollectionHandler, name='opendata-collection', strict_slash=True),
]
