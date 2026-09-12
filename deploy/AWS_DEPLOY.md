# AWS Deploy Kit — Football Blitz Command Center

> Profile: `football-blitz` · Region: `us-east-2` (Ohio) · Recommendation: **t4g.small (free tier 12 months, ~R$0/mês)**

## What's already done (by the agent)

| Step | Status |
|---|---|
| AWS CLI v2.36.43 installed (no-admin, `~/aws-cli`) | ✅ |
| PATH persisted in `~/.bashrc` | ✅ |
| Profile `football-blitz` created with region `us-east-2` | ✅ |
| `uv` installed (Agent Toolkit prerequisite) | ✅ |
| One-click login script `tools/aws_login.bat` | ✅ |

## Your one remaining step (needs your browser)

Double-click **`tools/aws_login.bat`** (or run it in a terminal). A browser window opens → sign in with your AWS account → the script verifies credentials automatically.

- Credentials stay valid **12 hours** and renew for **90 days** without re-login.
- If the popup doesn't appear, run: `~/aws-cli/aws login --region us-east-2 --profile football-blitz`

After login succeeds, install the Agent Toolkit (one command, `us-east-1` on purpose — the service only exists there):

```bash
~/aws-cli/aws configure agent-toolkit --yes --region us-east-1 --profile football-blitz
```

## EC2 setup (after login)

```bash
# 1. Key pair (one time)
~/aws-cli/aws ec2 create-key-pair --key-name football-blitz --profile football-blitz --query 'KeyMaterial' --output text > ~/football-blitz.pem

# 2. Security group: SSH + dashboard
~/aws-cli/aws ec2 create-security-group --group-name football-blitz-sg --description "Blitz dashboard" --profile football-blitz
~/aws-cli/aws ec2 authorize-security-group-ingress --group-name football-blitz-sg --protocol tcp --port 22 --cidr $(curl -s ifconfig.me)/32 --profile football-blitz
~/aws-cli/aws ec2 authorize-security-group-ingress --group-name football-blitz-sg --protocol tcp --port 443 --cidr 0.0.0.0/0 --profile football-blitz

# 3. Launch free-tier instance (ARM — cheaper and free for 12 months)
~/aws-cli/aws ec2 run-instances \
  --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-arm64-amzn-ami-2023-latest-kernel \
  --instance-type t4g.small \
  --key-name football-blitz \
  --security-group-ids football-blitz-sg \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=football-blitz}]' \
  --profile football-blitz
```

Then SSH in and deploy with the existing Docker kit:

```bash
ssh -i ~/football-blitz.pem ec2-user@<PUBLIC_IP>
# inside the instance: install docker, clone the repo, compose up
sudo dnf install -y docker git && sudo systemctl enable --now docker
git clone https://github.com/Victor-Enginner/Football-Blitz-Card-cassino.git
cd Football-Blitz-Card-cassino/deploy && sudo docker compose up -d
```

Full details (Caddy TLS, backups, costs) live in `VPS_DEPLOY.md` — the same compose stack runs on EC2 unchanged.

## Cost summary

| Item | Cost |
|---|---|
| t4g.small free tier (12 mo) | R$ 0/mês |
| t4g.small after free tier | ~US$ 6/mo (~R$ 33) |
| EBS 20GB gp3 | ~US$ 1.6/mo |
| **Total first year** | **~R$ 10/mês** (storage only) |

⚠️ The casino **observer stays on your PC** (manual login + BR IP); the cloud runs dashboard, agents, ledger and Telegram 24/7.
