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
from webapp2_extras.appengine.users import admin_required
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import users
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

    @admin_required
    def get(self):

        params = {
            'app_name': 'Dashboard'
        }
        self.render_response("dashboard.html", **params)


class CostcoCampaignCRUD(BaseHandler):

    def getAllCampaignMajorVersionList(self):
        """
        Retrieve a unsorted list which contains campaign major version integer number.
        Query data store only if querying mem cache is missed.

        Return: python list. Ex: [1400, 800, 900]
        """
        allCampaignMajorVersionList = getCachedCostcoAllCampaignMajorVersions('list')
        if allCampaignMajorVersionList is None:
            allCampInDatastore = models.Campaign.query()
            campMajorVerList = []
            for ver in allCampInDatastore:
                campMajorVerList.append(int(ver.key.id()))

            setCachedCostcoAllCampaignMajorVersions(campMajorVerList)
        else:
            campMajorVerList = allCampaignMajorVersionList

        return campMajorVerList

    @admin_required
    def get(self):

        campMajorVerList = self.getAllCampaignMajorVersionList()
        campMajorVerList.sort(reverse=True)

        # prepare for rendering data
        campaigns = []
        for majorVerInt in campMajorVerList:
            campaign = {}
            campEntity = models.Campaign.get_by_id(str(majorVerInt))
            campaign['start'] = campEntity.start
            campaign['end'] = campEntity.end
            campaign['published'] = campEntity.published
            campaign['modified'] = campEntity.modified
            campaign['ver'] = majorVerInt + campEntity.patch
            campaign['type'] = campEntity.type
            campaign['majorVer'] = majorVerInt
            campaigns.append(campaign)

        #logging.debug(campaigns)

        params = {
            'app_name': 'Costco',
            'campaigns': campaigns
        }
        self.render_response('costco_campaign_list.html', **params)

    def post(self):

        if not users.is_current_user_admin():
            self.abort(403)

        start_date = self.request.get('date-start')
        end_date = self.request.get('date-end')
        type = self.request.get('type')

        logging.debug('start: %s, end: %s, type: %s' % (start_date, end_date, type))

        sY, sM, sD = start_date.split('-')
        eY, eM, eD = end_date.split('-')

        mgrKey = ndb.Key(models.CampaignManager, models.COSTCO_CAMPAIGN_MANAGER)
        mgrEntity = mgrKey.get()
        if mgrEntity is None:
            logging.debug('''Manager entity doesn't exist yet''')
            mgrEntity = models.CampaignManager(id=models.COSTCO_CAMPAIGN_MANAGER)
            newVer = 100
        else:
            newVer = mgrEntity.lastCreatedVersion + 100

        mgrEntity.lastCreatedVersion = newVer
        campaign = models.Campaign(id=str(newVer))
        campaign.start = date(int(sY), int(sM), int(sD))
        campaign.end = date(int(eY), int(eM), int(eD))
        campaign.type = type

        ndb.put_multi([campaign, mgrEntity])

        # update memcache
        appendCachedCostcoAllCampaignMajorVersions(newVer)

        self.redirect_to('costco-campaign-crud')


