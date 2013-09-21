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
from google.appengine.api import runtime
from google.appengine.ext import ndb

# local imports
from handlers_admin_base import BaseHandler
import models_opendata as models


###########################################################################
# Check runtime resource usage
###########################################################################
def check_runtime_usage():
    cpu = runtime.cpu_usage()
    logging.debug('[CPU] Total: %f, Avg 1m: %f, Avg 10m: %f' % (cpu.total(), cpu.rate1m(), cpu.rate10m()))
    mem = runtime.memory_usage()
    logging.debug('[MEM] Current: %f, Avg 1m: %f, Avg 10m: %f' % (mem.current(), mem.average1m(), mem.average10m()))


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
            ps['published'] = q.published
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
                self.response.status_int = self.parse_police_stations_raw_data_and_populate_into_datastore(keySafe)
            elif action == 'clean':
                self.response.status_int = self.clean_up_police_stations_in_datastore(keySafe)
            else:
                self.response.status_int = 400
        else:
            self.response.status_int = 400

    def parse_police_stations_raw_data_and_populate_into_datastore(self, keySafe):

        status_int = 200

        if keySafe:
            raw_data = ndb.Key(urlsafe=keySafe).get()
            if raw_data:
                if raw_data.get_state() == models.PoliceStationRawData.STATE_UNPARSED:

                    start_time = datetime.now()

                    raw_data.set_state(models.PoliceStationRawData.STATE_PROCESSING)
                    raw_data.put()

                    reader = blobstore.BlobReader(raw_data.blob_key)

                    @ndb.transactional
                    def populate(reader):
                        loop_count = 0
                        dummyGroupKey = ndb.Key(models.PoliceStation, raw_data.date.isoformat())
                        for line in reader:
                            if runtime.is_shutting_down():
                                return False, 0
                            split = line.split(',')
                            station = models.PoliceStation(parent=dummyGroupKey)
                            station.name = split[0]
                            station.tel = split[1]
                            station.address = split[2]
                            station.xy = [float(split[3]), float(split[4])]
                            station.latlng = ndb.GeoPt(lat=float(split[5]), lon=float(split[6]))
                            station.put()
                            loop_count += 1
                        return True, loop_count

                    result, add_count = populate(reader)
                    if not result:
                        logging.warning('Shutting down early!')
                        status_int = 503  # service unavailable
                        check_runtime_usage()

                    reader.close()

                    if status_int == 200:
                        raw_data.set_state(models.PoliceStationRawData.STATE_PARSED)
                    else:
                        raw_data.set_state(models.PoliceStationRawData.STATE_UNPARSED)
                    raw_data.put()

                    end_time = datetime.now()
                    delta = end_time - start_time
                    logging.info('Create %d police station entities spend: %s sec' % (add_count, delta.total_seconds()))
                else:
                    logging.warning('Raw data is processing or was parsed, skip action now!')
                    status_int = 409  # conflict
            else:
                logging.warning('Can not find police stations raw data by this key!')
                status_int = 410  # gone
        else:
            logging.warning('No raw data key provided!')
            status_int = 400  # bad request
        return status_int

    def clean_up_police_stations_in_datastore(self, keySafe):

        status_int = 200

        if keySafe:
            raw_data = ndb.Key(urlsafe=keySafe).get()
            if raw_data:
                if raw_data.get_state() == models.PoliceStationRawData.STATE_PARSED:

                    start_time = datetime.now()

                    raw_data.set_state(models.PoliceStationRawData.STATE_PROCESSING)
                    raw_data.put()

                    @ndb.transactional
                    def cleanup():
                        has_more = True
                        next_cursor = None
                        loop_count = 0
                        qry = models.PoliceStation.query_entities(raw_data.date.isoformat())
                        while has_more:
                            result_page, next_cursor, has_more = qry.fetch_page(100, start_cursor=next_cursor)
                            for ps in result_page:
                                if runtime.is_shutting_down():
                                    return False, 0
                                ps.key.delete()
                                loop_count += 1
                        return True, loop_count

                    result, delete_count = cleanup()
                    if not result:
                        logging.warning('Shutting down early!')
                        status_int = 503  # service unavailable
                        check_runtime_usage()

                    if status_int == 200:
                        raw_data.set_state(models.PoliceStationRawData.STATE_UNPARSED)
                    else:
                        raw_data.set_state(models.PoliceStationRawData.STATE_PARSED)
                    raw_data.put()

                    end_time = datetime.now()
                    delta = end_time - start_time
                    logging.info('Delete %d police station entities spend: %s sec' %
                                 (delete_count, delta.total_seconds()))
                else:
                    logging.warning('Raw data is unparsed or in process, skip action now!')
                    status_int = 409  # conflict
            else:
                logging.warning('Can not find police stations raw data by this key!')
                status_int = 410  # gone
        else:
            logging.warning('No raw data key provided!')
            status_int = 400  # bad request
        return status_int


