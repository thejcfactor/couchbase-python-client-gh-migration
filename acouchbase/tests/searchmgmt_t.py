#  Copyright 2016-2022. Couchbase, Inc.
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import json
import pathlib
from os import path

import pytest
import pytest_asyncio

from acouchbase.cluster import get_event_loop
from couchbase.exceptions import (FeatureUnavailableException,
                                  InvalidArgumentException,
                                  QueryIndexAlreadyExistsException,
                                  SearchIndexNotFoundException)
from couchbase.management.search import SearchIndex

from ._test_utils import CollectionType, TestEnvironment


@pytest.mark.flaky(reruns=5)
class SearchIndexManagementTests:

    IDX_NAME = 'test-fts-index'

    @pytest_asyncio.fixture(scope="class")
    def event_loop(self):
        loop = get_event_loop()
        yield loop
        loop.close()

    @pytest_asyncio.fixture(scope="class", name="cb_env")
    async def couchbase_test_environment(self, couchbase_config):
        cb_env = await TestEnvironment.get_environment(__name__,
                                                       couchbase_config,
                                                       manage_buckets=True,
                                                       manage_search_indexes=True)

        yield cb_env

    @pytest.fixture(scope="class")
    def check_search_index_mgmt_supported(self, cb_env):
        cb_env.check_if_feature_supported('search_index_mgmt')

    @pytest.fixture(scope="class", name='test_idx')
    def get_test_index(self):
        return SearchIndex(name=self.IDX_NAME, source_name='default')

    @pytest_asyncio.fixture()
    async def create_test_index(self, cb_env, test_idx):
        await cb_env.try_n_times_till_exception(10, 3,
                                                cb_env.sixm.upsert_index,
                                                test_idx,
                                                expected_exceptions=(QueryIndexAlreadyExistsException, ))

    @pytest_asyncio.fixture()
    async def drop_test_index(self, cb_env, test_idx):
        yield
        await cb_env.try_n_times_till_exception(10, 3,
                                                cb_env.sixm.drop_index,
                                                test_idx.name,
                                                expected_exceptions=(SearchIndexNotFoundException, ))

    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_upsert_index(self, cb_env, test_idx):
        res = await cb_env.sixm.upsert_index(test_idx)
        assert res is None
        res = await cb_env.try_n_times(10, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_drop_index(self, cb_env, test_idx):
        res = await cb_env.try_n_times(3, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)
        await cb_env.sixm.drop_index(test_idx.name)
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.drop_index(test_idx.name)

    @pytest.mark.asyncio
    async def test_drop_index_fail(self, cb_env, test_idx):
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.drop_index(test_idx.name)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index(self, cb_env, test_idx):
        res = await cb_env.try_n_times(3, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)
        assert res.name == test_idx.name

    @pytest.mark.asyncio
    async def test_get_index_fail_no_index_name(self, cb_env):
        with pytest.raises(InvalidArgumentException):
            await cb_env.sixm.get_index('')
        with pytest.raises(InvalidArgumentException):
            await cb_env.sixm.get_index(None)

    @pytest.mark.asyncio
    async def test_get_index_fail(self, cb_env):
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.get_index('not-an-index')

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_all_indexes(self, cb_env, test_idx):
        # lets add one more
        new_idx = SearchIndex(name='new-search-idx', source_name='default')
        res = await cb_env.sixm.upsert_index(new_idx)
        assert res is None
        res = await cb_env.try_n_times(10, 3, cb_env.sixm.get_index, new_idx.name)
        assert isinstance(res, SearchIndex)

        indexes = await cb_env.sixm.get_all_indexes()
        assert isinstance(indexes, list)
        assert len(indexes) >= 2
        assert next((idx for idx in indexes if idx.name == test_idx.name), None) is not None
        assert next((idx for idx in indexes if idx.name == new_idx.name), None) is not None

        await cb_env.sixm.drop_index(new_idx.name)
        await cb_env.try_n_times_till_exception(10,
                                                3,
                                                cb_env.sixm.get_index,
                                                new_idx.name,
                                                expected_exceptions=(SearchIndexNotFoundException,))

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_analyze_doc(self, cb_env, test_idx):
        if cb_env.server_version_short < 6.5:
            pytest.skip((f'FTS analyzeDoc only supported on server versions >= 6.5. '
                        f'Using server version: {cb_env.server_version}.'))
        # like getting the doc count, this can fail immediately after index
        # creation
        doc = {"field": "I got text in here"}
        analysis = await cb_env.try_n_times(
            5, 2, cb_env.sixm.analyze_document, test_idx.name, doc)

        assert analysis.get('analysis', None) is not None
        assert isinstance(analysis.get('analysis'), (list, dict))
        assert analysis.get('status', None) == 'ok'

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_ingestion_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.pause_ingest,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.resume_ingest,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_query_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.disallow_querying,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.allow_querying,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_plan_freeze_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.freeze_plan,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.unfreeze_plan,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index_stats(self, cb_env, test_idx):
        # like getting the doc count, this can fail immediately after index
        # creation
        stats = await cb_env.try_n_times(
            5, 2, cb_env.sixm.get_index_stats, test_idx.name)

        assert stats is not None
        assert isinstance(stats, dict)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index_doc_count(self, cb_env, test_idx):
        # like getting the doc count, this can fail immediately after index
        # creation
        doc_count = await cb_env.try_n_times(
            5, 2, cb_env.sixm.get_indexed_documents_count, test_idx.name)

        assert doc_count is not None
        assert isinstance(doc_count, int)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_all_index_stats(self, cb_env, test_idx):
        # like getting the doc count, this can fail immediately after index
        # creation
        stats = await cb_env.try_n_times(
            5, 2, cb_env.sixm.get_all_index_stats)

        assert stats is not None
        assert isinstance(stats, dict)


@pytest.mark.flaky(reruns=5)
class ScopeSearchIndexManagementTests:

    IDX_NAME = 'test-fts-index'
    TEST_COLLECTION_INDEX_NAME = 'test-search-coll-index'
    TEST_COLLECTION_INDEX_PATH = path.join(pathlib.Path(__file__).parent.parent.parent,
                                           'tests',
                                           'test_cases',
                                           f'{TEST_COLLECTION_INDEX_NAME}-params-new.json')

    @pytest_asyncio.fixture(scope="class")
    def event_loop(self):
        loop = get_event_loop()
        yield loop
        loop.close()

    @pytest_asyncio.fixture(scope="class", name="cb_env")
    async def couchbase_test_environment(self, couchbase_config):
        cb_env = await TestEnvironment.get_environment(__name__,
                                                       couchbase_config,
                                                       CollectionType.NAMED,
                                                       manage_buckets=True)

        await cb_env.try_n_times(5, 3, cb_env.setup_named_collections)
        cb_env.enable_scope_search_mgmt().enable_search_mgmt()
        yield cb_env
        cb_env.disable_search_mgmt().disable_scope_search_mgmt()
        await cb_env.try_n_times_till_exception(5, 3,
                                                cb_env.teardown_named_collections,
                                                raise_if_no_exception=False)

    @pytest.fixture(scope="class")
    def check_search_index_mgmt_supported(self, cb_env):
        cb_env.check_if_feature_supported('search_index_mgmt')
        cb_env.check_if_feature_supported('scope_search_index_mgmt')

    @pytest.fixture(scope="class", name='test_idx')
    def get_test_index(self):
        params_json = {}
        with open(self.TEST_COLLECTION_INDEX_PATH) as params_file:
            input = params_file.read()
            params_json = json.loads(input)
            mapping_types = params_json.get('mapping', {}).get('types', {})
            if mapping_types and 'test-scope.other-collection' in mapping_types:
                del params_json['mapping']['types']['test-scope.other-collection']
        return SearchIndex(name=self.IDX_NAME, source_name='default', params=params_json)

    @pytest_asyncio.fixture()
    async def create_test_index(self, cb_env, test_idx):

        await cb_env.try_n_times_till_exception(10, 3,
                                                cb_env.sixm.upsert_index,
                                                test_idx,
                                                expected_exceptions=(QueryIndexAlreadyExistsException, ))

    @pytest_asyncio.fixture()
    async def drop_test_index(self, cb_env, test_idx):
        yield
        await cb_env.try_n_times_till_exception(10, 3,
                                                cb_env.sixm.drop_index,
                                                test_idx.name,
                                                expected_exceptions=(SearchIndexNotFoundException, ))

    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_upsert_index(self, cb_env, test_idx):
        res = await cb_env.sixm.upsert_index(test_idx)
        assert res is None
        res = await cb_env.try_n_times(10, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_drop_index(self, cb_env, test_idx):
        res = await cb_env.try_n_times(3, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)
        await cb_env.sixm.drop_index(test_idx.name)
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.drop_index(test_idx.name)

    @pytest.mark.asyncio
    async def test_drop_index_fail(self, cb_env, test_idx):
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.drop_index(test_idx.name)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index(self, cb_env, test_idx):
        res = await cb_env.try_n_times(3, 3, cb_env.sixm.get_index, test_idx.name)
        assert isinstance(res, SearchIndex)
        assert res.name == test_idx.name

    @pytest.mark.asyncio
    async def test_get_index_fail_no_index_name(self, cb_env):
        with pytest.raises(InvalidArgumentException):
            await cb_env.sixm.get_index('')
        with pytest.raises(InvalidArgumentException):
            await cb_env.sixm.get_index(None)

    @pytest.mark.asyncio
    async def test_get_index_fail(self, cb_env):
        with pytest.raises(SearchIndexNotFoundException):
            await cb_env.sixm.get_index('not-an-index')

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_all_indexes(self, cb_env, test_idx):
        # lets add one more
        new_idx = SearchIndex(name='new-search-idx', source_name='default')
        res = await cb_env.sixm.upsert_index(new_idx)
        assert res is None
        res = await cb_env.try_n_times(10, 3, cb_env.sixm.get_index, new_idx.name)
        assert isinstance(res, SearchIndex)

        indexes = await cb_env.sixm.get_all_indexes()
        assert isinstance(indexes, list)
        assert len(indexes) >= 2
        assert next((idx for idx in indexes if idx.name == test_idx.name), None) is not None
        assert next((idx for idx in indexes if idx.name == new_idx.name), None) is not None

        await cb_env.sixm.drop_index(new_idx.name)
        await cb_env.try_n_times_till_exception(10,
                                                3,
                                                cb_env.sixm.get_index,
                                                new_idx.name,
                                                expected_exceptions=(SearchIndexNotFoundException,))

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_analyze_doc(self, cb_env, test_idx):
        if cb_env.server_version_short < 6.5:
            pytest.skip((f'FTS analyzeDoc only supported on server versions >= 6.5. '
                        f'Using server version: {cb_env.server_version}.'))
        with pytest.raises(FeatureUnavailableException):
            await cb_env.sixm.analyze_document(test_idx.name, {"field": "I got text in here"})

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_ingestion_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.pause_ingest,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.resume_ingest,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_query_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.disallow_querying,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.allow_querying,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_plan_freeze_control(self, cb_env, test_idx):
        # can't easily test this, but lets at least call them and insure we get no
        # exceptions
        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.freeze_plan,
            test_idx.name)
        assert res is None

        res = await cb_env.try_n_times(
            10,
            3,
            cb_env.sixm.unfreeze_plan,
            test_idx.name)
        assert res is None

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index_stats(self, cb_env, test_idx):
        with pytest.raises(FeatureUnavailableException):
            await cb_env.sixm.get_index_stats(test_idx.name)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_index_doc_count(self, cb_env, test_idx):
        # like getting the doc count, this can fail immediately after index
        # creation
        doc_count = await cb_env.try_n_times(
            5, 2, cb_env.sixm.get_indexed_documents_count, test_idx.name)

        assert doc_count is not None
        assert isinstance(doc_count, int)

    @pytest.mark.usefixtures("create_test_index")
    @pytest.mark.usefixtures("drop_test_index")
    @pytest.mark.asyncio
    async def test_get_all_index_stats(self, cb_env, test_idx):
        # like getting the doc count, this can fail immediately after index
        # creation
        stats = await cb_env.try_n_times(
            5, 2, cb_env.sixm.get_all_index_stats)

        assert stats is not None
        assert isinstance(stats, dict)
