#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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
import os

# GAE imports
import webapp2
from webapp2_extras.routes import RedirectRoute

# local imports
import handlers


_debug = os.environ.get('SERVER_SOFTWARE').startswith('Dev')
_config = {}
_routes = [
    RedirectRoute(r'/', redirect_to='dashboard', name='home', strict_slash=True),
    RedirectRoute(r'/dashboard', handler=handlers.Dashboard, name='dashboard', strict_slash=True),
    RedirectRoute(r'/costco/campaign/<camp_id:[1-9]\d+>', handler=handlers.CostcoCreateAndListCampaignProduct,
                  name='costco-create-and-list-campaign-product', strict_slash=True),
    RedirectRoute(r'/costco/campaigns', handler=handlers.CostcoCreateAndListCampaign,
                  name='costco-create-and-list-campaign', strict_slash=True),
]

app = webapp2.WSGIApplication(routes=_routes, config=_config, debug=_debug)
