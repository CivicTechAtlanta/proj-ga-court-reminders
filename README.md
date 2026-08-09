# GA Court Reminders

Lambda functions that send SMS court date reminders.

## Setting up AWS and CDK
1. Install [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
2. Install aws cdk cli using npm (`npm install -g aws-cdk`)
3. Make sure you're logged in to AWS. Configure login with aws cli (`aws login`). 


## Local Development
1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Install dependencies (For details, see "setup" in repo top-level [`Makefile`](./Makefile)):
   ```bash
   make setup
   ```
3. After CDK changes, run `cdk deploy`. If actively developing, run `cdk watch` in a different terminal


## Running Locally
not yet sorted

## Adding a new dependency
```bash
uv add <dependency name>
```

