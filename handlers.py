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
import webapp2
from webapp2_extras import jinja2
from webapp2_extras.appengine import users

# local imports


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
