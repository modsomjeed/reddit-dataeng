import pytest


class FakeS3:
    """In-memory stand-in for the boto3 S3 client, covering the calls the scripts make."""

    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects = dict(objects or {})
        self.buckets = {"reddit-raw"}

    def head_bucket(self, Bucket):
        if Bucket not in self.buckets:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, Bucket):
        self.buckets.add(Bucket)

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = Body

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):
        with open(Filename, "rb") as f:
            self.objects[Key] = f.read()

    def download_file(self, Bucket, Key, Filename):
        with open(Filename, "wb") as f:
            f.write(self.objects[Key])

    def get_paginator(self, name):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix=""):
                keys = sorted(k for k in objects if k.startswith(Prefix))
                yield {"Contents": [{"Key": k, "Size": len(objects[k])} for k in keys]}

        return Paginator()


@pytest.fixture
def fake_s3():
    return FakeS3()
