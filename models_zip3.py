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


class Township(ndb.Model):
    name = ndb.StringProperty(required=True)
    zip_string = ndb.StringProperty(required=True)
    zip_int = ndb.ComputedProperty(lambda self: int(self.zip_string))


class County(ndb.Model):
    township_list = ndb.LocalStructuredProperty(Township, repeated=True)

    @classmethod
    def getInstance(cls, key_id_string):
        return cls.get_or_insert(key_id_string, township_list=list())


class Zip3Manager(ndb.Model):
    url = ndb.StringProperty(indexed=False)
    county_key_list = ndb.KeyProperty(kind=County, repeated=True)

    @classmethod
    def getInstance(cls):
        return cls.get_or_insert('Zip3Manager', url='', county_key_list=list())
