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
from webapp2_extras.appengine.users import admin_required
from webapp2_extras.routes import RedirectRoute
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

# local imports
import costco_models
from base_handlers import BaseHandler


class CostcoEventCRUD(BaseHandler):

    def getAllEventMajorVersionList(self):
        """
        Retrieve a unsorted list which contains event major version integer number.
        Query data store only if querying mem cache is missed.

        Return: python list. Ex: [1400, 800, 900]
        """
        allEventMajorVersionList = getCachedCostcoAllEventMajorVersions('list')
        if allEventMajorVersionList is None:
            allEventInDatastore = costco_models.Event.query()
            eventMajorVerList = []
            for ver in allEventInDatastore:
                eventMajorVerList.append(int(ver.key.id()))

            setCachedCostcoAllEventMajorVersions(eventMajorVerList)
        else:
            eventMajorVerList = allEventMajorVersionList

        return eventMajorVerList

    @admin_required
    def get(self):

        eventMajorVerList = self.getAllEventMajorVersionList()
        eventMajorVerList.sort(reverse=True)

        # prepare for rendering data
        events = []
        for majorVerInt in eventMajorVerList:
            event = {}
            eventEntity = costco_models.Event.get_by_id(str(majorVerInt))
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
            'app_name': 'Costco',
            'events': events
        }
        self.render_response('costco_event_list.html', **params)

    def post(self):

        if not users.is_current_user_admin():
            self.abort(403)

        start_date = self.request.get('date-start')
        end_date = self.request.get('date-end')
        type = self.request.get('type')

        logging.debug('start: %s, end: %s, type: %s' % (start_date, end_date, type))

        sY, sM, sD = start_date.split('-')
        eY, eM, eD = end_date.split('-')

        mgrKey = ndb.Key(costco_models.EventManager, costco_models.COSTCO_EVENT_MANAGER)
        mgrEntity = mgrKey.get()
        if mgrEntity is None:
            logging.debug('''Manager entity doesn't exist yet''')
            mgrEntity = costco_models.EventManager(id=costco_models.COSTCO_EVENT_MANAGER)
            newVer = 100
        else:
            newVer = mgrEntity.lastCreatedVersion + 100

        mgrEntity.lastCreatedVersion = newVer
        event = costco_models.Event(id=str(newVer))
        event.start = date(int(sY), int(sM), int(sD))
        event.end = date(int(eY), int(eM), int(eD))
        event.type = type

        ndb.put_multi([event, mgrEntity])

        # update memcache
        appendCachedCostcoAllEventMajorVersions(newVer)

        self.redirect_to('costco-event-crud')


