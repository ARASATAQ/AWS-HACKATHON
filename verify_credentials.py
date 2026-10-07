import boto3
from botocore.exceptions import ClientError

try:
    # Use NOVA-S profile
    session = boto3.Session(profile_name='NOVA-S')
    sts_client = session.client('sts', region_name='us-east-1')
    identity = sts_client.get_caller_identity()
    print(f"✅ AWS Credentials Valid!")
    print(f"   Account ID: {identity['Account']}")
    print(f"   ARN: {identity['Arn']}")
    print(f"   User ID: {identity['UserId']}")
except ClientError as e:
    print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