class ODPoliceStationsHandler(BaseHandler):

    PAGE_SIZE = 10

    def get(self):

        websafe = self.request.get('c', default_value=None)
        forward = True if self.request.get('f', default_value='1') == '1' else False
        logging.debug('c=%s, f=%s' % (websafe, forward))

        data_date = self.request.get('d', default_value=None)
        if not data_date:
            data_date = date.today().isoformat()
        qry = models.PoliceStation.query_entities(data_date)
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

    def put(self):

        keysafe = self.request.get('keySafe')
        action = self.request.get('action')
        if action == 'publish':
            self.response.status_int = self.publish_police_stations(keysafe)
        elif action == 'unpublish':
            self.unpublish_police_stations(keysafe)
        else:
            self.response.status_int = self.response.status_int = 400  # bad request

    def publish_police_stations(self, keysafe):

        status_int = 200

        raw_data = ndb.Key(urlsafe=keysafe).get()
        if raw_data:
            mgr = models.PoliceStationManager.getInstance()
            if not raw_data.published and raw_data.get_state() == models.PoliceStationRawData.STATE_PARSED \
                    and raw_data.date not in mgr.published_data_date:
                data_date = raw_data.date.isoformat()
                entity = models.PublishedPoliceStations(id=data_date)
                qry = models.PoliceStation.query_entities(data_date)
                cursor = None
                more = True
                list = []
                while more:
                    ps = dict()
                    page, cursor, more = qry.fetch_page(100, start_cursor=cursor)
                    for p in page:
                        ps['name'] = p.name
                        ps['tel'] = p.tel
                        ps['address'] = p.address
                        ps['geo'] = p.latlng.__unicode__()
                    list.append(ps)
                entity.list = list
                raw_data.published = True
                mgr.published_data_date.append(raw_data.date)
                mgr.published_data_date.sort(reverse=True)
                ndb.put_multi([entity, raw_data, mgr])
        else:
            status_int = 410  # gone

        return status_int

    def unpublish_police_stations(self, keysafe):

        status_int = 200

        raw_data = ndb.Key(urlsafe=keysafe).get()
        if raw_data:
            mgr = models.PoliceStationManager.getInstance()
            if raw_data.published and raw_data.get_state() == models.PoliceStationRawData.STATE_PARSED \
                    and raw_data.date in mgr.published_data_date:
                data_date = raw_data.date.isoformat()
                published_police_stations_entity_key = ndb.Key(models.PublishedPoliceStations, data_date)
                published_police_stations_entity_key.delete()
                raw_data.published = False
                mgr.published_data_date.remove(raw_data.date)
                ndb.put_multi([raw_data, mgr])
        else:
            status_int = 410  # gone

        return status_int


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/opendata/get_upload_url', ODGetUploadUrl),
    RedirectRoute(r'/opendata/police_stations', handler=ODPoliceStationsHandler, name='opendata-police-stations',
                  strict_slash=True),
    RedirectRoute(r'/opendata', handler=ODCollectionHandler, name='opendata-collection', strict_slash=True),
]
