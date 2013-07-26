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

    @classmethod
    def get_campaign_items(cls, camp_version):
        if isinstance(camp_version, str):
            intCampVersion = int(camp_version)
            intCampMajorVer = (intCampVersion / 100) * 100
        elif isinstance(camp_version, int):
            intCampMajorVer = (camp_version / 100) * 100
        else:
            return None

        return Item.query(ancestor=ndb.Key(Campaign, str(intCampMajorVer)))

    @classmethod
    def get_user_fields(cls, campaign_type='coupon'):
        """
        Fields provided by user input
        """
        if campaign_type == 'coupon':
            fields = ['brand', 'cname', 'ename', 'spec', 'code', 'discount', 'price']
        elif campaign_type == 'exhibition':
            fields = ['title', 'start', 'end', 'locations']
        elif campaign_type == 'preview':
            fields = ['brand', 'cname', 'ename', 'spec', 'code', 'price']
        elif campaign_type == 'announcement':
            fields = ['title', 'content']
        else:
            fields = []
        return fields

    @classmethod
    def get_blob_fields(cls):
        """
        Fields provided by blobstore and image service
        """
        fields = ['url', 'creation', 'content_type', 'md5_hash', 'size', 'filename', 'blob_key']
        return fields

    @classmethod
    def get_web_fields(cls, campaign_type='coupon'):
        """
        Fields used on web management page
        """
        if campaign_type == 'coupon':
            fields = ['url', 'blob_key', 'urlsafe', 'brand', 'cname', 'ename', 'spec', 'code', 'discount', 'price']
        elif campaign_type == 'exhibition':
            fields = ['url', 'blob_key', 'urlsafe', 'title', 'start', 'end', 'locations']
        elif campaign_type == 'preview':
            fields = ['url', 'blob_key', 'urlsafe', 'brand', 'cname', 'ename', 'spec', 'code', 'price']
        elif campaign_type == 'announcement':
            fields = ['url', 'blob_key', 'urlsafe', 'title', 'content']
        else:
            fields = []
        return fields

    @classmethod
    def get_published_fields(cls, campaign_type='coupon'):
        """
        Fields used by the app client
        """
        if campaign_type == 'coupon':
            fields = ['url', 'filename', 'brand', 'cname', 'ename', 'spec', 'code', 'discount', 'price']
        elif campaign_type == 'exhibition':
            fields = ['url', 'filename', 'title', 'start', 'end', 'locations']
        elif campaign_type == 'preview':
            fields = ['url', 'filename', 'brand', 'cname', 'ename', 'spec', 'code', 'price']
        elif campaign_type == 'announcement':
            fields = ['url', 'filename', 'title', 'content']
        else:
            fields = []
        return fields
