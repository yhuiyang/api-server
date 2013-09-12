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
from datetime import time

# GAE imports
import webapp2

# local imports
import costco_models as models


###########################################################################
# Events Offers
###########################################################################
class ApiV1CostcoWhatsNew(webapp2.RequestHandler):

    def get(self):

        # retrieve latest event timestamp in client side
        str_client_latest = self.request.get('timestamp')
        if str_client_latest:
            int_client_latest = int(str_client_latest)
        else:
            int_client_latest = 0

        # query event manager the newer events
        eventMgrEntity = models.EventManager.get_or_insert(models.COSTCO_EVENT_MANAGER)
        int_version_list = []
        for meta in eventMgrEntity.listPublishedMeta:
            if int_client_latest < int(meta.created.strftime('%s')):
                int_version_list.append(meta.version)
        int_version_list.sort(reverse=True)

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(int_version_list)


class ApiV1CostcoEvents(webapp2.RequestHandler):

    def get(self):

        # EventManager holds published event meta list, which holds version number and created time for each event
        eventMgrEntity = models.EventManager.get_or_insert(models.COSTCO_EVENT_MANAGER)
        int_version_list = []
        for meta in eventMgrEntity.listPublishedMeta:
            int_version_list.append(meta.version)
        int_version_list.sort(reverse=True)

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(int_version_list)


class ApiV1CostcoEventDetail(webapp2.RequestHandler):

    def get(self, event_id):

        self.response.content_type = 'application/json'

        strEventVer = event_id
        intEventVer = int(event_id)

        # check if event with this version is published or not
        eventMgrEntity = models.EventManager.get_or_insert(models.COSTCO_EVENT_MANAGER)
        metaIdx = 0
        for meta in eventMgrEntity.listPublishedMeta:
            if meta.version == intEventVer:
                break
            metaIdx += 1
        if metaIdx >= len(eventMgrEntity.listPublishedMeta):
            logging.warning('Bad client! It requests an unpublished event!')
            resp = {'error': 'Requested event is not yet published!'}
            self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))
            return

        publishedEventEntity = models.PublishedEvent.get_by_id(strEventVer)
        if publishedEventEntity is None:
            logging.error('There is version number in published version list, but not published event entity!')
            resp = {'error': 'Internal error!'}
        else:
            resp = publishedEventEntity.event_data
            # append published event created epoch time
            resp['created'] = int(eventMgrEntity.listPublishedMeta[metaIdx].created.strftime('%s'))
        self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))


###########################################################################
# Stores
###########################################################################
class ApiV1CostcoStoreWhatsNew(webapp2.RequestHandler):

    def get(self):

        stores = []

        storesDS = models.PublishedStores.get_by_id(models.COSTCO_PUBLISHED_STORES)
        if storesDS:
            client_timestamp = self.request.get('timestamp')
            if client_timestamp:  # filter by client timestamp
                for store in storesDS.stores:
                    if store['modified'] > int(client_timestamp):
                        stores.append(store)
            else:  # no filter at all
                stores = storesDS.stores

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(stores, indent=None, separators=(',', ':'))


###########################################################################
# Items
###########################################################################


###########################################################################
# Routes
###########################################################################
routes = [
    webapp2.Route(r'/api/v1/costco/whatsnew', handler=ApiV1CostcoWhatsNew),
    webapp2.Route(r'/api/v1/costco/events', handler=ApiV1CostcoEvents),
    webapp2.Route(r'/api/v1/costco/event/<event_id:[1-9]\d*>', ApiV1CostcoEventDetail),
    webapp2.Route(r'/api/v1/costco/stores/whatsnew', handler=ApiV1CostcoStoreWhatsNew),
]