class CostcoCampaignItemCRUD(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):

    @admin_required
    def get(self, camp_id):

        # find all items belongs to this campaign
        allItems = models.Item.get_campaign_items(camp_id)

        # populate product_list for later rendering
        campaignKey = ndb.Key(models.Campaign, str((int(camp_id) / 100) * 100))
        campaignEntity = campaignKey.get()
        product_list = []
        for item in allItems:
            product = {}
            for n in models.Item.get_web_fields(campaignEntity.type):
                if n == 'urlsafe':
                    product[n] = item.key.urlsafe()
                else:
                    product[n] = item.data.get(n)
            product_list.append(product)

        # the url to post to blobstore is dynamically generated, when blobstore saving completed, GAE will invoke
        # our callback which was setup in blobstore.create_upload_url(THIS_IS_APP_POST_CALLBACK_URL)
        myPostHandlerUrl = self.uri_for('costco-campaign-item-crud', camp_id=camp_id)
        params = {
            'app_name': 'Costco',
            'campaign': campaignEntity,
            'post_url': blobstore.create_upload_url(myPostHandlerUrl),
            'products': product_list,
        }
        self.render_response('costco_campaign_product_list.html', **params)

    def post(self, camp_id):

        if not users.is_current_user_admin():
            self.abort(403)

        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        blob_key = blob_info.key()

        data_dict = dict()
        # collect item image meta data
        # blobstore.BlobInfo.properties() = set(['creation', 'content_type', 'md5_hash', 'size', 'fielname'])
        for prop in models.Item.get_blob_fields():
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
        int_camp_id = int(camp_id)
        camp_key = str((int_camp_id / 100) * 100)
        campaignEntity = models.Campaign.get_by_id(camp_key)
        for prop in models.Item.get_user_fields(campaignEntity.type):
            if prop == 'locations':
                data_dict[prop] = self.request.get_all(prop)
            else:
                data_dict[prop] = self.request.get(prop)

        # mark campaign dirty
        campaignEntity.modified = True

        # create new item in datastore
        item = models.Item(parent=campaignEntity.key)
        item.data = data_dict

        # update datastore
        ndb.put_multi([item, campaignEntity])

        self.redirect_to('costco-campaign-item-crud', camp_id=camp_id, _code=303)

    def put(self, camp_id):

        if not users.is_current_user_admin():
            self.abort(403)

        intCampMajorVer = (int(camp_id) / 100) * 100
        strCampMajorVer = str(intCampMajorVer)
        campaignKey = ndb.Key(models.Campaign, strCampMajorVer)

        # edit publish state
        request_publish = self.request.get('publish')
        if request_publish is not None and request_publish in ['true', 'false']:
            campaignEntity = campaignKey.get()
            intCampVer = intCampMajorVer + campaignEntity.patch

            if request_publish == 'true':  # do publish

                patchAdvance = True

                # check if modification happened
                if campaignEntity.modified is False:
                    logging.warning('Request publish a non-modification campaign, patch will not be advanced!')
                    patchAdvance = False

                # retrieve campaign manager
                campMgrEntity = models.CampaignManager.get_or_insert(models.COSTCO_CAMPAIGN_MANAGER)

                # check if still in published state
                if campaignEntity.published is True:
                    try:
                        campMgrEntity.listPublishedVersions.remove(intCampVer)
                    except ValueError:
                        logging.error('Remove non-exist version(%d) from published version list.' % intCampVer)

                # update campaign fields
                if patchAdvance:
                    campaignEntity.patch += 1
                campaignEntity.modified = False
                campaignEntity.published = True

                # new campaign version number
                intCampVer = intCampMajorVer + campaignEntity.patch

                # populate this campaign data and create new one published campaign entity for it
                camp_data = dict()
                camp_data['start'] = campaignEntity.start.isoformat()
                camp_data['end'] = campaignEntity.end.isoformat()
                camp_data['type'] = campaignEntity.type
                camp_data['items'] = []
                allCampItems = models.Item.get_campaign_items(camp_id)
                for item in allCampItems:
                    item_published_data = dict()
                    for prop in models.Item.get_published_fields(campaignEntity.type):
                        item_published_data[prop] = item.data[prop]
                    camp_data['items'].append(item_published_data)

                publishedCampEntity = models.PublishedCampaign(id=str(intCampVer))
                publishedCampEntity.campaign_data = camp_data

                # append campaign version number into published campaign version list
                campMgrEntity.listPublishedVersions.append(intCampVer)

                # update data store
                ndb.put_multi([campMgrEntity, campaignEntity, publishedCampEntity])

            elif request_publish == 'false':  # do un-publish

                # check if already published
                if campaignEntity.published is False:
                    logging.warning('Request un-publish a not-yet-published campaign, skip action!')
                    self.abort(406)  # not acceptable

                # retrieve campaign manager
                campMgrEntity = models.CampaignManager.get_or_insert(models.COSTCO_CAMPAIGN_MANAGER)

                try:
                    campMgrEntity.listPublishedVersions.remove(intCampVer)
                except ValueError:
                    logging.error("Campaign is marked published, but doesn't exist in published campaign list!")

                # update campaign fields
                campaignEntity.published = False

                # update data store
                ndb.put_multi([campMgrEntity, campaignEntity])

        # edit xxx...

    def delete(self, camp_id):

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
            intCampId = int(camp_id)
            keyCampId = str((intCampId / 100) * 100)
            campaignEntity = models.Campaign.get_by_id(keyCampId)
            # mark campaign dirty
            if campaignEntity is not None:
                campaignEntity.modified = True
                campaignEntity.put()
                # self.redirect_to('costco-campaign-item-crud', camp_id=camp_id, _code=303)  # move redirect to client


