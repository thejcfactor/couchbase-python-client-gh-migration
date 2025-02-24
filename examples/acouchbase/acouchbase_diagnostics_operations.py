from datetime import timedelta

from acouchbase.cluster import Cluster, get_event_loop
from couchbase.auth import PasswordAuthenticator

# **DEPRECATED**, use: from couchbase.options import PingOptions
from couchbase.bucket import PingOptions
from couchbase.diagnostics import PingState, ServiceType
from couchbase.exceptions import UnAmbiguousTimeoutException
from couchbase.options import WaitUntilReadyOptions


async def ok(cluster):
    result = await cluster.ping()
    for _, reports in result.endpoints.items():
        for report in reports:
            if not report.state == PingState.OK:
                return False
    return True


async def main():
    cluster = Cluster(
        "couchbase://localhost",
        authenticator=PasswordAuthenticator(
            "Administrator",
            "password"))
    await cluster.on_connect()

    cluster_ready = False
    try:
        await cluster.wait_until_ready(timedelta(seconds=3),
                                       WaitUntilReadyOptions(service_types=[ServiceType.KeyValue, ServiceType.Query]))
        cluster_ready = True
    except UnAmbiguousTimeoutException as ex:
        print('Cluster not ready in time: {}'.format(ex))

    if cluster_ready is False:
        quit()

    # For Server versions 6.5 or later you do not need to open a bucket here
    bucket = cluster.bucket("beer-sample")
    await bucket.on_connect()
    collection = bucket.default_collection()

    ping_result = await cluster.ping()

    for endpoint, reports in ping_result.endpoints.items():
        for report in reports:
            print(
                "{0}: {1} took {2}".format(
                    endpoint.value,
                    report.remote,
                    report.latency))

    ping_result = await cluster.ping()
    print(ping_result.as_json())

    print("Cluster is okay? {}".format(await ok(cluster)))

    ping_result = await cluster.ping(PingOptions(service_types=[ServiceType.Query]))
    print(ping_result.as_json())

    diag_result = await cluster.diagnostics()
    print(diag_result.as_json())

    print("Cluster state: {}".format(diag_result.state))

if __name__ == "__main__":
    loop = get_event_loop()
    loop.run_until_complete(main())
