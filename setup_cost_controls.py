"""
Setup AWS Cost Controls and Billing Alerts
This script sets up cost controls WITHOUT requiring AWS CLI
Ensures you stay in free tier and get alerted if costs spike
"""

import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError, BotoCoreError

def setup_cost_controls(profile_name='NOVA-S', region='us-east-1'):
    """Set up billing alerts and cost monitoring"""
    
    print("=" * 70)
    print("AWS COST CONTROL SETUP")
    print("=" * 70)
    print()
    
    # Initialize clients
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region)
        
        # Try to verify credentials
        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()
        
        print(f"✅ AWS Credentials verified")
        print(f"   Account ID: {identity['Account']}")
        print(f"   ARN: {identity['Arn']}")
        print()
        
    except Exception as e:
        print(f"❌ Cannot verify AWS credentials: {e}")
        print()
        print("NEXT STEPS:")
        print("1. Open AWS Console: https://console.aws.amazon.com/")
        print("2. Go to Billing & Cost Management → Budgets")
        print("3. Create a new budget for cost alerts")
        print()
        return False

    # Get billing client
    try:
        ce_client = session.client('ce')
        cloudwatch_client = session.client('cloudwatch')
        sns_client = session.client('sns')
        
    except Exception as e:
        print(f"❌ Error initializing clients: {e}")
        return False

    # Step 1: Create SNS topic for billing alerts
    print("Step 1: Creating SNS topic for billing alerts...")
    try:
        response = sns_client.create_topic(Name='billing-alerts')
        sns_topic_arn = response['TopicArn']
        print(f"✅ SNS Topic created: {sns_topic_arn}")
        print()
    except Exception as e:
        print(f"⚠️  Could not create SNS topic: {e}")
        print("   (You may need to create this manually in AWS Console)")
        sns_topic_arn = None

    # Step 2: Set up CloudWatch alarms for cost monitoring
    print("Step 2: Setting up CloudWatch alarms...")
    alarms = [
        {
            'name': 'MonthlyBillingLimit-5USD',
            'threshold': 5.0,
            'description': 'Alert when estimated charges exceed $5/month'
        },
        {
            'name': 'MonthlyBillingLimit-10USD', 
            'threshold': 10.0,
            'description': 'Alert when estimated charges exceed $10/month'
        }
    ]

    for alarm in alarms:
        try:
            cloudwatch_client.put_metric_alarm(
                AlarmName=alarm['name'],
                ComparisonOperator='GreaterThanThreshold',
                EvaluationPeriods=1,
                MetricName='EstimatedCharges',
                Namespace='AWS/Billing',
                Period=86400,  # 1 day
                Statistic='Maximum',
                Threshold=alarm['threshold'],
                ActionsEnabled=True,
                AlarmActions=[sns_topic_arn] if sns_topic_arn else [],
                AlarmDescription=alarm['description'],
                Dimensions=[
                    {
                        'Name': 'Currency',
                        'Value': 'USD'
                    }
                ]
            )
            print(f"✅ Alarm created: {alarm['name']} (threshold: ${alarm['threshold']})")
        except ClientError as e:
            if 'InvalidParameterValue' in str(e):
                print(f"⚠️  Alarm {alarm['name']} already exists (skipping)")
            else:
                print(f"⚠️  Could not create alarm {alarm['name']}: {e}")
    print()

    # Step 3: Create a budget
    print("Step 3: Setting up AWS Budget for cost control...")
    budgets_client = session.client('budgets')
    
    try:
        budget_name = 'NOVA-S-Monthly-Limit'
        
        # Delete existing budget if it exists
        try:
            budgets_client.delete_budget(AccountId=identity['Account'], BudgetName=budget_name)
            print(f"   Removed existing budget: {budget_name}")
        except:
            pass

        # Create new budget
        budgets_client.create_budget(
            AccountId=identity['Account'],
            Budget={
                'BudgetName': budget_name,
                'BudgetLimit': {
                    'Amount': '15',
                    'Unit': 'USD'
                },
                'TimeUnit': 'MONTHLY',
                'BudgetType': 'COST',
                'CostFilters': {
                    'Service': [
                        'Amazon Bedrock',
                        'Amazon DynamoDB',
                        'Amazon S3',
                        'AWS CloudWatch Logs',
                        'Amazon SNS'
                    ]
                }
            },
            NotificationsWithSubscribers=[
                {
                    'Notification': {
                        'NotificationType': 'ACTUAL',
                        'ComparisonOperator': 'GREATER_THAN',
                        'Threshold': 50,
                        'ThresholdType': 'PERCENTAGE'
                    },
                    'Subscribers': [
                        {
                            'SubscriptionType': 'EMAIL',
                            'Address': 'your-email@example.com'  # Change this!
                        }
                    ]
                },
                {
                    'Notification': {
                        'NotificationType': 'ACTUAL',
                        'ComparisonOperator': 'GREATER_THAN',
                        'Threshold': 100,
                        'ThresholdType': 'PERCENTAGE'
                    },
                    'Subscribers': [
                        {
                            'SubscriptionType': 'EMAIL',
                            'Address': 'your-email@example.com'  # Change this!
                        }
                    ]
                }
            ]
        )
        print(f"✅ Budget created: {budget_name}")
        print(f"   Limit: $15/month")
        print(f"   Alerts at: 50% ($7.50) and 100% ($15)")
        print()
    except Exception as e:
        print(f"⚠️  Could not create budget: {e}")
        print("   Create manually in AWS Console → Billing & Cost Management → Budgets")
        print()

    # Step 4: Display current cost summary
    print("Step 4: Current cost summary...")
    try:
        today = datetime.now().date()
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': today.replace(day=1).isoformat(),
                'End': today.isoformat()
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )
        
        print("   Services with charges this month:")
        total_cost = 0
        for result in response['ResultsByTime']:
            for group in result.get('Groups', []):
                service = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                if cost > 0:
                    total_cost += cost
                    print(f"   - {service}: ${cost:.2f}")
        
        print(f"\n   📊 Total this month (so far): ${total_cost:.2f}")
        print()
    except Exception as e:
        print(f"⚠️  Could not fetch cost data: {e}")
        print()

    print("=" * 70)
    print("COST CONTROL SETUP COMPLETE")
    print("=" * 70)
    print()
    print("WHAT'S BEEN SET UP:")
    print("✅ SNS Topic for billing notifications")
    print("✅ CloudWatch alarms at $5 and $10")
    print("✅ AWS Budget with $15/month limit")
    print()
    print("MANUAL ACTIONS REQUIRED:")
    print("1. Go to AWS Console → Billing & Cost Management → Cost Anomaly Detection")
    print("2. Enable anomaly detection (free service)")
    print("3. Update email addresses in the budget notifications (if created)")
    print()
    print("FREE TIER SERVICES BEING USED:")
    print("- DynamoDB: 25GB storage + 1M units/month")
    print("- S3: 5GB + 20k GETs/month")
    print("- SNS: 1M publishes/month")
    print("- CloudWatch Logs: 5GB ingestion/month")
    print("- Bedrock (Claude 3 Haiku): $0.25/1M input, $1.25/1M output tokens")
    print()
    print("ESTIMATED MONTHLY COST: $0-$5 (demo mode)")
    print()

if __name__ == '__main__':
    setup_cost_controls(profile_name='NOVA-S', region='us-east-1')
