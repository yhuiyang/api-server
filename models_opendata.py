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
# Police Stations
###########################################################################
class PoliceStationRawData(ndb.Model):

    STATE_UNPARSED = 'unparsed'
    STATE_PROCESSING = 'processing'
    STATE_PARSED = 'parsed'

    date = ndb.DateProperty(indexed=False, required=True)
    blob_key = ndb.BlobKeyProperty(indexed=False, required=True)
    state = ndb.IntegerProperty(indexed=False, default=0)
    published = ndb.BooleanProperty(indexed=False, default=False)

    def get_state(self):
        if self.state == 0:
            return self.STATE_UNPARSED
        elif self.state == 1:
            return self.STATE_PROCESSING
        else:
            return self.STATE_PARSED

    def set_state(self, state):
        if state == self.STATE_UNPARSED:
            self.state = 0
        elif state == self.STATE_PROCESSING:
            self.state = 1
        else:
            self.state = 2


class PoliceStation(ndb.Model):
    name = ndb.StringProperty(indexed=False, required=True)
    tel = ndb.StringProperty(indexed=False)
    address = ndb.StringProperty(indexed=False)
    xy = ndb.FloatProperty(indexed=False, repeated=True)
    latlng = ndb.GeoPtProperty(indexed=False)

    @classmethod
    def query_entities(cls, data_date):  # data_date is str like '2013-9-19'. It can get from date.isoformat().
        return cls.query(ancestor=ndb.Key(PoliceStation, data_date))


class PublishedPoliceStations(ndb.Model):
    list = ndb.JsonProperty(indexed=False, required=True)


class PoliceStationManager(ndb.Model):
    published_data_date = ndb.DateProperty(indexed=False, repeated=True)

    @classmethod
    def getInstance(cls):
        return cls.get_or_insert('PoliceStationMgr', published_data_date=list())
