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


COSTCO_CAMPAIGN_VERSIONS = 'CostcoCampaignVersions'


class CampaignVersion(ndb.Model):  # one entity
    ver_list = ndb.IntegerProperty(repeated=True, indexed=False)


class Campaign(ndb.Model):  # one major version, one entity, id=major version
    start = ndb.DateProperty(required=True)
    end = ndb.DateProperty(required=True)
    patch = ndb.IntegerProperty(default=0, indexed=False)
    published = ndb.BooleanProperty(default=False, indexed=False)


class Item(ndb.Model):
    data = ndb.JsonProperty(required=True)
    campaignKey = ndb.KeyProperty(kind=Campaign, required=True)
