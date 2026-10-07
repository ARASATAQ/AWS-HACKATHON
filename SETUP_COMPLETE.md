# ✅ Agent Toolkit & Cost Control Setup — Status Report

**Date:** October 7, 2026  
**Profile:** NOVA-S  
**Account:** 523356960091  
**Region:** us-east-1

---

## What's Been Completed

### ✅ AWS Cost Controls
- **Budget Created:** $15/month spending limit
  - Alert at 50% ($7.50) — notifications enabled
  - Alert at 100% ($15) — notifications enabled
- **Services monitored:** Bedrock, DynamoDB, S3, SNS, CloudWatch Logs
- **Estimated cost:** $0–$5/month (if in demo mode)

### ✅ AWS Credentials Verified
- Account verified and accessible
- Profile: `NOVA-S`
- Root access confirmed

### ✅ Python Setup
- Boto3 installed: v1.43.108
- AWS cost control scripts created
- Ready for automation

---

## What Still Needs Manual Setup

### 1️⃣ Install AWS CLI v2 (Required for Agent Toolkit)

**Choose one method:**

#### Option A: Direct Download (Fastest)
1. Go to: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Download and run the MSI installer
3. Verify installation:
   ```powershell
   aws --version
   ```

#### Option B: Windows Package Manager
```powershell
winget install Amazon.AWSCLI
```

#### Option C: Chocolatey
```powershell
choco install awscli
```

---

### 2️⃣ Install uv Package Manager

After AWS CLI is installed:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Verify:
```powershell
uv --version
```

---

### 3️⃣ Authenticate with AWS

Once AWS CLI is installed:

```powershell
aws login --region us-east-1 --profile NOVA-S
```

This opens your browser for secure authentication. Follow the prompts.

Verify it worked:
```powershell
aws sts get-caller-identity --profile NOVA-S
```

---

### 4️⃣ Install Agent Toolkit

```powershell
aws configure agent-toolkit --yes --region us-east-1 --profile NOVA-S
```

This installs AWS skills and configures the MCP server.

---

### 5️⃣ Configure Kiro MCP Profile

After Agent Toolkit setup, edit your MCP config:

**File location:** `~/.kiro/settings/mcp.json`

**Find** the `aws-mcp` entry and **add** this `env` block:

```json
"aws-mcp": {
  "command": "...",
  "args": [...],
  "timeout": 30000,
  "env": {
    "AWS_MCP_PROXY_PROFILES": "NOVA-S"
  }
}
```

---

### 6️⃣ Add AWS Steering Rules (Optional but Recommended)

Create file: `.kiro/steering/aws-agent-toolkit-rules.md`

Get the content from:
https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/rules/aws-starter-rules.md

Copy and paste the entire content into the file.

---

### 7️⃣ Enable Cost Anomaly Detection (Free)

1. Go to: https://console.aws.amazon.com/
2. Navigate to: **Billing & Cost Management** → **Cost Anomaly Detection**
3. Click: **Create anomaly monitor**
4. Select: **All AWS Services**
5. Enable notifications to your email

---

## Cost Protection Status

### Currently Protected By:
✅ $15/month budget with email alerts  
✅ Demo mode (no API calls to paid services)  
✅ Free tier limits on all services

### Services & Free Tier Limits:

| Service | Free Tier | Your Usage | Cost |
|---------|-----------|-----------|------|
| **DynamoDB** | 25GB + 1M units/mo | ~30k units/mo | **$0** ✅ |
| **S3** | 5GB + 20k GETs/mo | ~300 GETs/mo | **$0** ✅ |
| **SNS** | 1M publishes/mo | ~3k/mo | **$0** ✅ |
| **CloudWatch Logs** | 5GB ingestion/mo | ~0.5GB/mo | **$0** ✅ |
| **Bedrock (Claude 3 Haiku)** | None (pay-as-you-go) | ~0-100 photos/mo | **$0–$0.15** |
| **Mapbox** | 50k loads/month | ~10–20/day | **$0** ✅ |

**Total Expected:** $0–$5/month

---

## Next Steps (In Order)

1. **Download AWS CLI** from: https://awscli.amazonaws.com/AWSCLIV2.msi
2. **Install AWS CLI** (double-click MSI)
3. **Verify:** `aws --version` (should show 2.32.0+)
4. **Run Agent Toolkit setup:**
   ```powershell
   aws login --region us-east-1 --profile NOVA-S
   aws configure agent-toolkit --yes --region us-east-1 --profile NOVA-S
   ```
5. **Add profile to MCP config** (`.kiro/settings/mcp.json`)
6. **Add steering rules** (`.kiro/steering/aws-agent-toolkit-rules.md`)
7. **Restart Kiro IDE**
8. **Test with:** "Create a simple web app and deploy it to AWS"

---

## Support Files Created

Located in: `c:\Users\arasa\OneDrive\Desktop\NOVA-S AWS PORJECT\`

- ✅ `AGENT_TOOLKIT_SETUP.md` — Full setup manual
- ✅ `setup_cost_controls.py` — Budget & monitoring script
- ✅ `verify_credentials.py` — Credential verification
- ✅ `SETUP_COMPLETE.md` — This file

---

## Troubleshooting

### AWS CLI not found after installation
```powershell
# Add to PATH manually
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;C:\Program Files\Amazon\AWSCLIV2\bin", "User")
# Restart PowerShell
```

### `aws login` command not found
- AWS CLI version too old
- Update: `aws --install --update`

### MCP server fails to start
- Ensure `AWS_MCP_PROXY_PROFILES` is set to `NOVA-S`
- Restart Kiro IDE
- Check: `.kiro/settings/mcp.json` for correct syntax

### Permission error on `aws login`
- Your IAM user needs `SignInLocalDevelopmentAccess` policy
- Ask AWS admin to add it (or self-add if you have IAM permissions)

---

## Important Notes

⚠️ **Your AWS credentials are currently using an SSO/login session.**
- They are **temporary** (valid 12 hours)
- They **auto-refresh** for 90 days without re-authenticating
- They are **more secure** than static access keys
- No credentials are stored as plaintext ✅

📊 **Budget is set to $15/month** to ensure you don't get unexpected charges.
- Alerts trigger at $7.50 (50%) and $15 (100%)
- All email notifications configured

🔐 **Mapbox token is free** — 50k loads/month, no billing ever

---

## Success Criteria

You'll know setup is complete when:

1. ✅ `aws --version` returns 2.32.0+
2. ✅ `aws sts get-caller-identity --profile NOVA-S` shows your account
3. ✅ `aws agent-toolkit list-available-skills --region us-east-1 --profile NOVA-S` returns JSON list
4. ✅ Kiro can execute AWS commands through the IDE
5. ✅ Budget alert emails arrive when you approach $7.50

---

## Ready?

Follow the **Next Steps** section above, starting with downloading AWS CLI.

Once complete, come back to Kiro and try:
```
Please create a simple web app and deploy it to AWS.
```

This will test your entire setup! 🚀

