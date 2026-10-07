# Agent Toolkit for AWS — Manual Setup Guide

Since automated remote script downloads are timing out, follow these manual steps:

## Step 1: Install AWS CLI v2

### Option A: Direct Download (Recommended)
1. Go to: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Download the MSI installer
3. Double-click to install (default location: `C:\Program Files\Amazon\AWSCLIV2\`)
4. Verify installation:
```powershell
aws --version
```

### Option B: Using Chocolatey (if installed)
```powershell
choco install awscli
```

### Option C: Using Windows Package Manager
```powershell
winget install Amazon.AWSCLI
```

---

## Step 2: Configure AWS Region

Once AWS CLI is installed, set your default region:

```powershell
aws configure set region us-east-1 --profile NOVA-S
```

---

## Step 3: Log in to AWS

Sign in using browser-based authentication:

```powershell
aws login --region us-east-1 --profile NOVA-S
```

**What happens:**
- A browser window opens automatically
- You log in with your AWS account
- Credentials are stored securely (valid for 12 hours, refreshable for 90 days)
- Return to terminal — credentials are ready

---

## Step 4: Verify AWS Access

Test that credentials work:

```powershell
aws sts get-caller-identity --profile NOVA-S
```

**Expected output:**
```json
{
    "UserId": "...",
    "Account": "523356960091",
    "Arn": "arn:aws:iam::523356960091:root"
}
```

---

## Step 5: Install uv Package Manager

uv is needed for the Agent Toolkit. Choose one method:

### Option A: PowerShell (Recommended for Windows)
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Then restart PowerShell and verify:
```powershell
uv --version
```

### Option B: Download Script First
1. Go to: https://astral.sh/uv/install.ps1
2. Save as `uv_install.ps1`
3. Run: `.\uv_install.ps1`

---

## Step 6: Install Agent Toolkit

Once AWS CLI and uv are installed:

```powershell
aws configure agent-toolkit --yes --region us-east-1 --profile NOVA-S
```

**What happens:**
- Installs AWS Agent Toolkit skills
- Configures AWS MCP server
- Updates `.kiro/settings/mcp.json` with AWS integration

---

## Step 7: Configure MCP Profile

After the agent toolkit command completes, you need to add the profile to your MCP config:

1. Open: `~/.kiro/settings/mcp.json` (or `.kiro/settings/mcp.json` in your workspace)

2. Find the `aws-mcp` server entry:
```json
"mcpServers": {
  "aws-mcp": {
    "command": "...",
    "args": [...],
    "timeout": 30000
  }
}
```

3. Add the `env` block with your profile:
```json
"mcpServers": {
  "aws-mcp": {
    "command": "...",
    "args": [...],
    "timeout": 30000,
    "env": {
      "AWS_MCP_PROXY_PROFILES": "NOVA-S"
    }
  }
}
```

---

## Step 8: Verify Agent Toolkit Installation

List available skills:

```powershell
aws agent-toolkit list-available-skills --region us-east-1 --profile NOVA-S
```

**Expected output:** JSON list of available skills (bedrock, ec2, s3, dynamodb, etc.)

---

## Step 9: Add AWS Steering Rules

Fetch the AWS Agent Toolkit rules for Kiro:

```powershell
# For new AWS experience (recommended)
$rules = (Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/rules/aws-starter-rules.md').Content
$rules | Out-File -FilePath '.kiro/steering/aws-agent-toolkit-rules.md' -Encoding UTF8
```

Or manually:
1. Go to: https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/rules/aws-starter-rules.md
2. Copy the content
3. Create `.kiro/steering/aws-agent-toolkit-rules.md`
4. Paste the content

---

## Troubleshooting

### "aws: command not found"
- AWS CLI not installed or not in PATH
- Restart PowerShell after installation
- Or add to PATH manually: `[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;C:\Program Files\Amazon\AWSCLIV2\bin", "User")`

### "aws login: command not found"
- AWS CLI version is too old (need 2.32.0+)
- Update: `aws --install --update`

### "SignInLocalDevelopmentAccess" permission error
- Your IAM user needs the `SignInLocalDevelopmentAccess` policy attached
- Ask your AWS admin to add it, or self-add if you have IAM permissions

### Network timeouts during installation
- Try installing during off-peak hours
- Use a VPN if your ISP blocks downloads
- Download installers manually and run locally

---

## Summary

After completing these steps:

1. ✅ AWS CLI installed and authenticated
2. ✅ Agent Toolkit installed and configured
3. ✅ Kiro MCP server linked to your AWS account
4. ✅ AWS steering rules loaded in Kiro

You can now use AWS commands and skills directly in Kiro sessions to:
- Deploy infrastructure
- Manage resources
- Create applications
- And much more!

**Next steps:** Close and restart Kiro, then try this prompt:
> "Create a single-page web game and deploy it to AWS"