class ApiCostcoWhatsNew(BaseHandler):

    def get(self):

        client_camp_str = self.request.get('camp_id')
        if client_camp_str == '':
            client_camp_int = 0
        else:
            client_camp_int = int(client_camp_str)

        # CampaignManager holds published campaign version number list
        campMgrEntity = models.CampaignManager.get_or_insert(models.COSTCO_CAMPAIGN_MANAGER)
        resp = [ver for ver in campMgrEntity.listPublishedVersions if ver > client_camp_int]
        resp.sort(reverse=True)

        self.response.content_type = 'application/json'
        self.response.body = json.dumps(resp)


class ApiCostcoCampaignDetail(BaseHandler):

    def get(self, camp_id):

        self.response.content_type = 'application/json'

        strCampVer = camp_id
        intCampVer = int(camp_id)

        # check if this is published campaign
        campMgrEntity = models.CampaignManager.get_or_insert(models.COSTCO_CAMPAIGN_MANAGER)
        if intCampVer not in campMgrEntity.listPublishedVersions:
            resp = {'error': 'Requested campaign is not yet published!'}
            self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))
            return

        publishedCampEntity = models.PublishedCampaign.get_by_id(strCampVer)
        if publishedCampEntity is None:
            logging.error('There is version number in published version list, but not published campaign entity!')
            resp = {'error': 'Internal error!'}
        else:
            resp = publishedCampEntity.campaign_data
        self.response.body = json.dumps(resp, indent=None, separators=(',', ':'))


def getCachedCostcoAllCampaignMajorVersions(requestType='str'):
    """
    Return a json string (requestType='str') or python list (requestType='list') which contains a array or list of
    campaign major version number.
    Ex:
        Json string => '[ 600, 500, 300 ]' or
        Python list => [ 600, 500, 300 ]
    """
    assert requestType in ['str', 'list'], "Unknown request type, only accept 'str' or 'list'."

    verJsonStr = memcache.get('all-costco-campaign-major-version-list', namespace='costco')

    if verJsonStr is None or len(verJsonStr) == 2:
        return None

    if requestType == 'str':
        return verJsonStr
    elif requestType == 'list':
        return json.loads(verJsonStr)


def setCachedCostcoAllCampaignMajorVersions(verList_or_verStr):
    """
    Save a json string or python list which contains campaign major version number.
    """
    verJsonStr = None

    if isinstance(verList_or_verStr, list):
        verJsonStr = json.dumps(verList_or_verStr)
    elif isinstance(verList_or_verStr, str):
        verJsonStr = verList_or_verStr

    verList = json.loads(verJsonStr)
    assert len(verList) == 0 or isinstance(verList[0], int), 'Version is required to be integer number.'

    if verJsonStr is not None and len(verJsonStr) > 2:
        memcache.set('all-costco-campaign-major-version-list', verJsonStr, time=1440, namespace='costco')


def appendCachedCostcoAllCampaignMajorVersions(intMajorVersion):
    """
    Append one int major version into memcache.
    """
    list = getCachedCostcoAllCampaignMajorVersions('list')
    if list is None:
        list = []
    list.append(intMajorVersion)
    setCachedCostcoAllCampaignMajorVersions(list)
