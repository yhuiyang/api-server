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


COSTCO_CAMPAIGN_MANAGER = 'CostcoCampaignManager'


class CampaignManager(ndb.Model):  # one entity
    listPublishedVersions = ndb.IntegerProperty(repeated=True, indexed=False)
    lastCreatedVersion = ndb.IntegerProperty(default=0, indexed=False)


class PublishedCampaign(ndb.Model):
    campaign_data = ndb.JsonProperty(required=True, indexed=False)


class Campaign(ndb.Model):  # one major version, one entity, id=major version
    start = ndb.DateProperty(required=True)
    end = ndb.DateProperty(required=True)
    patch = ndb.IntegerProperty(default=0, indexed=False)
    published = ndb.BooleanProperty(default=False, indexed=False)
    modified = ndb.BooleanProperty(default=False, indexed=False)
    type = ndb.StringProperty(default='coupon', choices=['coupon', 'exhibition', 'preview', 'announcement'],
                              indexed=False)


class Item(ndb.Model):
    data = ndb.JsonProperty(required=True)
    campaignKey = ndb.KeyProperty(kind=Campaign, required=True)

    @classmethod
    def get_fields(cls, campaign_type='coupon'):
        if campaign_type == 'coupon':
            fields = ['url', 'brand', 'cname', 'ename', 'spec', 'code', 'discount', 'price']
        elif campaign_type == 'exhibition':
            fields = ['url', 'title', 'start', 'end', 'locations']
        elif campaign_type == 'preview':
            fields = ['url', 'brand', 'cname', 'ename', 'spec', 'code', 'price']
        elif campaign_type == 'announcement':
            fields = ['url', 'title', 'content']
        else:
            fields = []
        return fields
