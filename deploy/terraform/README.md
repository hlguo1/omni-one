# omni-one Terraform — single-box on AWS (VPC-lite)

Provisions: default-VPC EC2 (`t3.small`) + 20 GB EBS volume for `./data`
(DuckDB + audit + closes) + security group opening **5003** + CloudWatch
log group `/omni-one/api`. Outputs `api_url`.

## Cost note (~us-east-1, on-demand, 2026 prices)

| Piece | ~$/mo |
|---|---|
| `t3.small` 24/7 | ~$15 |
| 20 GB `gp3` EBS | ~$1.60 |
| CloudWatch logs (30-day retention, demo traffic) | <$1 |
| **Total** | **~$17/mo** |

Stop the instance when not demoing (`aws ec2 stop-instances`) — the EBS
volume keeps `./data` and costs ~$1.60/mo at rest. For HA/scale use the
Helm chart (HPA 2–6 replicas) instead of upsizing this box.

## State backend warning

> **Do NOT `terraform apply` with local state for anything shared.**
> Uncomment the `backend "s3"` block in `versions.tf` FIRST (encrypted
> bucket + `dynamodb_table` lock), then `terraform init -migrate-state`.
> Local `terraform.tfstate` contains IPs/ids and WILL be lost or conflict
> on a second machine. Never commit `*.tfstate*` to git.

## Use

```sh
terraform init
terraform plan -var key_name=my-key
terraform apply -var key_name=my-key
terraform output api_url   # -> http://<ip>:5003
curl "$(terraform output -raw api_url)/health"
terraform destroy          # EBS volume is NOT auto-deleted; remove it by hand if done
```
