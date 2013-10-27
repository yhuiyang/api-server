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
import datetime

# GAE imports
from google.appengine.ext import ndb

# local imports


###########################################################################
# Police Stations
###########################################################################
class PoliceStationRawData(ndb.Model):

    STATE_INITIAL = 'initial'
    STATE_POPULATED = 'populated'
    STATE_PUBLISHED = "published"
    STATE_PROCESSING = 'processing'

    date = ndb.DateProperty(required=True)
    rev = ndb.IntegerProperty(indexed=False, required=True)
    blob_key = ndb.BlobKeyProperty(indexed=False, required=True)
    state = ndb.StringProperty(indexed=False, default=STATE_INITIAL)

    @classmethod
    def get_count(cls, date=None):
        if date:
            cnt = cls.query(cls.date == date).count(keys_only=True)
        else:
            cnt = cls.query().count(keys_only=True)
        return cnt


class PoliceStation(ndb.Model):
    name = ndb.StringProperty(indexed=False, required=True)
    tel = ndb.StringProperty(indexed=False)
    address = ndb.StringProperty(indexed=False)
    county = ndb.StringProperty()
    township = ndb.StringProperty()
    xy = ndb.FloatProperty(indexed=False, repeated=True)
    latlng = ndb.GeoPtProperty(indexed=False)

    @classmethod
    def query_entities(cls, date, rev):  # date is str like '2013-09-19'. It can get from date.isoformat().
        if isinstance(date, datetime.date):
            strId = date.isoformat() + 'r' + str(rev)
        else:
            strId = date + 'r' + str(rev)
        return cls.query(ancestor=ndb.Key(PoliceStation, strId))


class PublishedPoliceStations(ndb.Model):
    list = ndb.JsonProperty(indexed=False, required=True)


class PublishedPSMeta(ndb.Model):
    time = ndb.DateTimeProperty(auto_now_add=True)  # published datetime
    date = ndb.DateProperty(required=True)  # data date
    rev = ndb.IntegerProperty(required=True)


class PoliceStationManager(ndb.Model):
    meta_list = ndb.LocalStructuredProperty(PublishedPSMeta, repeated=True)

    @classmethod
    def getInstance(cls):
        return cls.get_or_insert('PoliceStationMgr', meta_list=list())

    def getLatestDateAndRevision(self, default_date, default_rev):
        latest_date = default_date
        latest_rev = default_rev
        for meta in self.meta_list:
            if meta.date > latest_date:
                latest_date = meta.date
                latest_rev = meta.rev
            elif meta.date == latest_date and meta.rev > latest_rev:
                latest_rev = meta.rev
        return latest_date, latest_rev
