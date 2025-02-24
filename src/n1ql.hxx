/*
 *   Copyright 2016-2022. Couchbase, Inc.
 *   All Rights Reserved.
 *
 *   Licensed under the Apache License, Version 2.0 (the "License");
 *   you may not use this file except in compliance with the License.
 *   You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 *   Unless required by applicable law or agreed to in writing, software
 *   distributed under the License is distributed on an "AS IS" BASIS,
 *   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *   See the License for the specific language governing permissions and
 *   limitations under the License.
 */

#pragma once

#include "client.hxx"
#include "result.hxx"

streamed_result*
handle_n1ql_query(PyObject* self, PyObject* args, PyObject* kwargs);

std::string
scan_consistency_type_to_string(couchbase::query_scan_consistency consistency);

couchbase::query_profile
str_to_profile_mode(std::string profile_mode);
