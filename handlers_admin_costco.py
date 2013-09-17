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
from webapp2_extras.routes import RedirectRoute
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

# local imports
import models_costco as models
from handlers_admin_base import BaseHandler


###########################################################################
# Events Offers
###########################################################################
class CostcoEventCRUD(BaseHandler):

    def getAllEventMajorVersionList(self):
        """
        Retrieve a unsorted list which contains event major version integer number.
        Query data store only if querying mem cache is missed.

        Return: python list. Ex: [1400, 800, 900]
        """
        allEventMajorVersionList = getCachedCostcoAllEventMajorVersions('list')
        if allEventMajorVersionList is None:
            allEventInDatastore = models.Event.query()
            eventMajorVerList = []
            for ver in allEventInDatastore:
                eventMajorVerList.append(int(ver.key.id()))

            setCachedCostcoAllEventMajorVersions(eventMajorVerList)
        else:
            eventMajorVerList = allEventMajorVersionList

        return eventMajorVerList

    def get(self):

        eventMajorVerList = self.getAllEventMajorVersionList()
        eventMajorVerList.sort(reverse=True)

        # prepare for rendering data
        events = []
        for majorVerInt in eventMajorVerList:
            event = {}
            eventEntity = models.Event.get_by_id(str(majorVerInt))
            event['start'] = eventEntity.start
            event['end'] = eventEntity.end
            event['published'] = eventEntity.published
            event['modified'] = eventEntity.modified
            event['ver'] = majorVerInt + eventEntity.patch
            event['type'] = eventEntity.type
            event['majorVer'] = majorVerInt
            events.append(event)

        #logging.debug(events)

        params = {
            'app_name': 'Costco Events Offers',
            'events': events
        }
        self.render_response('costco_event_list.html', **params)

    def post(self):

        start_date = self.request.get('date-start')
        end_date = self.request.get('date-end')
        type = self.request.get('type')

        logging.debug('start: %s, end: %s, type: %s' % (start_date, end_date, type))

        sY, sM, sD = start_date.split('-')
        eY, eM, eD = end_date.split('-')

        mgrKey = ndb.Key(models.EventManager, models.COSTCO_EVENT_MANAGER)
        mgrEntity = mgrKey.get()
        if mgrEntity is None:
            logging.debug('''Manager entity doesn't exist yet''')
            mgrEntity = models.EventManager(id=models.COSTCO_EVENT_MANAGER)
            newVer = 100
        else:
            newVer = mgrEntity.lastCreatedVersion + 100

        mgrEntity.lastCreatedVersion = newVer
        event = models.Event(id=str(newVer))
        event.start = date(int(sY), int(sM), int(sD))
        event.end = date(int(eY), int(eM), int(eD))
        event.type = type

        ndb.put_multi([event, mgrEntity])

        # update memcache
        appendCachedCostcoAllEventMajorVersions(newVer)

        self.redirect_to('costco-event-crud')


