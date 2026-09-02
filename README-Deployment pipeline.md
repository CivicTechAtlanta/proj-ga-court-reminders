## Things to be aware of
- If you delete and recreate the GithubActionStack, make sure to update AWS_GITHUBACTIONROLE_ARN secret for the repo. It will be in Settings
- The thumbprint value in the `OIDCProvider` could potentially change. If the aws config step fails, this could be something to check.
- The GitHub Actions role is deployed by hand, not by the pipeline. After changing its policy in `cdk_stack/github_stack.py`, someone with admin credentials must run `uv run cdk deploy GithubActionStack`; the role ARN does not change, so the secret stays the same. The role assumes CDK's bootstrap roles (`cdk-hnb659fds-*`), which the deploy needs for context lookups such as VPC availability zones.
