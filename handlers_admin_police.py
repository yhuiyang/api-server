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
from datetime import date, datetime

# GAE imports
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
# Open data - Police station data detail
###########################################################################
class PoliceStationDetailHandler(BaseHandler):

    PAGE_SIZE = 10

    def get(self, date, rev):

        result_page, next_cursor, more = models.PoliceStation.query_entities(date, rev).fetch_page(self.PAGE_SIZE)

        params = {
            'app_name': 'Police Station - ' + date + 'r' + rev,
            'police_stations': result_page,
        }
        self.render_response('od_police_detail.html', **params)


############################################################################
# Open data - Police stations data management
############################################################################
class PoliceStationsHandler(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    # Prepare admin page to provide the following functions:
    #  0) show latest published data
    #    GET
    #  1) upload csv data to blob store. (create corresponding PoliceStationRawData entity)
    #    POST
    #  2) execute actions for specific uploaded csv
    #    PUT action=parse and publish (not support un-publish), data=urlsafe of PoliceStationRawData
    #    When parse, create many PoliceStation entities, when publish, convert many PoliceStation entities to
    #    single PublishedPoliceStations and save record in PoliceStationManager

    def get(self):

        station_list = []
        stations = models.PoliceStationRawData.query()
        for station in stations:
            d = dict()
            blob_info = BlobInfo(station.blob_key)
            d['name'] = blob_info.filename
            d['size'] = blob_info.size
            d['creation'] = blob_info.creation
            d['date'] = station.date
            d['revision'] = station.rev
            d['token'] = station.key.urlsafe()
            d['state'] = station.state
            station_list.append(d)

        params = {
            'app_name': 'Open Data - Police Stations',
            'success_path': self.uri_for('opendata-police-stations'),
            'police_stations': station_list,
        }
        self.render_response('od_police.html', **params)

    def post(self):

        csv_files = self.get_uploads('csv-file')
        csv_date = self.request.get('csv-date')
        if len(csv_files) == 1 and csv_date:

            # retrieve blob info entity
            blob_info = csv_files[0]

            # check is there raw data with the same date? And how many? (used to determinate revision number)
            y, m, d = csv_date.split('-')
            src_date = date(int(y), int(m), int(d))
            existed_revision = models.PoliceStationRawData.get_count(src_date)

            # create corresponding raw data entity
            raw_data_entity = models.PoliceStationRawData()
            raw_data_entity.blob_key = blob_info.key()
            raw_data_entity.date = src_date
            raw_data_entity.rev = existed_revision + 1
            raw_data_entity.put()

        self.redirect_to('opendata-police-stations')

    def put(self):

        token = self.request.get('token')
        action = self.request.get('action')

        if action == 'populate':
            result = self.populate(token)
        elif action == 'publish':
            result = self.publish(token)
        else:
            result = 400
        self.response.status_int = result

    def populate(self, token):
        if token:
            raw_data = ndb.Key(urlsafe=token).get()
            if raw_data:
                if raw_data.state == models.PoliceStationRawData.STATE_INITIAL:
                    start_time = datetime.now()

                    raw_data.state = models.PoliceStationRawData.STATE_PROCESSING
                    raw_data.put()

                    reader = blobstore.BlobReader(raw_data.blob_key)

                    @ndb.transactional
                    def populate__(reader):
                        id = raw_data.date.isoformat() + 'r' + str(raw_data.rev)
                        dummyGroupKey = ndb.Key(models.PoliceStation, id)
                        put_count = 0
                        for line in reader:
                            if runtime.is_shutting_down():
                                return False, 0
                            columns = line.rstrip().split(',')
                            station = models.PoliceStation(parent=dummyGroupKey)
                            station.name = columns[0]
                            station.tel = columns[1]
                            station.address = columns[2]
                            station.xy = [float(columns[3]), float(columns[4])]
                            station.county = columns[5]
                            station.township = columns[6]
                            station.latlng = ndb.GeoPt(lat=float(columns[7]), lon=float(columns[8]))
                            station.put()
                            put_count += 1
                        return True, put_count

                    populate_result, populate_count = populate__(reader)
                    reader.close()

                    if not populate_result:
                        logging.warning('Population is terminated early!')
                        result = 503  # service unavailable
                        # check_runtime_usage()
                        raw_data.state = models.PoliceStationRawData.STATE_INITIAL
                    else:
                        logging.info('Population is completed!')
                        result = 200
                        raw_data.state = models.PoliceStationRawData.STATE_POPULATED
                    raw_data.put()

                    end_time = datetime.now()
                    delta = end_time - start_time
                    logging.info('It spends %s seconds to populate %d police station entities.' %
                                 (delta.total_seconds(), populate_count))
                else:
                    logging.warning('The specific raw data can not be populated.')
                    result = 409  # conflict
            else:
                logging.error('The token provided by client is invalid.')
                result = 410  # gone
        else:
            logging.error("Client doesn't provide token.")
            result = 400  # bad request
        return result

    def publish(self, token):
        if token:
            raw_data = ndb.Key(urlsafe=token).get()
            if raw_data:
                # check raw data is in correct state. (populated, but not yet published)
                if raw_data.state == models.PoliceStationRawData.STATE_POPULATED:
                    mgr = models.PoliceStationManager.getInstance()
                    # check data date and/or rev is newer
                    published_allowed = True
                    for meta in mgr.meta_list:
                        if raw_data.date < meta.date:
                            published_allowed = False
                            break
                        elif raw_data.date == meta.date and raw_data.rev <= meta.rev:
                            published_allowed = False
                            break
                    if published_allowed:

                        # mark busy
                        raw_data.state = models.PoliceStationRawData.STATE_PROCESSING
                        raw_data.put()

                        # build PublishedPoliceStations entity from PoliceStation entities
                        strId = raw_data.date.isoformat() + 'r' + str(raw_data.rev)
                        entity = models.PublishedPoliceStations(id=strId)
                        stations = models.PoliceStation.query_entities(raw_data.date, raw_data.rev)
                        cursor = None
                        more = True
                        list = []
                        while more:
                            page, cursor, more = stations.fetch_page(100, start_cursor=cursor)
                            for p in page:
                                ps = dict()
                                ps['name'] = p.name
                                ps['tel'] = p.tel
                                ps['address'] = p.address
                                ps['county'] = p.county
                                ps['township'] = p.township
                                ps['geo'] = p.latlng.__unicode__()
                                list.append(ps)
                        entity.list = list

                        # mark completed (published)
                        raw_data.state = models.PoliceStationRawData.STATE_PUBLISHED

                        # append new record to manager
                        mgr.meta_list.append(models.PublishedPSMeta(date=raw_data.date, rev=raw_data.rev))

                        # finally put
                        ndb.put_multi([entity, mgr, raw_data])
                        result = 200
                    else:
                        logging.warning('The specific raw data can not be published. (Older data)')
                        result = 409  # conflict
                else:
                    logging.warning('The specific raw data can not be published. (Incorrect state)')
                    result = 409  # conflict
            else:
                logging.error('The token provided by client is invalid.')
                result = 410  # gone
        else:
            logging.error("Client doesn't provide token.")
            result = 400  # bad request
        return result


###########################################################################
# Routes
###########################################################################
routes = [
    RedirectRoute(r'/opendata/police_station/<date:\d{4}-\d{2}-\d{2}>r<rev:[1-9]\d*>',
                  handler=PoliceStationDetailHandler, name='police-station-detail', strict_slash=True),
    RedirectRoute(r'/opendata/police_stations', handler=PoliceStationsHandler, name='opendata-police-stations',
                  strict_slash=True),
]