class CostcoEventItemCRUD(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    def get(self, event_id):

        # find all items belongs to this event
        allItems = models.EventItem.get_event_items(event_id)

        # populate item_list for later rendering
        eventKey = ndb.Key(models.Event, str((int(event_id) / 100) * 100))
        eventEntity = eventKey.get()
        item_list = []
        for item in allItems:
            item_prop = {}
            for n in models.EventItem.get_web_fields(eventEntity.type):
                if n == 'urlsafe':
                    item_prop[n] = item.key.urlsafe()
                else:
                    item_prop[n] = item.data.get(n)
            item_list.append(item_prop)
        logging.debug(item_list)

        # populate store list for exhibition type event
        published_store_select = []
        if eventEntity.type == 'exhibition':
            storesDS = models.PublishedStores.get_by_id(models.COSTCO_PUBLISHED_STORES)
            if storesDS:
                for store in storesDS.stores:
                    sel = dict()
                    sel['value'] = store['id']
                    sel['name'] = store['name']
                    published_store_select.append(sel)

        params = {
            'app_name': 'Costco Events Offers',
            'event': eventEntity,
            'Items': item_list,
            'store_select_list': published_store_select,
        }
        self.render_response('costco_event_item_list.html', **params)

    def post(self, event_id):

        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        blob_key = blob_info.key()

        data_dict = dict()
        # collect item image meta data
        # blobstore.BlobInfo.properties() = set(['creation', 'content_type', 'md5_hash', 'size', 'fielname'])
        for prop in models.EventItem.get_blob_fields():
            if prop == 'url':
                data_dict[prop] = images.get_serving_url(blob_key)
            elif prop == 'blob_creation':
                data_dict[prop] = blob_info.creation.isoformat()
            elif prop == 'content_type':
                data_dict[prop] = blob_info.content_type
            elif prop == 'md5_hash':
                data_dict[prop] = blob_info.md5_hash
            elif prop == 'size':
                data_dict[prop] = blob_info.size
            elif prop == 'filename':
                data_dict[prop] = blob_info.filename
            elif prop == 'blob_key':
                data_dict[prop] = str(blob_key)
            elif prop == 'img_height':
                img = images.Image(blob_key=blob_key)
                img.im_feeling_lucky()
                img.execute_transforms()
                data_dict['img_height'] = str(img.height)
                data_dict['img_width'] = str(img.width)
            elif prop == 'img_width':
                pass  # do nothing

        # collect item info
        int_event_id = int(event_id)
        event_key = str((int_event_id / 100) * 100)
        eventEntity = models.Event.get_by_id(event_key)
        for prop in models.EventItem.get_user_fields(eventEntity.type):
            if prop == 'locations':
                data_dict[prop] = self.request.get_all(prop)
            else:
                user_input_str = self.request.get(prop)
                data_dict[prop] = user_input_str.replace('\r', '')

        #logging.debug(data_dict)  # logging all input data

        # mark event dirty
        eventEntity.modified = True

        # create new item in datastore
        item = models.EventItem(parent=eventEntity.key)
        item.data = data_dict

        # update datastore
        ndb.put_multi([item, eventEntity])

        self.redirect_to('costco-event-item-crud', event_id=event_id, _code=303)

    def put(self, event_id):

        intEventMajorVer = (int(event_id) / 100) * 100
        strEventMajorVer = str(intEventMajorVer)
        eventKey = ndb.Key(models.Event, strEventMajorVer)

        eventEntity = eventKey.get()
        if eventEntity is None:
            logging.error('Invalid event id.')
            self.abort(404)

        # edit event publish state
        request_publish = self.request.get('publish')
        if request_publish is not None and request_publish in ['true', 'false']:
            intEventVer = intEventMajorVer + eventEntity.patch

            if request_publish == 'true':  # do publish

                patchAdvance = True

                # check if modification happened
                if eventEntity.modified is False:
                    logging.warning('Request publish a non-modification event, patch will not be advanced!')
                    patchAdvance = False

                # retrieve event manager
                eventMgrEntity = models.EventManager.get_or_insert(models.COSTCO_EVENT_MANAGER)

                # check if still in published state
                if eventEntity.published is True:
                    try:
                        # loop through meta and find index of this meta
                        metaIdx = 0
                        for meta in eventMgrEntity.listPublishedMeta:
                            if meta.version == intEventVer:
                                break
                            metaIdx += 1
                        del(eventMgrEntity.listPublishedMeta[metaIdx])
                    except IndexError:
                        logging.error('Remove non-exist version(%d) from published meta list.' % intEventVer)

                # update event fields
                if patchAdvance:
                    eventEntity.patch += 1
                eventEntity.modified = False
                eventEntity.published = True

                # new event version number
                intEventVer = intEventMajorVer + eventEntity.patch

                # populate this event data and create new one published event entity for it
                event_data = dict()
                event_data['start'] = eventEntity.start.isoformat()
                event_data['end'] = eventEntity.end.isoformat()
                event_data['type'] = eventEntity.type
                event_data['items'] = []
                allEventItems = models.EventItem.get_event_items(event_id)
                for item in allEventItems:
                    item_published_data = dict()
                    for prop in models.EventItem.get_published_fields(eventEntity.type):
                        try:
                            item_published_data[prop] = item.data[prop]
                        except KeyError:
                            logging.warning('(Old) item data without field: %s. Remove it?' % prop)
                            item_published_data[prop] = ''
                    event_data['items'].append(item_published_data)

                publishedEventEntity = models.PublishedEvent(id=str(intEventVer))
                publishedEventEntity.event_data = event_data

                # append event version number into published event meta list
                eventMgrEntity.listPublishedMeta.append(models.PublishedMeta(version=intEventVer))

                # update data store
                ndb.put_multi([eventMgrEntity, eventEntity, publishedEventEntity])

            elif request_publish == 'false':  # do un-publish

                # check if already published
                if eventEntity.published is False:
                    logging.warning('Request un-publish a not-yet-published event, skip action!')
                    self.abort(406)  # not acceptable

                # retrieve event manager
                eventMgrEntity = models.EventManager.get_or_insert(models.COSTCO_EVENT_MANAGER)

                try:
                    metaIdx = 0
                    for meta in eventMgrEntity.listPublishedMeta:
                        if meta.version == intEventVer:
                            break
                        metaIdx += 1
                    del(eventMgrEntity.listPublishedMeta[metaIdx])
                except IndexError:
                    logging.error("Event is marked published, but doesn't find in published event meta list!")

                # update event fields
                eventEntity.published = False

                # update data store
                ndb.put_multi([eventMgrEntity, eventEntity])

            return

        # edit event item properties
        urlsafeKey = self.request.get('urlsafe')
        if len(urlsafeKey) == 0:
            logging.error("Request doesn't contain a valid item urlsafe key.")
            self.abort(404)

        itemKey = ndb.Key(urlsafe=urlsafeKey)
        itemEntity = itemKey.get()
        if itemEntity is None:
            logging.error('Request urlsafe is invalid.')
            self.abort(404)

        item_data = itemEntity.data
        for prop in models.EventItem.get_user_fields(eventEntity.type):
            old = item_data[prop]
            if prop in ['locations']:
                new = self.request.get_all('locations[]')
            else:
                new = self.request.get(prop)
            item_data[prop] = new
            logging.debug('Property %s: old [%s], new [%s]' % (prop, old, new))

        eventEntity.modified = True
        ndb.put_multi([eventEntity, itemEntity])

    def delete(self, event_id):

        # delete image in blobstore & serving url
        strBlobKey = self.request.get('blob_key')
        if strBlobKey:
            images.delete_serving_url(strBlobKey)
            blobInfo = blobstore.BlobInfo.get(strBlobKey)
            if blobInfo is not None:
                blobInfo.delete()

        # delete item in datastore
        strItemKey = self.request.get('item_key')
        if strItemKey:
            ndb.Key(urlsafe=strItemKey).delete()
            intEventId = int(event_id)
            keyEventId = str((intEventId / 100) * 100)
            eventEntity = models.Event.get_by_id(keyEventId)
            # mark event dirty
            if eventEntity is not None:
                eventEntity.modified = True
                eventEntity.put()
                # self.redirect_to('costco-event-item-crud', event_id=event_id, _code=303)  # move redirect to client


class CostcoEventItemImageUpload(webapp2.RequestHandler):

    def get(self, event_id):

        self.response.content_type = 'application/json'
        # the url to post to blobstore is dynamically generated by GAE,
        # when blob upload completed, GAE will invoke our callback handler
        # registered on the success_path
        success_path = self.uri_for('costco-event-item-crud', event_id=event_id)
        upload_url = [blobstore.create_upload_url(success_path)]
        self.response.body = json.dumps(upload_url)


def getCachedCostcoAllEventMajorVersions(requestType='str'):
    """
    Return a json string (requestType='str') or python list (requestType='list') which contains a array or list of
    event major version number.
    Ex:
        Json string => '[ 600, 500, 300 ]' or
        Python list => [ 600, 500, 300 ]
    """
    assert requestType in ['str', 'list'], "Unknown request type, only accept 'str' or 'list'."

    verJsonStr = memcache.get('all-costco-event-major-version-list', namespace='costco')

    if verJsonStr is None or len(verJsonStr) == 2:
        return None

    if requestType == 'str':
        return verJsonStr
    elif requestType == 'list':
        return json.loads(verJsonStr)


def setCachedCostcoAllEventMajorVersions(verList_or_verStr):
    """
    Save a json string or python list which contains event major version number.
    """
    verJsonStr = None

    if isinstance(verList_or_verStr, list):
        verJsonStr = json.dumps(verList_or_verStr)
    elif isinstance(verList_or_verStr, str):
        verJsonStr = verList_or_verStr

    verList = json.loads(verJsonStr)
    assert len(verList) == 0 or isinstance(verList[0], int), 'Version is required to be integer number.'

    if verJsonStr is not None and len(verJsonStr) > 2:
        memcache.set('all-costco-event-major-version-list', verJsonStr, time=1440, namespace='costco')


def appendCachedCostcoAllEventMajorVersions(intMajorVersion):
    """
    Append one int major version into memcache.
    """
    list = getCachedCostcoAllEventMajorVersions('list')
    if list is None:
        list = []
    list.append(intMajorVersion)
    setCachedCostcoAllEventMajorVersions(list)


###########################################################################
# Stores
###########################################################################
class CostcoStoreCRUD(BaseHandler):

    def get(self):

        # Check if any query string exists, if exist, simple return json response instead of html page.
        # The name GET is a bit misleading, but has historical reasons: request.GET is not only available when
        # the HTTP method is GET. It is available for any request with query strings in the URI, for any HTTP
        # method: GET, POST, PUT etc.
        if len(self.request.GET) > 0:

            resp = {}

            store_id = self.request.get('id')
            if store_id:
                storeEntity = models.Store.get_by_id(store_id)
                if storeEntity:
                    queryItem = self.request.get('q')
                    if queryItem == 'name':
                        resp['result'] = storeEntity.name
                    elif queryItem == 'phone':
                        resp['result'] = storeEntity.phone
                    elif queryItem == 'address':
                        resp['result'] = storeEntity.address
                    elif queryItem == 'services':
                        resp['result'] = storeEntity.services
                    elif queryItem == 'geo':
                        resp['result'] = storeEntity.geo.__unicode__()
                    else:
                        self.response.status_int = 404
                        resp['error'] = 'Unsupported'
                else:
                    self.response.status_int = 404
                    resp['error'] = 'Store id is incorrect.'
            else:
                self.response.status_int = 400
                resp['error'] = 'Store id is not assigned.'

            self.response.content_type = 'application/json'
            self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))

            return

        stores = []

        allStoresInDS = models.Store.query()
        for store_in_ds in allStoresInDS:
            store = dict()
            store['id'] = store_in_ds.key.id()
            store['name'] = store_in_ds.name
            store['address'] = store_in_ds.address
            store['phone'] = store_in_ds.phone
            store['business_hour'] = []
            for bh in store_in_ds.businessHour:
                bh_dict = dict()
                bh_dict['day_of_week_begin'] = bh.dayOfWeekBegin
                bh_dict['day_of_week_end'] = bh.dayOfWeekEnd
                bh_dict['hour_of_day_begin'] = bh.hourBegin
                bh_dict['hour_of_day_end'] = bh.hourEnd
                store['business_hour'].append(bh_dict)
            store['geo'] = store_in_ds.geo
            store['services'] = store_in_ds.services

            stores.append(store)

        logging.debug(stores)

        params = {
            'app_name': 'Costco Stores',
            'stores': stores,
        }
        self.render_response('costco_store_list.html', **params)

    def post(self):

        id = self.request.get('id')
        storeEntity = models.Store(id=id)
        storeEntity.name = self.request.get('name')
        storeEntity.address = self.request.get('address').replace('\r', '')  # remove '\r' or replace '\r\n' with '\n'.
        storeEntity.phone = self.request.get('phone')

        list_day_begin = self.request.get_all('day_begin')
        list_day_end = self.request.get_all('day_end')
        list_hour_begin = self.request.get_all('hour_begin')
        list_hour_end = self.request.get_all('hour_end')
        if len(list_day_begin) != len(list_day_end) \
                or len(list_day_begin) != len(list_hour_begin) \
                or len(list_day_begin) != len(list_hour_end):
            logging.warning('Incorrect business hour setting.')
            self.response.status_int = 400
            return
        for idx in range(len(list_day_begin)):
            hb, mb = list_hour_begin[idx].split(':')
            he, me = list_hour_end[idx].split(':')
            storeEntity.businessHour.append(models.BusinessHour(dayOfWeekBegin=int(list_day_begin[idx]),
                                            dayOfWeekEnd=int(list_day_end[idx]),
                                            hourBegin=time(int(hb), int(mb)),
                                            hourEnd=time(int(he), int(me))))

        storeEntity.services = self.request.get('services').replace('\r', '')
        lat = self.request.get('lat')
        lng = self.request.get('lng')
        storeEntity.geo = ndb.GeoPt(float(lat), float(lng))

        storeEntity.put()

        self.redirect_to('costco-store-crud', _code=303)

    def put(self):

        self.response.status_int = 200

        store_id = self.request.get('id')
        if store_id:  # update store properties
            storeEntity = models.Store.get_by_id(store_id)
            if storeEntity:
                setValue = self.request.get('v')
                if not setValue:
                    self.response.status_int = 400
                    return
                setItem = self.request.get('n')
                if setItem == 'name':
                    storeEntity.name = setValue
                elif setItem == 'phone':
                    storeEntity.phone = setValue
                elif setItem == 'address':
                    storeEntity.address = setValue.replace('\r', '')
                elif setItem == 'services':
                    storeEntity.services = setValue.replace('\r', '')
                elif setItem == 'geo':
                    storeEntity.geo = ndb.GeoPt(setValue)
                else:
                    self.response.status_int = 400
            else:
                self.response.status_int = 404

            # write to datastore
            if self.response.status_int == 200:
                storeEntity.put()

        else:  # publish or unpublish stores
            state = self.request.get('state')
            if state == 'publish':
                published_store = models.PublishedStores(id=models.COSTCO_PUBLISHED_STORES)
                store_list = []
                allStoresInDS = models.Store.query()
                for store_in_ds in allStoresInDS:
                    # prepare published field for each store
                    store_dict = dict()
                    store_dict['id'] = store_in_ds.key.id()
                    store_dict['name'] = store_in_ds.name
                    store_dict['address'] = store_in_ds.address
                    store_dict['phone'] = store_in_ds.phone
                    store_dict['services'] = store_in_ds.services
                    store_dict['geo'] = store_in_ds.geo.__unicode__()
                    store_dict['modified'] = int(store_in_ds.modified.strftime('%s'))  # datetime to epoch time
                    bh_list = []
                    for bh in store_in_ds.businessHour:
                        bh_dict = dict()
                        bh_dict['day_of_week_begin'] = bh.dayOfWeekBegin
                        bh_dict['day_of_week_end'] = bh.dayOfWeekEnd
                        bh_dict['hour_of_day_begin'] = bh.hourBegin.strftime('%H:%M')
                        bh_dict['hour_of_day_end'] = bh.hourEnd.strftime('%H:%M')
                        bh_list.append(bh_dict)
                    store_dict['businessHour'] = bh_list

                    store_list.append(store_dict)
                #logging.debug(store_list)
                published_store.stores = store_list
                published_store.put()

            elif state == 'unpublish':
                published_store_key = ndb.Key(models.PublishedStores, models.COSTCO_PUBLISHED_STORES)
                if published_store_key:
                    published_store_key.delete()
            else:
                self.response.status_int = 400

    def delete(self):

        store_id = self.request.get('id')
        if store_id:
            storeEntity = models.Store.get_by_id(store_id)
            if storeEntity:
                storeEntity.key.delete_async()


