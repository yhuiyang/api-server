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

# GAE imports
from google.appengine.ext import ndb

# local imports


###########################################################################
# Events Offers
###########################################################################
COSTCO_EVENT_MANAGER = 'CostcoEventManager'


class PublishedMeta(ndb.Model):
    version = ndb.IntegerProperty(indexed=False)
    created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)


class EventManager(ndb.Model):  # one entity
    listPublishedMeta = ndb.LocalStructuredProperty(PublishedMeta, repeated=True)
    lastCreatedVersion = ndb.IntegerProperty(default=0, indexed=False)


class PublishedEvent(ndb.Model):
    event_data = ndb.JsonProperty(required=True, indexed=False)


class Event(ndb.Model):  # one major version, one entity, id=major version
    start = ndb.DateProperty(required=True)
    end = ndb.DateProperty(required=True)
    patch = ndb.IntegerProperty(default=0, indexed=False)
    published = ndb.BooleanProperty(default=False, indexed=False)
    modified = ndb.BooleanProperty(default=False, indexed=False)
    type = ndb.StringProperty(default='coupon', choices=['coupon', 'exhibition', 'preview', 'announcement'],
                              indexed=False)


class EventItem(ndb.Model):
    data = ndb.JsonProperty(required=True)

    @classmethod
    def get_event_items(cls, event_version):
        if isinstance(event_version, str):
            intEventVersion = int(event_version)
            intEventMajorVer = (intEventVersion / 100) * 100
        elif isinstance(event_version, int):
            intEventMajorVer = (event_version / 100) * 100
        else:
            return None

        return EventItem.query(ancestor=ndb.Key(Event, str(intEventMajorVer)))

    @classmethod
    def get_user_fields(cls, event_type='coupon'):
        """
        Fields provided by user input
        """
        if event_type == 'coupon':
            fields = ['brand', 'cname', 'ename', 'spec', 'code', 'discount', 'unit', 'price', 'note']
        elif event_type == 'exhibition':
            fields = ['title', 'start', 'end', 'locations']
        elif event_type == 'preview':
            fields = ['brand', 'cname', 'ename', 'spec', 'code', 'price', 'note']
        elif event_type == 'announcement':
            fields = ['title', 'content']
        else:
            fields = []
        return fields

    @classmethod
    def get_blob_fields(cls):
        """
        Fields provided by blobstore and image service
        """
        fields = ['url', 'blob_creation', 'content_type', 'md5_hash', 'size', 'filename', 'blob_key', 'img_height',
                  'img_width']
        return fields

    @classmethod
    def get_web_fields(cls, event_type='coupon'):
        """
        Fields used on web management page
        """
        if event_type == 'coupon':
            fields = ['url', 'blob_key', 'urlsafe', 'brand', 'cname', 'ename', 'spec', 'code', 'discount', 'unit',
                      'price', 'note']
        elif event_type == 'exhibition':
            fields = ['url', 'blob_key', 'urlsafe', 'title', 'start', 'end', 'locations']
        elif event_type == 'preview':
            fields = ['url', 'blob_key', 'urlsafe', 'brand', 'cname', 'ename', 'spec', 'code', 'price', 'note']
        elif event_type == 'announcement':
            fields = ['url', 'blob_key', 'urlsafe', 'title', 'content']
        else:
            fields = []
        return fields

    @classmethod
    def get_published_fields(cls, event_type='coupon'):
        """
        Fields used by the app client
        """
        if event_type == 'coupon':
            fields = ['url', 'filename', 'img_height', 'img_width', 'brand', 'cname', 'ename', 'spec', 'code',
                      'discount', 'unit', 'price', 'note']
        elif event_type == 'exhibition':
            fields = ['url', 'filename', 'img_height', 'img_width', 'title', 'start', 'end', 'locations']
        elif event_type == 'preview':
            fields = ['url', 'filename', 'img_height', 'img_width', 'brand', 'cname', 'ename', 'spec', 'code', 'price',
                      'note']
        elif event_type == 'announcement':
            fields = ['url', 'filename', 'img_height', 'img_width', 'title', 'content']
        else:
            fields = []
        return fields


###########################################################################
# Stores
###########################################################################
class BusinessHour(ndb.Model):
    dayOfWeekBegin = ndb.IntegerProperty(required=True, indexed=False)
    dayOfWeekEnd = ndb.IntegerProperty(required=True, indexed=False)
    hourBegin = ndb.TimeProperty(required=True, indexed=False)
    hourEnd = ndb.TimeProperty(required=True, indexed=False)


class Store(ndb.Model):
    name = ndb.StringProperty(required=True, indexed=False)
    address = ndb.StringProperty(required=True, indexed=False)
    phone = ndb.StringProperty(required=True, indexed=False)
    businessHour = ndb.LocalStructuredProperty(BusinessHour, repeated=True, indexed=False)
    geo = ndb.GeoPtProperty(required=True, indexed=False)
    services = ndb.StringProperty(required=True, indexed=False)
    modified = ndb.DateTimeProperty(auto_now=True, indexed=False)


COSTCO_PUBLISHED_STORES = 'CostcoPublishedStores'


class PublishedStores(ndb.Model):
    stores = ndb.JsonProperty(required=True, indexed=False)
