from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster

# **DEPRECATED**, import ALL management options from `couchbase.management.options`
# from couchbase.management.queries import CreatePrimaryQueryIndexOptions
from couchbase.management.options import CreatePrimaryQueryIndexOptions
from couchbase.management.users import Role, User

bucket_name = "travel-sample"
username = "test-user"
pw = "test-passw0rd!"

adm_cluster = Cluster(
    "couchbase://localhost",
    authenticator=PasswordAuthenticator(
        "Administrator",
        "password"))
# For Server versions 6.5 or later you do not need to open a bucket here
adm_bucket = adm_cluster.bucket(bucket_name)

user_manager = adm_cluster.users()
user = User(username=username, display_name="Test User",
            roles=[
                # Roles required for reading data from bucket
                Role(name="data_reader", bucket="*"),
                Role(name="query_select", bucket="*"),
                # Roles require for writing data to bucket
                Role(name="data_writer", bucket=bucket_name),
                Role(name="query_insert", bucket=bucket_name),
                Role(name="query_delete", bucket=bucket_name),
                # Role required for idx creation on bucket
                Role(name="query_manage_index", bucket=bucket_name),
            ], password=pw)

user_manager.upsert_user(user)

users_metadata = user_manager.get_all_users()
for u in users_metadata:
    print("User's display name: {}".format(u.user.display_name))
    roles = u.user.roles
    for r in roles:
        print(
            "\tUser has role {}, applicable to bucket {}".format(
                r.name, r.bucket))

user_cluster = Cluster(
    "couchbase://localhost",
    authenticator=PasswordAuthenticator(username, pw))

# For Server versions 6.5 or later you do not need to open a bucket here
user_bucket = user_cluster.bucket(bucket_name)
collection = user_bucket.default_collection()

# create primary idx for testing purposes
user_cluster.query_indexes().create_primary_index(
    bucket_name, CreatePrimaryQueryIndexOptions(
        ignore_if_exists=True))

# test k/v operations
airline_10 = collection.get("airline_10")
print("Airline 10: {}".format(airline_10.content_as[dict]))

airline_11 = {
    "callsign": "MILE-AIR",
                "iata": "Q5",
                "id": 11,
                "name": "40-Mile Air",
                "type": "airline",
}

collection.upsert("airline_11", airline_11)

query_res = user_cluster.query("SELECT * FROM `travel-sample` LIMIT 5;")
for row in query_res.rows():
    print("Query row: {}".format(row))

# drop the user
user_manager.drop_user(user.username)
