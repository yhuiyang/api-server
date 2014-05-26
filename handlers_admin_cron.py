#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014, YH Yang <yhuiyang@gmail.com>
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
import re
from HTMLParser import HTMLParser
from datetime import date

# GAE imports
import webapp2
from webapp2_extras.routes import RedirectRoute
from google.appengine.api import urlfetch

# local imports


###########################################################################
# 80 Plus
###########################################################################
class Web80PlusManufacturesBriefParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

        # final manufactures brief result
        self.result_dict = dict()
        self.result_dict['115v'] = list()
        self.result_dict['230v'] = list()

        # date field
        self.date_found = False
        self.date_parsed = False

        # manufacturer
        self.manufacture115_found = False
        self.manufacture230_found = False
        self.manufacture = None
        self.link_found = False
        self.name_found = False
        self.transparent_found = False
        self.bronze_found = False
        self.silver_found = False
        self.gold_found = False
        self.platinum_found = False
        self.titanium_found = False
        self.total_found = False

        # debug stuff
        self.handle_start_called = 0
        self.handle_end_called = 0
        self.handle_data_called = 0

    def handle_data(self, data):

        self.handle_data_called += 1

        if self.date_found:
            #logging.info(data)
            if not self.date_parsed:
                match = re.search(r"(\d+)/(\d+)/(\d+)", data)
                if match:
                    try:
                        year = match.group(3)
                        month = match.group(1)
                        day = match.group(2)
                        self.result_dict['date'] = date(int(year), int(month), int(day))
                        self.date_parsed = True
                    except TypeError:  # year, month, or day missing
                        self.date_parsed = False
            else:
                logging.warn('Found multiple date, fix the find parameters ASAP.')

        elif self.name_found:
            self.manufacture['name'] = data

        elif self.transparent_found:
            self.manufacture['transparent'] = int(data)

        elif self.bronze_found:
            self.manufacture['bronze'] = int(data)

        elif self.silver_found:
            self.manufacture['silver'] = int(data)

        elif self.gold_found:
            self.manufacture['gold'] = int(data)

        elif self.platinum_found:
            self.manufacture['platinum'] = int(data)

        elif self.titanium_found:
            self.manufacture['titanium'] = int(data)

        elif self.total_found:
            self.manufacture['total'] = int(data)

    def handle_endtag(self, tag):

        self.handle_end_called += 1

        if tag == 'span':
            if self.date_found:
                self.date_found = False
        elif tag == 'tr':
            if self.manufacture115_found or self.manufacture230_found:
                # data should be inserted into self.manufacture already, append to result_dict
                if self.manufacture115_found:
                    self.result_dict['115v'].append(self.manufacture)
                elif self.manufacture230_found:
                    self.result_dict['230v'].append(self.manufacture)
                self.manufacture = None
                self.manufacture115_found = False
                self.manufacture230_found = False
        elif tag == 'td':
            if self.manufacture115_found or self.manufacture230_found:
                if self.link_found:
                    self.link_found = False
                elif self.transparent_found:
                    self.transparent_found = False
                elif self.bronze_found:
                    self.bronze_found = False
                elif self.silver_found:
                    self.silver_found = False
                elif self.gold_found:
                    self.gold_found = False
                elif self.platinum_found:
                    self.platinum_found = False
                elif self.titanium_found:
                    self.titanium_found = False
                elif self.total_found:
                    self.total_found = False
        elif tag == 'a':
            if self.manufacture115_found or self.manufacture230_found:
                if self.link_found and self.name_found:
                    self.name_found = False

    def handle_starttag(self, tag, attrs):

        self.handle_start_called += 1

        #
        # date format
        #
        # <span id="ctl00_body_lastUpdateDateLabel" class="alert">
        #   *The list of PSUs above is current as of: 1/10/2014
        # </span>
        #
        if tag == 'span':
            if ('class', 'alert') in attrs and ('id', 'ctl00_body_lastUpdateDateLabel') in attrs:
                self.date_found = True
        #
        # single manufacture brief format (style attr is removed for simplicity)
        #
        # <tr id="ctl00_body_ASPxPageControl1_ASPxGridView1_DXDataRow0" class="dxgvDataRow_manu">
        #   <td class="borderOddTD dxgv borderEvenTD">
        #     <a class="dxeHyperlink" href="80PlusPowerSuppliesDetail.aspx?id=277&amp;type=2">1st Player</a>
        #   </td>
        #   <td class="transparentOddTD dxgv transparentEvenTD">1</td>
        #   <td class="bronzeOddTD dxgv bronzeEvenTD">3</td>
        #   <td class="silverOddTD dxgv silverEvenTD">2</td>
        #   <td class="goldOddTD dxgv goldEvenTD">0</td>
        #   <td class="platinumOddTD dxgv platinumEvenTD">0</td>
        #   <td class="titaniumOddTD dxgv titaniumEvenTD">0</td>
        #   <td class="totalOddTD dxgv totalEvenTD">6</td>
        # </tr>
        #
        elif tag == 'tr':
            if ('class', 'dxgvDataRow_manu') in attrs:
                for attr in attrs:
                    if attr[0] == 'id' and attr[1].startswith('ctl00_body_ASPxPageControl1_ASPxGridView1_DXDataRow'):
                        self.manufacture115_found = True
                        # prepare an empty manufacture dict for data insertion later
                        self.manufacture = dict()
                        break
                    elif attr[0] == 'id' and attr[1].startswith('ctl00_body_ASPxPageControl1_ASPxGridView2_DXDataRow'):
                        self.manufacture230_found = True
                        self.manufacture = dict()
                        break
        elif tag == 'td' and (self.manufacture115_found or self.manufacture230_found):
            for attr in attrs:
                if attr[0] == 'class':
                    if attr[1].startswith('borderOddTD'):
                        self.link_found = True
                    elif attr[1].startswith('transparentOddTD'):
                        self.transparent_found = True
                    elif attr[1].startswith('bronzeOddTD'):
                        self.bronze_found = True
                    elif attr[1].startswith('silverOddTD'):
                        self.silver_found = True
                    elif attr[1].startswith('goldOddTD'):
                        self.gold_found = True
                    elif attr[1].startswith('platinumOddTD'):
                        self.platinum_found = True
                    elif attr[1].startswith('titaniumOddTD'):
                        self.titanium_found = True
                    elif attr[1].startswith('totalOddTD'):
                        self.total_found = True
                    break
        elif tag == 'a' and self.link_found:
            self.name_found = True
            for attr in attrs:
                if attr[0] == 'href':
                    self.manufacture['link'] = attr[1]
                    break


class Cron80Plus(webapp2.RequestHandler):
    def get(self):

        try:
            result = urlfetch.fetch('http://www.80plus.org/', follow_redirects=True, deadline=60)
            #logging.info(result.headers)
            #logging.info('status code: %d' % result.status_code)
            if result.status_code == 200:
                self.parse_content(result.content)
        except urlfetch.DownloadError:
            logging.error('Urlfetch timeout!!!')

    def parse_content(self, content):
        parser = Web80PlusManufacturesBriefParser()
        parser.feed(content)
        #logging.info(parser.result_dict)
        logging.info('%d %d' % (len(parser.result_dict['115v']), len(parser.result_dict['230v'])))


###########################################################################
# Routes
###########################################################################
routes = [
    RedirectRoute(r'/cron/80plus', handler=Cron80Plus, name='cron-80plus', strict_slash=True),
]
