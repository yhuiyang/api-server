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
from webapp2_extras import jinja2
from webapp2_extras.appengine import users
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

# local imports
import models


class BaseHandler(webapp2.RequestHandler):
    """ Simple base handler for Jinja2 template rendering. """

    @webapp2.cached_property
    def jinja2(self):
        """Cached property holding a Jinja2 instance.

        Returns:
            A Jinja2 object for the current app.
        """
        return jinja2.get_jinja2(app=self.app)

    def render_response(self, template, **kwargs):
        """Use Jinja2 instance to render template and write to output.

        Args:
            template: filename (relative to $PROJECT/templates) that we are
                      rendering.
            kwargs: keyword arguments corresponding to variables in template.
        """
        rendered_value = self.jinja2.render_template(template, **kwargs)
        self.response.write(rendered_value)


class Dashboard(BaseHandler):

    @users.admin_required
    def get(self):

        params = {
            'app_name': 'Dashboard'
        }
        self.render_response("dashboard.html", **params)


class CostcoCreateAndListCampaign(BaseHandler):

    @users.admin_required
    def get(self):

        allCampVer = models.CampaignVersion.get_by_id(models.COSTCO_CAMPAIGN_VERSIONS)
        if allCampVer is not None:
            ver_list = sorted(allCampVer.ver_list, reverse=True)
            campaigns = []
            for v in ver_list:
                campaign = {}
                campEntity = models.Campaign.get_by_id(str((v / 100) * 100))
                campaign['start'] = campEntity.start
                campaign['end'] = campEntity.end
                campaign['ver'] = v  # v should be equal to (id + patch), otherwise it is error
                campaign['patch'] = campEntity.patch
                campaign['published'] = campEntity.published
                campaigns.append(campaign)
        else:
            campaigns = []

        #logging.debug(campaigns)

        params = {
            'app_name': 'Costco',
            'campaigns': campaigns
        }
        self.render_response('costco_campaign_list.html', **params)

    def post(self):

        start_date = self.request.get('date-start')
        end_date = self.request.get('date-end')
        logging.debug('start: %s, end: %s' % (start_date, end_date))
        if start_date != '' and end_date != '':
            sY, sM, sD = start_date.split('-')
            eY, eM, eD = end_date.split('-')

            versionsKey = ndb.Key(models.CampaignVersion, models.COSTCO_CAMPAIGN_VERSIONS)
            versions = versionsKey.get()
            if versions is None:
                logging.debug('''Versions list doesn't exist yet''')
                versions = models.CampaignVersion(id=models.COSTCO_CAMPAIGN_VERSIONS)
                newVer = 100
            else:
                newVer = (versions.ver_list[-1] / 100 + 1) * 100

            versions.ver_list.append(newVer)
            campaign = models.Campaign(id=str(newVer))
            campaign.start = date(int(sY), int(sM), int(sD))
            campaign.end = date(int(eY), int(eM), int(eD))

            ndb.put_multi([campaign, versions])

        self.redirect_to('costco-create-and-list-campaign')


class CostcoCreateAndListCampaignProduct(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    @users.admin_required
    def get(self, camp_id):

        # find all items belongs to this campaign
        int_camp_id = int(camp_id)
        camp_key = str((int_camp_id / 100) * 100)
        campaignKey = ndb.Key(models.Campaign, camp_key)
        allItems = models.Item.query(models.Item.campaignKey == campaignKey)

        # populate product_list for later rendering
        product_list = []
        for item in allItems:
            product = {}
            for n in ['url', 'brand', 'cname', 'ename', 'model_or_spec', 'code', 'discount', 'orig_price']:
                product[n] = item.data.get(n)
            product_list.append(product)

        # the url to post to blobstore is dynamically generated, when blobstore saving completed, GAE will invoke
        # our callback which was setup in blobstore.create_upload_url(THIS_IS_APP_POST_CALLBACK_URL)
        myPostHandlerUrl = self.uri_for('costco-create-and-list-campaign-product', camp_id=camp_id)
        params = {
            'app_name': 'Costco',
            'campaign': campaignKey.get(),
            'str_btn_disable_publish': 'Click to disable publish',
            'str_btn_enable_publish': 'Click to enable publish',
            'str_confirm_disable_publish': 'Are you sure you want to disable publish state?',
            'str_confirm_enable_publish': 'Are you sure you want to enable publish state?',
            'post_url': blobstore.create_upload_url(myPostHandlerUrl),
            'products': product_list,
        }

        self.render_response('costco_campaign_product_list.html', **params)

    def post(self, camp_id):

        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]

        data_dict = {}
        # collect item image meta data
        data_dict['url'] = images.get_serving_url(blob_info.key())
        for prop in blobstore.BlobInfo.properties():
            data_dict[prop] = blob_info.get(prop)

        # collect item info
        for prop in ['brand', 'cname', 'ename', 'model_or_spec', 'code', 'discount', 'orig_price']:
            data_dict[prop] = self.request.get(prop)

        # create new item in datastore
        item = models.Item()
        item.campaignKey = ndb.Key(models.Campaign, str((int(camp_id) / 100) * 100))
        item.data = data_dict
        item.put()

        self.redirect_to('costco-create-and-list-campaign-product', camp_id=camp_id)