class CostcoEventItemCRUD(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    @admin_required
    def get(self, event_id):

        # find all items belongs to this event
        allItems = costco_models.Item.get_event_items(event_id)

        # populate item_list for later rendering
        eventKey = ndb.Key(costco_models.Event, str((int(event_id) / 100) * 100))
        eventEntity = eventKey.get()
        item_list = []
        for item in allItems:
            item_prop = {}
            for n in costco_models.Item.get_web_fields(eventEntity.type):
                if n == 'urlsafe':
                    item_prop[n] = item.key.urlsafe()
                else:
                    item_prop[n] = item.data.get(n)
            item_list.append(item_prop)
        logging.debug(item_list)

        params = {
            'app_name': 'Costco',
            'event': eventEntity,
            'Items': item_list,
        }
        self.render_response('costco_event_item_list.html', **params)

    def post(self, event_id):

        if not users.is_current_user_admin():
            self.abort(403)

        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        blob_key = blob_info.key()

        data_dict = dict()
        # collect item image meta data
        # blobstore.BlobInfo.properties() = set(['creation', 'content_type', 'md5_hash', 'size', 'fielname'])
        for prop in costco_models.Item.get_blob_fields():
            if prop == 'url':
                data_dict[prop] = images.get_serving_url(blob_key)
            elif prop == 'creation':
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

        # collect item info
        int_event_id = int(event_id)
        event_key = str((int_event_id / 100) * 100)
        eventEntity = costco_models.Event.get_by_id(event_key)
        for prop in costco_models.Item.get_user_fields(eventEntity.type):
            if prop == 'locations':
                data_dict[prop] = self.request.get_all(prop)
            else:
                data_dict[prop] = self.request.get(prop)

        # mark event dirty
        eventEntity.modified = True

        # create new item in datastore
        item = costco_models.Item(parent=eventEntity.key)
        item.data = data_dict

        # update datastore
        ndb.put_multi([item, eventEntity])

        self.redirect_to('costco-event-item-crud', event_id=event_id, _code=303)

    def put(self, event_id):

        if not users.is_current_user_admin():
            self.abort(403)

        intEventMajorVer = (int(event_id) / 100) * 100
        strEventMajorVer = str(intEventMajorVer)
        eventKey = ndb.Key(costco_models.Event, strEventMajorVer)

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
                eventMgrEntity = costco_models.EventManager.get_or_insert(costco_models.COSTCO_EVENT_MANAGER)

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
                allEventItems = costco_models.Item.get_event_items(event_id)
                for item in allEventItems:
                    item_published_data = dict()
                    for prop in costco_models.Item.get_published_fields(eventEntity.type):
                        item_published_data[prop] = item.data[prop]
                    event_data['items'].append(item_published_data)

                publishedEventEntity = costco_models.PublishedEvent(id=str(intEventVer))
                publishedEventEntity.event_data = event_data

                # append event version number into published event meta list
                eventMgrEntity.listPublishedMeta.append(costco_models.PublishedMeta(version=intEventVer))

                # update data store
                ndb.put_multi([eventMgrEntity, eventEntity, publishedEventEntity])

            elif request_publish == 'false':  # do un-publish

                # check if already published
                if eventEntity.published is False:
                    logging.warning('Request un-publish a not-yet-published event, skip action!')
                    self.abort(406)  # not acceptable

                # retrieve event manager
                eventMgrEntity = costco_models.EventManager.get_or_insert(costco_models.COSTCO_EVENT_MANAGER)

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
        for prop in costco_models.Item.get_user_fields(eventEntity.type):
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

        if not users.is_current_user_admin():
            self.abort(403)

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
            eventEntity = costco_models.Event.get_by_id(keyEventId)
            # mark event dirty
            if eventEntity is not None:
                eventEntity.modified = True
                eventEntity.put()
                # self.redirect_to('costco-event-item-crud', event_id=event_id, _code=303)  # move redirect to client


class CostcoEventItemImageUpload(webapp2.RequestHandler):

    @admin_required
    def get(self, event_id):

        self.response.content_type = 'application/json'
        # the url to post to blobstore is dynamically generated by GAE,
        # when blob upload completed, GAE will invoke our callback handler
        # registered on the success_path
        success_path = self.uri_for('costco-event-item-crud', event_id=event_id)
        upload_url = [blobstore.create_upload_url(success_path)]
        self.response.body = json.dumps(upload_url)


class ApiV1CostcoWhatsNew(BaseHandler):

    def get(self):

        # retrieve latest event timestamp in client side
        str_client_latest = self.request.get('timestamp')
        if str_client_latest:
            int_client_latest = int(str_client_latest)
        else:
            int_client_latest = 0

        # query event manager the newer events
        eventMgrEntity = costco_models.EventManager.get_or_insert(costco_models.COSTCO_EVENT_MANAGER)
        int_version_list = []
        for meta in eventMgrEntity.listPublishedMeta:
            if int_client_latest < int(meta.created.strftime('%s')):
                int_version_list.append(meta.version)
        int_version_list.sort(reverse=True)

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(int_version_list)


class ApiV1CostcoEvents(BaseHandler):

    def get(self):

        # EventManager holds published event meta list, which holds version number and created time for each event
        eventMgrEntity = costco_models.EventManager.get_or_insert(costco_models.COSTCO_EVENT_MANAGER)
        int_version_list = []
        for meta in eventMgrEntity.listPublishedMeta:
            int_version_list.append(meta.version)
        int_version_list.sort(reverse=True)

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(int_version_list)


class ApiV1CostcoEventDetail(BaseHandler):

    def get(self, event_id):

        self.response.content_type = 'application/json'

        strEventVer = event_id
        intEventVer = int(event_id)

        # check if event with this version is published or not
        eventMgrEntity = costco_models.EventManager.get_or_insert(costco_models.COSTCO_EVENT_MANAGER)
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

        publishedEventEntity = costco_models.PublishedEvent.get_by_id(strEventVer)
        if publishedEventEntity is None:
            logging.error('There is version number in published version list, but not published event entity!')
            resp = {'error': 'Internal error!'}
        else:
            resp = publishedEventEntity.event_data
            # append published event created epoch time
            resp['created'] = int(eventMgrEntity.listPublishedMeta[metaIdx].created.strftime('%s'))
        self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))


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

routes = [
    RedirectRoute(r'/costco/event/<event_id:[1-9]\d*>', handler=CostcoEventItemCRUD,
                  name='costco-event-item-crud', strict_slash=True),
    webapp2.Route(r'/costco/event/<event_id:[1-9]\d*>/upload', CostcoEventItemImageUpload),
    RedirectRoute(r'/costco/events', handler=CostcoEventCRUD,
                  name='costco-event-crud', strict_slash=True),
    webapp2.Route(r'/api/v1/costco/whatsnew', handler=ApiV1CostcoWhatsNew),
    webapp2.Route(r'/api/v1/costco/events', handler=ApiV1CostcoEvents),
    webapp2.Route(r'/api/v1/costco/event/<event_id:[1-9]\d*>', ApiV1CostcoEventDetail),
]