###########################################################################
# Items
###########################################################################
class CostcoItemCRUD(BaseHandler):

    def get(self):

        items = []

        item = dict()
        item['id'] = '001234'
        item['brand'] = 'Brand'
        item['cname'] = 'Good'
        item['ename'] = 'Bad'
        item['price'] = 23
        images = []
        image = dict()
        image['serving_url'] = 'serving_url'
        image['blob_key_str'] = 'str(blobkey)'
        images.append(image)
        image.clear()
        item['images'] = images
        items.append(item)

        params = {
            'app_name': 'Costco Items',
            'items': items,
        }
        self.render_response('costco_item_list.html', **params)

    def post(self):

        logging.info(self.request.POST)

        self.redirect_to('costco-item-crud')


###########################################################################
# Routes
###########################################################################
routes = [
    RedirectRoute(r'/costco/event/<event_id:[1-9]\d*>', handler=CostcoEventItemCRUD, name='costco-event-item-crud',
                  strict_slash=True),
    webapp2.Route(r'/costco/event/<event_id:[1-9]\d*>/upload', CostcoEventItemImageUpload),
    RedirectRoute(r'/costco/events', handler=CostcoEventCRUD, name='costco-event-crud', strict_slash=True),
    RedirectRoute(r'/costco/stores', handler=CostcoStoreCRUD, name='costco-store-crud', strict_slash=True),
    RedirectRoute(r'/costco/items', handler=CostcoItemCRUD, name='costco-item-crud', strict_slash=True),
]