class CostcoCampaignEdit(BaseHandler):

    def post(self, camp_id):

        campaignKey = ndb.Key(models.Campaign, str((int(camp_id) / 100) * 100))

        # edit publish state
        update_publish = self.request.get('publish')
        if update_publish is not None and update_publish in ['true', 'false']:
            campaignEntity = campaignKey.get()
            if update_publish == 'true':
                campaignEntity.published = True
            elif update_publish == 'false':
                campaignEntity.published = False
            campaignEntity.put()

        # edit xxx...


class ApiCostcoCampaignWhatsNew(BaseHandler):

    def get(self):

        client_camp_str = self.request.get('camp_id')
        if client_camp_str == '':
            client_camp_int = 0
        else:
            client_camp_int = int(client_camp_str)

        # allCampVer holds all published campaign version number
        allCampVer = models.CampaignVersion.get_by_id(models.COSTCO_CAMPAIGN_VERSIONS)
        resp = [ver for ver in allCampVer.ver_list if ver > client_camp_int]

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(resp)


class ApiCostcoCampaignDetail(BaseHandler):

    def get(self, camp_id):

        self.response.content_type = 'application/json'

        # Check memcache first,
        cachedCampaign = getCachedCostcoCampaign(camp_id)
        if cachedCampaign is not None:
            self.response.body = cachedCampaign
            return

        # Get campaign entity
        camp_id_int = int(camp_id)
        camp_key = str((camp_id_int / 100) * 100)
        campaignKey = ndb.Key(models.Campaign, camp_key)
        campaignEntity = campaignKey.get()

        # Should we allow cache?
        # we cache:
        #   'error' (with shorter expiration)
        #       campaign doesn't exist
        #       campaign exists but version isn't matched
        #       campaign exists but not yet published
        #   'success' (with longer expiration)
        #       no above errors detected
        campaign_published = False
        error_happened = False
        if campaignEntity is not None:
            if campaignEntity.published is True:
                campaign_published = True
            elif campaignEntity.patch != (camp_id_int % 100):
                error_happened = True
        else:
            error_happened = True

        if error_happened is True or campaign_published is False:
            resp = {'error': "Campaign version doesn't exist!"}
            self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))
            setCachedCostcoCampaign(camp_id, self.response.body, 300)
            return

        # Now, the campaign is existed, version matched, and published, but not yet cached.
        resp = {
            'campaign': camp_id_int,
            'begin': campaignEntity.start.isoformat(),
            'end': campaignEntity.end.isoformat()
        }
        allItems = models.Item.query(models.Item.campaignKey == campaignKey)
        item_list = []
        for item in allItems:
            item_dict = {}
            for prop in ['url', 'brand', 'cname', 'ename', 'model_or_spec', 'code', 'discount', 'orig_price']:
                item_dict[prop] = item.data.get(prop)
            item_list.append(item_dict)
        resp['items'] = item_list
        self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))
        setCachedCostcoCampaign(camp_id, self.response.body)


def getCachedCostcoCampaign(major_version):
    return memcache.get(major_version, namespace='costco',)


def setCachedCostcoCampaign(major_version, detail, time=86400):
    memcache.set(major_version, detail, time=time, namespace='costco')


def rmCachedCostcoCampaign(major_version):
    result = memcache.delete(major_version, namespace='costco')
    if result == memcache.DELETE_NETWORK_FAILURE:
        logging.error('DELETE NETWORK FAILURE')
    elif result == memcache.DELETE_ITEM_MISSING:
        logging.warning('DELETE ITEM MISSING')
